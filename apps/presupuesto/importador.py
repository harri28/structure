"""
Importador flexible de presupuestos Excel.

Soporta dos formatos:
  - Formato S10 clásico: columnas Ítem | Descripción | Und | Metrado | P.U.
  - Formato propio (Conila/oferta): Hoja1 con col A=código, B=descripción,
    C=unidad, D=metrado, E=P.U., F=subtotal

Detecta automáticamente la hoja más limpia y la fila de encabezados.
Soporta jerarquías de hasta 5 niveles.
"""

import io
import re
import openpyxl
import xlrd
from decimal import Decimal, InvalidOperation
from .models import Partida, InsumoPresupuesto


# ── Utilidades ──────────────────────────────────────────────────

def _to_decimal(val):
    try:
        return Decimal(str(val)).quantize(Decimal('0.0001'))
    except (InvalidOperation, TypeError, ValueError):
        return Decimal('0')


def _nivel_codigo(codigo):
    """
    Determina el nivel jerárquico a partir del código de ítem.
    Maneja:
      1, 2, 3          → nivel 1
      1.01, 1.02       → nivel 2  (float con 2 decimales)
      01.01.01         → nivel 3  (string con puntos)
      01.01.01.01      → nivel 4
      01.05.01.01.01   → nivel 5
    """
    if not codigo:
        return 1
    s = str(codigo).strip()
    # Intentar como número
    try:
        f = float(s)
        if f == int(f):
            return 1            # 1, 2, 3, 1.0, 2.0 → nivel 1
        return 2                # 1.1, 1.01, 1.10 → nivel 2
    except ValueError:
        pass
    # Formato string con puntos: 01.01.01, 01.01.01.01, 01.05.01.01.01
    partes = s.split('.')
    return len(partes)


def _es_fila_encabezado(row):
    """Devuelve True si la fila parece ser una cabecera de columnas."""
    textos = [str(c).strip().lower() for c in row if c is not None]
    keywords = {'item', 'partida', 'descripcion', 'descripción', 'und', 'unidad', 'metrado', 'cant.', 'pu', 'p.u.', 'precio'}
    return bool(keywords & set(textos))


def _detectar_columnas(row):
    """
    A partir de la fila de encabezado, devuelve un dict con los índices
    de columna para cada campo: codigo, nombre, unidad, cantidad, precio_unitario.
    Si no encuentra alguna columna, usa el offset posicional desde la primera col con datos.
    """
    mapping = {}
    for i, cell in enumerate(row):
        if cell is None:
            continue
        t = str(cell).strip().lower()
        if t in ('item', 'ítem', 'partida', 'cod', 'código', 'codigo') and 'codigo' not in mapping:
            mapping['codigo'] = i
        elif t in ('descripcion', 'descripción', 'descripcion.', 'nombre') and 'nombre' not in mapping:
            mapping['nombre'] = i
        elif t in ('und', 'unid.', 'unid', 'unidad', 'u.m.') and 'unidad' not in mapping:
            mapping['unidad'] = i
        elif t in ('metrado', 'cant.', 'cant', 'cantidad', 'medida') and 'cantidad' not in mapping:
            mapping['cantidad'] = i
        elif t in ('pu', 'p.u.', 'precio', 'precio unit.', 'p. unit.', 'p.unitario') and 'precio_unitario' not in mapping:
            mapping['precio_unitario'] = i

    # Fallback: si no detectó el código, buscar la primera columna con datos no-None
    if 'codigo' not in mapping:
        for i, cell in enumerate(row):
            if cell is not None:
                mapping.setdefault('codigo', i)
                mapping.setdefault('nombre', i + 1)
                mapping.setdefault('unidad', i + 2)
                mapping.setdefault('cantidad', i + 3)
                mapping.setdefault('precio_unitario', i + 4)
                break
    return mapping


def _es_codigo_valido(val):
    """Determina si un valor puede ser un código de ítem (no un header ni texto largo)."""
    if val is None:
        return False
    s = str(val).strip()
    if not s or len(s) > 25:
        return False
    # Número entero
    try:
        f = float(s)
        return f > 0
    except ValueError:
        pass
    # Patrón de código: dígitos y puntos únicamente (01.01.01.01)
    return bool(re.match(r'^\d+(\.\d+)+$', s))


def _elegir_hoja(wb):
    """Elige la hoja más limpia para importar el presupuesto."""
    preferidas = ['hoja1', 'presupuesto', 'partidas', 'budget']
    for nombre in wb.sheetnames:
        if nombre.lower().strip() in preferidas:
            return wb[nombre]
    return wb.active


# ── Importador principal ─────────────────────────────────────────

def importar_presupuesto_excel(archivo, presupuesto):
    """
    Lee un archivo .xlsx/.xls e importa las partidas al presupuesto dado.
    Retorna la cantidad de partidas importadas.
    """
    nombre = getattr(archivo, 'name', '').lower()

    if nombre.endswith('.xls'):
        filas = _leer_xls(archivo)
    else:
        filas = _leer_xlsx(archivo)

    presupuesto.partidas.all().delete()

    pila = {}   # nivel → partida
    orden = 0
    total = 0

    for fila in filas:
        codigo = str(fila.get('codigo', '') or '').strip()
        nombre_p = str(fila.get('nombre', '') or '').strip()

        if not codigo or not nombre_p:
            continue
        if _es_fila_encabezado([codigo, nombre_p]):
            continue
        if not _es_codigo_valido(codigo):
            continue

        nivel = _nivel_codigo(codigo)
        padre = pila.get(nivel - 1)

        partida = Partida.objects.create(
            presupuesto=presupuesto,
            padre=padre,
            codigo=codigo,
            nombre=nombre_p,
            nivel=nivel,
            orden=orden,
            unidad=str(fila.get('unidad', '') or '').strip()[:20],
            cantidad=_to_decimal(fila.get('cantidad')),
            precio_unitario=_to_decimal(fila.get('precio_unitario')),
        )
        pila[nivel] = partida
        # Limpiar niveles más profundos
        for k in list(pila.keys()):
            if k > nivel:
                del pila[k]
        orden += 1
        total += 1

    return total


