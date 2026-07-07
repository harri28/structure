"""
Parser de presupuestos S10 exportados en PDF.
Extrae partidas con jerarquía (hasta 5 niveles) y las importa directamente
al modelo Partida sin pasar por un archivo intermedio.
"""

import re
import io
from decimal import Decimal, InvalidOperation

from django.db import transaction

try:
    import fitz          # PyMuPDF
    PYMUPDF_OK = True
except ImportError:
    PYMUPDF_OK = False

from .models import Partida


def computar_parciales(presupuesto):
    """
    Calcula y persiste el total (parcial) de cada partida del presupuesto,
    bottom-up: primero hojas (cantidad × precio_unitario), luego capítulos
    acumulando sus descendientes. Usa bulk_update para mínimas queries.
    """
    todas = list(
        presupuesto.partidas
        .order_by('-nivel', 'orden')
        .values('pk', 'padre_id', 'cantidad', 'precio_unitario')
    )

    acum = {}
    for p in todas:
        pk       = p['pk']
        padre_id = p['padre_id']
        if pk not in acum:
            # Hoja: ningún hijo la ha acumulado aún
            acum[pk] = float(p['cantidad']) * float(p['precio_unitario'])
        if padre_id:
            acum[padre_id] = acum.get(padre_id, 0) + acum[pk]

    updates = [
        Partida(pk=pk, parcial=Decimal(str(round(val, 2))))
        for pk, val in acum.items()
    ]
    Partida.objects.bulk_update(updates, ['parcial'], batch_size=2000)


# ── Coordenadas de columnas S10 (puntos PDF) ─────────────────────────
COLS = {
    'item':    (0,    108),
    'desc':    (108,  342),
    'und':     (342,  408),
    'metrado': (408,  452),
    'precio':  (452,  500),
}

RE_CODIGO   = re.compile(r'^\d{1,2}(\.\d{2,})*$')
RE_PCT_VAL  = re.compile(r'\(\s*(\d+(?:[.,]\d+)?)\s*%', re.I)

IGNORAR_DESC = {
    'COSTO DIRECTO', 'GASTOS GENERALES', 'UTILIDAD',
    'SUB TOTAL', 'SUB-TOTAL', 'IMPUESTO', 'IGV',
    'TOTAL PRESUPUESTO', 'SON:', 'SON',
}

IGNORAR_KEYWORDS = ('TOTAL PRESUPUESTO', 'TOTAL DE OBRA', 'COSTO DE OBRA',
                    'COSTO TOTAL', 'PRESUPUESTO TOTAL')


# ── Utilidades ────────────────────────────────────────────────────────

def _es_codigo(s: str) -> bool:
    return bool(RE_CODIGO.match(s.strip()))


def _a_decimal(val) -> Decimal:
    if val is None or val == '':
        return Decimal('0')
    try:
        s = str(val).strip().replace(',', '')
        return Decimal(s).quantize(Decimal('0.0001'))
    except (InvalidOperation, ValueError):
        return Decimal('0')


def _nivel(codigo: str) -> int:
    """Nivel jerárquico a partir del código S10: 01→1, 01.01→2, 01.01.01→3 …"""
    s = codigo.strip()
    try:
        f = float(s)
        return 1 if f == int(f) else 2
    except ValueError:
        pass
    return len(s.split('.'))


def _col_de(x: float) -> str:
    for nombre, (x0, x1) in COLS.items():
        if x0 <= x < x1:
            return nombre
    return 'parcial'


def _es_numero(s: str) -> bool:
    try:
        float(s.strip().replace(',', ''))
        return True
    except ValueError:
        return False


# ── Extracción por página ─────────────────────────────────────────────

def _palabras_por_fila(page) -> list:
    """Agrupa palabras del PDF por línea (tolerancia Y=3 pt)."""
    words = page.get_text("words")
    if not words:
        return []
    grupos = {}
    for w in words:
        x0, y0, texto = w[0], w[1], w[4]
        y_key = round(y0 / 3) * 3
        grupos.setdefault(y_key, []).append((x0, texto))
    return [sorted(v, key=lambda t: t[0]) for _, v in sorted(grupos.items())]


def _parsear_pagina(page) -> tuple[list, list]:
    """Retorna (partidas, resumenes). 'resumenes' son las filas de totales/porcentajes."""
    filas_raw = _palabras_por_fila(page)
    partidas  = []
    resumenes = []

    # Saltar encabezado hasta la fila con "Item" / "Descripción"
    inicio = 0
    for i, fila in enumerate(filas_raw):
        textos = [t.lower() for _, t in fila]
        if any(t in ('item', 'ítem', 'descripción', 'descripcion') for t in textos):
            inicio = i + 1
            break

    for fila in filas_raw[inicio:]:
        row = {k: [] for k in ('item', 'desc', 'und', 'metrado', 'precio')}
        for x, texto in fila:
            col = _col_de(x)
            if col == 'und' and _es_numero(texto):
                col = 'metrado'
            if col in row:
                row[col].append(texto)

        item  = ' '.join(row['item']).strip()
        desc  = ' '.join(row['desc']).strip()
        und   = ' '.join(row['und']).strip()
        metrado_raw = ' '.join(row['metrado']).strip()
        precio_raw  = ' '.join(row['precio']).strip()

        if not item and not desc:
            continue
        desc_up = desc.strip().upper()
        item_up = item.strip().upper()

        es_resumen = (
            desc_up in IGNORAR_DESC
            or item_up in IGNORAR_DESC
            or any(kw in desc_up or kw in item_up for kw in IGNORAR_KEYWORDS)
        )
        if es_resumen:
            resumenes.append({'item': item, 'desc': desc, 'precio': precio_raw})
            continue

        partidas.append({
            'item':    item,
            'desc':    desc,
            'und':     und,
            'metrado': metrado_raw,
            'precio':  precio_raw,
        })

    return partidas, resumenes


