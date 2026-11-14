"""Catálogo seed de unidades de medida + helper de auto-registro.

Separado de views.py para poder importarlo desde cualquier app sin arrastrar
dependencias circulares. La función `registrar_unidades_desconocidas` se usa
desde el importador de presupuesto para que las abreviaturas detectadas en
los Excel queden grabadas en el catálogo y no reaparezcan como "unidades
no reconocidas" en futuros imports.
"""

UNIDADES_DEFAULT = [
    # (codigo, nombre, descripcion, aliases)
    ('hh',  'Hora Hombre',    'Mano de obra directa',   'HH, hora hombre, horas hombre'),
    ('hm',  'Hora Máquina',   'Equipos y maquinaria',   'HM, hora máquina, horas máquina, hora maquina, horas maquina'),
    ('he',  'Hora Equipo',    'Equipos varios',          'HE, hora equipo, horas equipo'),
    ('m2',  'Metro Cuadrado', '',                        'M2, m², metro cuadrado, metros cuadrados'),
    ('m3',  'Metro Cúbico',   '',                        'M3, m³, metro cúbico, metros cúbicos, metro cubico'),
    ('ml',  'Metro Lineal',   '',                        'ML, mll, metro lineal, metros lineales'),
    ('m',   'Metro',          '',                        'MT, mt, metro, metros'),
    ('kg',  'Kilogramo',      '',                        'KG, Kg, kilogramo, kilogramos'),
    ('tn',  'Tonelada',       '',                        'TN, ton, TON, tonelada, toneladas'),
    ('g',   'Gramo',          '',                        'GR, gr, gramo, gramos'),
    ('lt',  'Litro',          '',                        'LT, lts, LTS, l, L, litro, litros'),
    ('gal', 'Galón',          '',                        'GAL, Gal, galón, galon, galones'),
    ('glb', 'Global',         '',                        'GLB, gb, GL, gl, global, globales'),
    ('und', 'Unidad',         '',                        'UND, un, UN, u, U, unidad, unidades'),
    ('pza', 'Pieza',          '',                        'PZA, Pza, pieza, piezas'),
    ('par', 'Par',            '',                        'PAR, pares'),
    ('jgo', 'Juego',          '',                        'JGO, Jgo, juego, juegos'),
    ('set', 'Set',            '',                        'SET, sets'),
    ('bls', 'Bolsa',          '',                        'BLS, Bls, bolsa, bolsas, bol'),
    ('caj', 'Caja',           '',                        'CAJ, Caj, caja, cajas'),
    ('rll', 'Rollo',          '',                        'RLL, Rll, rollo, rollos'),
    ('plg', 'Pulgada',        '',                        'PLG, Plg, pulgada, pulgadas'),
    ('p2',  'Pie Cuadrado',   '',                        'P2, pie2, pie cuadrado, pies cuadrados'),
    ('p3',  'Pie Cúbico',     '',                        'P3, pie3, pie cúbico, pie cubico, pies cúbicos'),
    ('dia', 'Día',            '',                        'DIA, Dia, día, d'),
    ('mes', 'Mes',            '',                        'MES, Mes'),
    ('sem', 'Semana',         '',                        'SEM, Sem, semana, semanas'),
    ('pln', 'Plancha',        '',                        'PLN, Pln, plancha, planchas'),
]


def _indice_defaults():
    """{alias_lower: (codigo, nombre, descripcion, aliases)} para resolver
    una abreviatura detectada en el import contra el seed de defaults."""
    idx = {}
    for row in UNIDADES_DEFAULT:
        codigo, nombre, descripcion, aliases = row
        idx[codigo.lower()] = row
        for a in aliases.split(','):
            a = a.strip().lower()
            if a:
                idx.setdefault(a, row)
    return idx


def registrar_unidades_desconocidas(codigos):
    """Dado un iterable de códigos detectados en un import que no estaban
    en UnidadMedida, crea las entradas correspondientes y devuelve tres
    listas: (creadas_con_nombre, creadas_sin_nombre, ya_existentes).

    - creadas_con_nombre: se encontraron en los defaults → nombre bonito.
    - creadas_sin_nombre: no se encontraron → nombre = código en mayúsculas.
    - ya_existentes: ya estaban en el catálogo (idealmente no debería
      pasar porque el importador filtra antes, pero cubrimos la carrera).
    """
    from .models import UnidadMedida

    idx = _indice_defaults()
    creadas_con_nombre = []
    creadas_sin_nombre = []
    ya_existentes = []

    for raw in codigos:
        codigo_raw = (raw or '').strip()
        if not codigo_raw:
            continue
        # Doble chequeo contra lo que ya está en BD (por código o por alias).
        existente = UnidadMedida.objects.filter(codigo__iexact=codigo_raw).first()
        if existente:
            ya_existentes.append(existente.codigo)
            continue

        match = idx.get(codigo_raw.lower())
        if match:
            codigo, nombre, descripcion, aliases = match
            # Puede existir con `codigo` canonical distinto al `codigo_raw`
            # del archivo (ej. "MLL" → "ml"). Doble chequeo.
            if UnidadMedida.objects.filter(codigo__iexact=codigo).exists():
                ya_existentes.append(codigo)
                continue
            UnidadMedida.objects.create(
                codigo=codigo, nombre=nombre, descripcion=descripcion,
                aliases=aliases, activo=True,
            )
            creadas_con_nombre.append(codigo)
        else:
            UnidadMedida.objects.create(
                codigo=codigo_raw, nombre=codigo_raw.upper(),
                descripcion='Auto-registrada desde importación de presupuesto',
                aliases='', activo=True,
            )
            creadas_sin_nombre.append(codigo_raw)

    return creadas_con_nombre, creadas_sin_nombre, ya_existentes