# ── Importador de insumos ────────────────────────────────────────

TIPO_MAP = {
    'MANO DE OBRA':  'MANO_OBRA',
    'MANO DE OBRA.': 'MANO_OBRA',
    'MATERIALES':    'MATERIAL',
    'MATERIAL':      'MATERIAL',
    'EQUIPO':        'EQUIPO',
    'EQUIPOS':       'EQUIPO',
    'MAQUINARIA':    'EQUIPO',
    'SUB-CONTRATOS': 'SUBCONTRATO',
    'SUBCONTRATOS':  'SUBCONTRATO',
    'SUBCONTRATO':   'SUBCONTRATO',
}


def importar_insumos_excel(archivo, presupuesto):
    """
    Lee el archivo de insumos (lista plana con categorías) e importa a InsumoPresupuesto.
    Formato esperado: col C=código, D=descripción, E=unidad, F=cantidad, G=costo_unitario, H=total
    Las filas sin código pero con descripción en mayúsculas marcan el tipo de insumo.
    """
    nombre = getattr(archivo, 'name', '').lower()
    contenido = archivo.read()
    if nombre.endswith('.xls'):
        wb = xlrd.open_workbook(file_contents=contenido)
        ws = wb.sheet_by_index(0)
        raw_rows = [[ws.cell_value(r, c) for c in range(ws.ncols)] for r in range(ws.nrows)]
    else:
        wb = openpyxl.load_workbook(io.BytesIO(contenido), read_only=True, data_only=True)
        ws = wb.active
        raw_rows = list(ws.iter_rows(values_only=True))
        wb.close()

    presupuesto.insumos.all().delete()

    tipo_actual = 'MATERIAL'
    col_cod, col_desc, col_und, col_cant, col_costo = 2, 3, 4, 5, 6  # columnas C-G (base 0)
    total = 0

    for row in raw_rows:
        def get(idx):
            try: return row[idx]
            except IndexError: return None

        cod  = get(col_cod)
        desc = get(col_desc)

        # Fila de categoría: sin código, descripción en mayúsculas
        if cod is None and desc:
            desc_up = str(desc).strip().upper()
            if desc_up in TIPO_MAP:
                tipo_actual = TIPO_MAP[desc_up]
                continue

        # Saltar filas sin código válido
        if not _es_codigo_valido(cod) or not desc:
            continue

        InsumoPresupuesto.objects.create(
            presupuesto=presupuesto,
            tipo=tipo_actual,
            codigo=str(cod).strip().split('.')[0] if cod else '',
            descripcion=str(desc).strip()[:400],
            unidad=str(get(col_und) or '').strip()[:20],
            cantidad=_to_decimal(get(col_cant)),
            costo_unitario=_to_decimal(get(col_costo)),
        )
        total += 1

    return total


# ── Leer archivos ────────────────────────────────────────────────

def _leer_xlsx(archivo):
    contenido = io.BytesIO(archivo.read())
    wb = openpyxl.load_workbook(contenido, read_only=True, data_only=True)
    ws = _elegir_hoja(wb)
    raw = list(ws.iter_rows(values_only=True))
    wb.close()

    filas = []
    cols = None
    data_iniciada = False

    for row in raw:
        if not any(c is not None for c in row):
            continue
        if _es_fila_encabezado(row) and not data_iniciada:
            cols = _detectar_columnas(row)
            data_iniciada = True
            continue
        if not data_iniciada:
            continue
        filas.append(_mapear_fila(row, cols))

    # Sin encabezado: usar todas las filas con offset 0
    if not filas:
        for row in raw:
            if any(c is not None for c in row):
                filas.append(_mapear_fila(row, None))
    return filas


def _leer_xls(archivo):
    contenido = archivo.read()
    wb = xlrd.open_workbook(file_contents=contenido)
    ws = wb.sheet_by_index(0)
    filas = []
    cols = None
    data_iniciada = False
    for i in range(ws.nrows):
        row = [ws.cell_value(i, c) for c in range(ws.ncols)]
        if not any(row):
            continue
        if _es_fila_encabezado(row) and not data_iniciada:
            cols = _detectar_columnas(row)
            data_iniciada = True
            continue
        if not data_iniciada:
            continue
        filas.append(_mapear_fila(row, cols))
    return filas


def _mapear_fila(row, cols):
    if not cols:
        cols = {'codigo': 0, 'nombre': 1, 'unidad': 2, 'cantidad': 3, 'precio_unitario': 4}

    def get(key):
        idx = cols.get(key)
        if idx is None:
            return ''
        try:
            v = row[idx]
            return v if v is not None else ''
        except IndexError:
            return ''

    return {
        'codigo':          get('codigo'),
        'nombre':          get('nombre'),
        'unidad':          get('unidad'),
        'cantidad':        get('cantidad'),
        'precio_unitario': get('precio_unitario'),
    }


# Mantener compatibilidad con el nombre anterior
importar_s10_excel = importar_presupuesto_excel