def _extraer_porcentajes(resumenes: list) -> dict:
    """Lee las filas de resumen y extrae GG%, Utilidad%, IGV%, Supervisión%."""
    pcts = {}
    for r in resumenes:
        texto = (r.get('item', '') + ' ' + r.get('desc', '')).upper()
        m = RE_PCT_VAL.search(texto)
        if not m:
            continue
        val = float(m.group(1).replace(',', '.'))
        if 'SUPERVISION' in texto or 'SUPERVISIÓN' in texto:
            pcts['supervision_pct'] = val
        elif 'GASTOS GENERALES' in texto:
            pcts['gastos_generales_pct'] = val
        elif 'UTILIDAD' in texto:
            pcts['utilidad_pct'] = val
        elif 'I.G.V' in texto or 'IGV' in texto or 'IMPUESTO' in texto:
            pcts['igv_pct'] = val
    return pcts


def _fusionar(registros: list) -> list:
    """Fusiona líneas de continuación (descripción que desborda a la fila siguiente)."""
    resultado = []
    for r in registros:
        item = r['item']
        desc = r['desc']

        if not item and desc and resultado:
            prev = resultado[-1]
            if not prev['desc']:
                prev['desc']    = desc
                prev['und']     = prev['und']    or r['und']
                prev['metrado'] = prev['metrado'] or r['metrado']
                prev['precio']  = prev['precio']  or r['precio']
            else:
                prev['desc'] += ' ' + desc
            continue

        resultado.append({
            'item':    item if _es_codigo(item) else '',
            'desc':    desc,
            'und':     r['und'],
            'metrado': r['metrado'],
            'precio':  r['precio'],
        })
    return resultado


# ── API principal ─────────────────────────────────────────────────────

def parsear_pdf_a_partidas(archivo_django) -> tuple[list, dict]:
    """
    Recibe un InMemoryUploadedFile de Django (PDF).
    Retorna (partidas, porcentajes):
      partidas:    [{'item', 'desc', 'und', 'metrado', 'precio'}, ...]
      porcentajes: {'gastos_generales_pct', 'utilidad_pct', 'igv_pct', 'supervision_pct'} (parcial)
    Lanza ImportError si PyMuPDF no está instalado.
    Lanza ValueError si el archivo no es un PDF válido.
    """
    if not PYMUPDF_OK:
        raise ImportError(
            'PyMuPDF no está instalado. Ejecuta: pip install pymupdf'
        )

    contenido = archivo_django.read()

    try:
        doc = fitz.open(stream=io.BytesIO(contenido), filetype='pdf')
    except Exception:
        raise ValueError('El archivo no es un PDF válido o está dañado.')

    todos    = []
    resumenes = []
    for num in range(len(doc)):
        p, r = _parsear_pagina(doc[num])
        todos.extend(p)
        resumenes.extend(r)
    doc.close()

    return _fusionar(todos), _extraer_porcentajes(resumenes)


def importar_pdf(archivo_django, presupuesto) -> tuple[int, list]:
    """
    Importa partidas desde un PDF al presupuesto dado.
    Retorna (total_importadas, advertencias).
    Usa ML precio_historico para detectar partidas con precios atípicos.
    """
    from . import ml as ml_engine

    filas, pcts = parsear_pdf_a_partidas(archivo_django)

    # Guardar porcentajes extraídos del PDF (GG%, Utilidad%, IGV%, Supervisión%)
    if pcts:
        update_fields = []
        for campo, valor in pcts.items():
            if hasattr(presupuesto, campo):
                setattr(presupuesto, campo, Decimal(str(valor)))
                update_fields.append(campo)
        if update_fields:
            presupuesto.save(update_fields=update_fields)

    pila    = {}
    orden   = 0
    total   = 0
    avisos  = []
    hojas_ml = []  # (nombre, codigo, pu) for ML check after bulk insert

    with transaction.atomic():
        presupuesto.partidas.all().delete()

        for fila in filas:
            codigo   = fila['item'].strip()
            nombre_p = fila['desc'].strip()

            if not codigo or not nombre_p:
                continue
            if not _es_codigo(codigo):
                continue

            nivel  = _nivel(codigo)
            padre  = pila.get(nivel - 1)
            cant   = _a_decimal(fila['metrado'])
            pu     = _a_decimal(fila['precio'])

            partida = Partida.objects.create(
                presupuesto=presupuesto,
                padre=padre,
                codigo=codigo,
                nombre=nombre_p,
                nivel=nivel,
                orden=orden,
                unidad=fila['und'][:20],
                cantidad=cant,
                precio_unitario=pu,
            )
            pila[nivel] = partida
            for k in list(pila.keys()):
                if k > nivel:
                    del pila[k]
            orden += 1
            total += 1

            if nivel >= 3 and pu > 0:
                hojas_ml.append((nombre_p, codigo, float(pu)))

    # ML price check outside the transaction (read-only, capped to avoid timeout)
    for nombre_p, codigo, pu_f in hojas_ml[:300]:
        hist = ml_engine.precio_historico(nombre_p, excluir_presupuesto_id=presupuesto.pk)
        if hist:
            diff_pct = abs(pu_f - hist['media']) / hist['media'] * 100
            if diff_pct > 40:
                avisos.append({
                    'codigo':   codigo,
                    'nombre':   nombre_p[:60],
                    'pu':       pu_f,
                    'ml_media': hist['media'],
                    'diff_pct': round(diff_pct, 1),
                })

    computar_parciales(presupuesto)
    ml_engine.invalidar_cache()
    return total, avisos
