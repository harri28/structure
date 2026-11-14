"""
Reportes de obra — vistas consolidadas para el Jefe de obra.

Cuatro reportes iniciales:
  1. Consumo de insumos por período (salidas agrupadas por insumo).
  2. Ejecutado vs presupuestado por partida (cupo y aprobado por partida nivel 1).
  3. Asistencia mensual del personal (grilla trabajadores × días del mes).
  4. Maquinaria trabajada por período (horas y combustible por máquina).

Cada reporte tiene su versión HTML con filtros y botón de exportar a Excel
(openpyxl, ya en requirements por el módulo de asistencia).
"""
from decimal import Decimal
from datetime import date, timedelta
from calendar import monthrange

from django.shortcuts import render, get_object_or_404, redirect
from django.http import HttpResponse
from django.db.models import Sum, Q, Value, DecimalField as DFld
from django.db.models.functions import Coalesce

from apps.proyectos.models import Proyecto, ProyectoMiembro
from apps.presupuesto.models import Partida, Presupuesto
from apps.almacen.models import DetalleSalida
from apps.maquinaria.models import Asistencia, Trabajador, RegistroMaquinaria
from config.permisos import requiere


def _acceso(request, proyecto):
    """Admite superadmin y miembros del proyecto."""
    if request.user.is_superuser:
        return True
    try:
        if request.user.perfil.rol and request.user.perfil.rol.es_superadmin:
            return True
    except AttributeError:
        pass
    return ProyectoMiembro.objects.filter(proyecto=proyecto, usuario=request.user).exists()


def _no_acceso():
    return redirect('proyectos:dashboard')


# ── Hub ───────────────────────────────────────────────────────────

@requiere('puede_ver_dashboard')
def hub(request, proyecto_id):
    proyecto = get_object_or_404(Proyecto, pk=proyecto_id)
    if not _acceso(request, proyecto):
        return _no_acceso()
    return render(request, 'reportes/hub.html', {'proyecto': proyecto})


# ── Helpers de fechas ─────────────────────────────────────────────

def _rango_fechas(request, default_dias=30):
    hoy = date.today()
    hasta_str = request.GET.get('hasta', '')
    desde_str = request.GET.get('desde', '')
    try:
        hasta = date.fromisoformat(hasta_str) if hasta_str else hoy
    except ValueError:
        hasta = hoy
    try:
        desde = date.fromisoformat(desde_str) if desde_str else (hasta - timedelta(days=default_dias))
    except ValueError:
        desde = hasta - timedelta(days=default_dias)
    return desde, hasta


def _mes_anio(request):
    hoy = date.today()
    try:
        anio = int(request.GET.get('anio') or hoy.year)
    except (ValueError, TypeError):
        anio = hoy.year
    try:
        mes = int(request.GET.get('mes') or hoy.month)
        if not 1 <= mes <= 12:
            mes = hoy.month
    except (ValueError, TypeError):
        mes = hoy.month
    return anio, mes


# ── 1. Consumo de insumos por período ────────────────────────────

def _query_consumo(proyecto, desde, hasta, tipo=None):
    qs = (DetalleSalida.objects
          .filter(salida__proyecto=proyecto,
                  salida__fecha__gte=desde,
                  salida__fecha__lte=hasta,
                  insumo__isnull=False))
    if tipo:
        qs = qs.filter(insumo__tipo=tipo)
    rows = (qs
            .values('insumo_id', 'insumo__codigo', 'insumo__descripcion',
                    'insumo__unidad', 'insumo__tipo', 'insumo__costo_unitario')
            .annotate(cantidad=Coalesce(Sum('cantidad'), Value(0, output_field=DFld())))
            .order_by('-cantidad'))
    items = []
    total_general = Decimal('0')
    for r in rows:
        cant = r['cantidad'] or Decimal('0')
        precio = r['insumo__costo_unitario'] or Decimal('0')
        subtotal = (Decimal(cant) * Decimal(precio))
        total_general += subtotal
        items.append({
            'codigo':    r['insumo__codigo'] or '',
            'descripcion': r['insumo__descripcion'] or '',
            'unidad':    r['insumo__unidad'] or '',
            'tipo':      r['insumo__tipo'] or '',
            'cantidad':  cant,
            'precio':    precio,
            'subtotal':  subtotal,
        })
    return items, total_general


@requiere('puede_ver_dashboard')
def insumos_consumo(request, proyecto_id):
    proyecto = get_object_or_404(Proyecto, pk=proyecto_id)
    if not _acceso(request, proyecto):
        return _no_acceso()
    desde, hasta = _rango_fechas(request)
    tipo = request.GET.get('tipo', '') or None
    items, total_general = _query_consumo(proyecto, desde, hasta, tipo)
    return render(request, 'reportes/insumos_consumo.html', {
        'proyecto':      proyecto,
        'desde':         desde,
        'hasta':         hasta,
        'tipo':          tipo or '',
        'items':         items,
        'total_general': total_general,
    })


def _excel_response(nombre_archivo):
    from openpyxl import Workbook
    wb = Workbook()
    ws = wb.active
    return wb, ws, nombre_archivo


def _flush_wb(wb, nombre_archivo):
    from io import BytesIO
    buf = BytesIO()
    wb.save(buf)
    buf.seek(0)
    resp = HttpResponse(
        buf.read(),
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    resp['Content-Disposition'] = f'attachment; filename="{nombre_archivo}"'
    return resp


@requiere('puede_ver_dashboard')
def insumos_consumo_excel(request, proyecto_id):
    proyecto = get_object_or_404(Proyecto, pk=proyecto_id)
    if not _acceso(request, proyecto):
        return _no_acceso()
    desde, hasta = _rango_fechas(request)
    tipo = request.GET.get('tipo', '') or None
    items, total_general = _query_consumo(proyecto, desde, hasta, tipo)

    from openpyxl.styles import Font, Alignment, PatternFill
    nombre = f'consumo_insumos_{proyecto.codigo}_{desde}_{hasta}.xlsx'
    wb, ws, _ = _excel_response(nombre)
    ws.title = 'Consumo de Insumos'
    ws['A1'] = f'Consumo de Insumos — {proyecto.codigo}'
    ws['A1'].font = Font(bold=True, size=14)
    ws['A2'] = f'Período: {desde.strftime("%d/%m/%Y")} al {hasta.strftime("%d/%m/%Y")}'
    if tipo:
        ws['A3'] = f'Tipo: {tipo}'

    row = 5
    headers = ['Código', 'Descripción', 'Tipo', 'Unidad', 'Cantidad', 'Costo Unit.', 'Subtotal (S/)']
    for col, h in enumerate(headers, 1):
        c = ws.cell(row=row, column=col, value=h)
        c.font = Font(bold=True, color='FFFFFF')
        c.fill = PatternFill('solid', fgColor='1D4ED8')
        c.alignment = Alignment(horizontal='center', vertical='center')
    row += 1
    for it in items:
        ws.cell(row=row, column=1, value=it['codigo'])
        ws.cell(row=row, column=2, value=it['descripcion'])
        ws.cell(row=row, column=3, value=it['tipo'])
        ws.cell(row=row, column=4, value=it['unidad'])
        ws.cell(row=row, column=5, value=float(it['cantidad'])).number_format = '#,##0.0000'
        ws.cell(row=row, column=6, value=float(it['precio'])).number_format = '#,##0.0000'
        ws.cell(row=row, column=7, value=float(it['subtotal'])).number_format = '#,##0.00'
        row += 1
    # Total general
    ws.cell(row=row, column=6, value='TOTAL').font = Font(bold=True)
    c = ws.cell(row=row, column=7, value=float(total_general))
    c.font = Font(bold=True)
    c.number_format = '#,##0.00'
    from openpyxl.utils import get_column_letter
    for col, width in enumerate([14, 50, 14, 10, 14, 14, 16], 1):
        ws.column_dimensions[get_column_letter(col)].width = width
    return _flush_wb(wb, nombre)


# ── 2. Ejecutado vs presupuestado por partida ───────────────────

def _query_avance(proyecto):
    try:
        presupuesto = proyecto.presupuesto
    except Presupuesto.DoesNotExist:
        return [], Decimal('0'), Decimal('0')
    partidas_lvl1 = list(presupuesto.partidas.filter(nivel=1).order_by('orden', 'codigo'))

    def _descendientes(p):
        ids = {p.pk}
        pendientes = [p.pk]
        while pendientes:
            x = pendientes.pop()
            hijos = list(presupuesto.partidas.filter(padre_id=x).values_list('pk', flat=True))
            for h in hijos:
                if h not in ids:
                    ids.add(h)
                    pendientes.append(h)
        return ids

    rows = []
    gran_presup = Decimal('0')
    gran_ejec = Decimal('0')
    for p in partidas_lvl1:
        desc_ids = _descendientes(p)
        ins_qs = presupuesto.insumos.filter(
            recursopartida__partida_id__in=desc_ids
        ).distinct().annotate(
            aprob=Coalesce(
                Sum('detallerequerimiento__cantidad_requerida',
                    filter=Q(detallerequerimiento__requerimiento__estado__in=[
                        'APROBADO', 'COTIZADO', 'ATENDIDO', 'PARCIAL',
                    ])),
                Value(0, output_field=DFld()),
            )
        )
        tot = Decimal('0'); eje = Decimal('0')
        for i in ins_qs:
            precio = i.costo_unitario or Decimal('0')
            cupo   = i.cantidad_total or Decimal('0')
            tot += Decimal(cupo) * precio
            eje += Decimal(i.aprob or 0) * precio
        pct = round(float(eje * 100 / tot), 2) if tot > 0 else 0
        saldo = tot - eje
        rows.append({
            'codigo': p.codigo,
            'nombre': p.nombre,
            'presupuestado': tot,
            'ejecutado':     eje,
            'saldo':         saldo,
            'pct':           pct,
        })
        gran_presup += tot
        gran_ejec += eje
    return rows, gran_presup, gran_ejec


@requiere('puede_ver_dashboard')
def avance_partidas(request, proyecto_id):
    proyecto = get_object_or_404(Proyecto, pk=proyecto_id)
    if not _acceso(request, proyecto):
        return _no_acceso()
    rows, gran_presup, gran_ejec = _query_avance(proyecto)
    gran_saldo = gran_presup - gran_ejec
    gran_pct = round(float(gran_ejec * 100 / gran_presup), 2) if gran_presup > 0 else 0
    return render(request, 'reportes/avance_partidas.html', {
        'proyecto':    proyecto,
        'items':       rows,
        'gran_presup': gran_presup,
        'gran_ejec':   gran_ejec,
        'gran_saldo':  gran_saldo,
        'gran_pct':    gran_pct,
    })


@requiere('puede_ver_dashboard')
def avance_partidas_excel(request, proyecto_id):
    proyecto = get_object_or_404(Proyecto, pk=proyecto_id)
    if not _acceso(request, proyecto):
        return _no_acceso()
    rows, gran_presup, gran_ejec = _query_avance(proyecto)

    from openpyxl.styles import Font, Alignment, PatternFill
    nombre = f'ejecutado_vs_presupuestado_{proyecto.codigo}.xlsx'
    wb, ws, _ = _excel_response(nombre)
    ws.title = 'Avance por partida'
    ws['A1'] = f'Ejecutado vs Presupuestado — {proyecto.codigo}'
    ws['A1'].font = Font(bold=True, size=14)
    ws['A2'] = f'Al {date.today().strftime("%d/%m/%Y")}'

    row = 4
    headers = ['Código', 'Partida', 'Presupuestado (S/)', 'Ejecutado (S/)', 'Saldo (S/)', '% Avance']
    for col, h in enumerate(headers, 1):
        c = ws.cell(row=row, column=col, value=h)
        c.font = Font(bold=True, color='FFFFFF')
        c.fill = PatternFill('solid', fgColor='1D4ED8')
        c.alignment = Alignment(horizontal='center', vertical='center')
    row += 1
    for it in rows:
        ws.cell(row=row, column=1, value=it['codigo'])
        ws.cell(row=row, column=2, value=it['nombre'])
        ws.cell(row=row, column=3, value=float(it['presupuestado'])).number_format = '#,##0.00'
        ws.cell(row=row, column=4, value=float(it['ejecutado'])).number_format = '#,##0.00'
        ws.cell(row=row, column=5, value=float(it['saldo'])).number_format = '#,##0.00'
        ws.cell(row=row, column=6, value=it['pct'] / 100).number_format = '0.00%'
        row += 1
    gran_saldo = gran_presup - gran_ejec
    gran_pct = (float(gran_ejec) / float(gran_presup)) if gran_presup else 0
    ws.cell(row=row, column=2, value='TOTAL').font = Font(bold=True)
    for col, val, fmt in [(3, float(gran_presup), '#,##0.00'),
                          (4, float(gran_ejec), '#,##0.00'),
                          (5, float(gran_saldo), '#,##0.00'),
                          (6, gran_pct, '0.00%')]:
        c = ws.cell(row=row, column=col, value=val)
        c.font = Font(bold=True)
        c.number_format = fmt
    from openpyxl.utils import get_column_letter
    for col, width in enumerate([12, 50, 20, 20, 20, 12], 1):
        ws.column_dimensions[get_column_letter(col)].width = width
    return _flush_wb(wb, nombre)


# ── 3. Asistencia mensual ───────────────────────────────────────

ASIST_LABELS = {
    'P': 'P', 'F': 'F', 'T': 'T', 'PM': 'PM', 'D': 'D', 'FE': 'FE', '': '',
}


def _query_asistencia_mes(proyecto, anio, mes, cuadrilla_id=None):
    from django.db import ProgrammingError, OperationalError
    dias_mes = monthrange(anio, mes)[1]
    desde = date(anio, mes, 1)
    hasta = date(anio, mes, dias_mes)

    try:
        qs_trab = Trabajador.objects.filter(proyecto=proyecto, activo=True)
        if cuadrilla_id:
            qs_trab = qs_trab.filter(membresias__cuadrilla_id=cuadrilla_id).distinct()
        trabajadores = list(qs_trab.order_by('apellidos', 'nombres'))
    except (ProgrammingError, OperationalError):
        # Schema drift (p. ej., migraciones pendientes en local) — degradamos.
        return [], dias_mes, desde, hasta

    # Diccionario {trab_id: {dia: estado}}
    mapa = {}
    try:
        qs_a = Asistencia.objects.filter(
            trabajador__proyecto=proyecto,
            fecha__gte=desde, fecha__lte=hasta,
        )
        if cuadrilla_id:
            qs_a = qs_a.filter(trabajador__membresias__cuadrilla_id=cuadrilla_id)
        for a in qs_a:
            mapa.setdefault(a.trabajador_id, {})[a.fecha.day] = a.estado
    except (ProgrammingError, OperationalError):
        pass

    filas = []
    for t in trabajadores:
        dias_map = mapa.get(t.pk, {})
        fila = {'trabajador': t, 'dias': [], 'p': 0, 'f': 0, 't': 0, 'otros': 0}
        for d in range(1, dias_mes + 1):
            estado = dias_map.get(d, '')
            fila['dias'].append({'num': d, 'estado': estado})
            if estado == 'P':
                fila['p'] += 1
            elif estado == 'F':
                fila['f'] += 1
            elif estado == 'T':
                fila['t'] += 1
            elif estado:
                fila['otros'] += 1
        filas.append(fila)

    return filas, dias_mes, desde, hasta


@requiere('puede_ver_dashboard')
def asistencia_mes(request, proyecto_id):
    proyecto = get_object_or_404(Proyecto, pk=proyecto_id)
    if not _acceso(request, proyecto):
        return _no_acceso()
    from apps.maquinaria.models import Cuadrilla
    anio, mes = _mes_anio(request)
    try:
        cuadrilla_id = int(request.GET.get('cuadrilla') or 0) or None
    except ValueError:
        cuadrilla_id = None
    from django.db import ProgrammingError, OperationalError
    filas, dias_mes, desde, hasta = _query_asistencia_mes(proyecto, anio, mes, cuadrilla_id)
    try:
        cuadrillas = list(Cuadrilla.objects.filter(proyecto=proyecto, activo=True).order_by('nombre'))
    except (ProgrammingError, OperationalError):
        cuadrillas = []
    meses_label = ['Ene','Feb','Mar','Abr','May','Jun','Jul','Ago','Sep','Oct','Nov','Dic']
    return render(request, 'reportes/asistencia_mes.html', {
        'proyecto':    proyecto,
        'anio':        anio,
        'mes':         mes,
        'mes_label':   meses_label[mes - 1],
        'dias':        list(range(1, dias_mes + 1)),
        'filas':       filas,
        'cuadrillas':  cuadrillas,
        'cuadrilla_id': cuadrilla_id,
        'anios':       list(range(date.today().year - 3, date.today().year + 2)),
    })


@requiere('puede_ver_dashboard')
def asistencia_mes_excel(request, proyecto_id):
    proyecto = get_object_or_404(Proyecto, pk=proyecto_id)
    if not _acceso(request, proyecto):
        return _no_acceso()
    anio, mes = _mes_anio(request)
    try:
        cuadrilla_id = int(request.GET.get('cuadrilla') or 0) or None
    except ValueError:
        cuadrilla_id = None
    filas, dias_mes, desde, hasta = _query_asistencia_mes(proyecto, anio, mes, cuadrilla_id)

    from openpyxl.styles import Font, Alignment, PatternFill
    nombre = f'asistencia_{proyecto.codigo}_{anio}-{mes:02d}.xlsx'
    wb, ws, _ = _excel_response(nombre)
    ws.title = f'Asistencia {anio}-{mes:02d}'
    ws['A1'] = f'Asistencia mensual — {proyecto.codigo}'
    ws['A1'].font = Font(bold=True, size=14)
    ws['A2'] = f'{anio}-{mes:02d}  ({desde.strftime("%d/%m/%Y")} al {hasta.strftime("%d/%m/%Y")})'

    row = 4
    ws.cell(row=row, column=1, value='Trabajador').font = Font(bold=True, color='FFFFFF')
    ws.cell(row=row, column=1).fill = PatternFill('solid', fgColor='1D4ED8')
    for d in range(1, dias_mes + 1):
        c = ws.cell(row=row, column=1 + d, value=d)
        c.font = Font(bold=True, color='FFFFFF')
        c.fill = PatternFill('solid', fgColor='1D4ED8')
        c.alignment = Alignment(horizontal='center')
    for i, label in enumerate(['P', 'F', 'T', 'Otros'], start=dias_mes + 2):
        c = ws.cell(row=row, column=i, value=label)
        c.font = Font(bold=True, color='FFFFFF')
        c.fill = PatternFill('solid', fgColor='059669' if label == 'P' else '6B7280')
        c.alignment = Alignment(horizontal='center')
    row += 1
    for fila in filas:
        t = fila['trabajador']
        ws.cell(row=row, column=1, value=f'{t.apellidos}, {t.nombres}')
        for dnum, d in enumerate(fila['dias'], 1):
            c = ws.cell(row=row, column=1 + dnum, value=d['estado'] or '')
            c.alignment = Alignment(horizontal='center')
        ws.cell(row=row, column=dias_mes + 2, value=fila['p']).alignment = Alignment(horizontal='center')
        ws.cell(row=row, column=dias_mes + 3, value=fila['f']).alignment = Alignment(horizontal='center')
        ws.cell(row=row, column=dias_mes + 4, value=fila['t']).alignment = Alignment(horizontal='center')
        ws.cell(row=row, column=dias_mes + 5, value=fila['otros']).alignment = Alignment(horizontal='center')
        row += 1

    from openpyxl.utils import get_column_letter
    ws.column_dimensions['A'].width = 34
    for d in range(1, dias_mes + 1):
        ws.column_dimensions[get_column_letter(1 + d)].width = 4
    for i in range(4):
        ws.column_dimensions[get_column_letter(dias_mes + 2 + i)].width = 7
    return _flush_wb(wb, nombre)


# ── 4. Maquinaria por período ───────────────────────────────────

def _query_maquinaria(proyecto, desde, hasta, maq_id=None):
    qs = RegistroMaquinaria.objects.filter(
        proyecto=proyecto, fecha__gte=desde, fecha__lte=hasta,
    )
    if maq_id:
        qs = qs.filter(maquinaria_id=maq_id)
    rows = (qs.values('maquinaria_id', 'maquinaria__codigo', 'maquinaria__nombre',
                      'maquinaria__marca', 'maquinaria__modelo', 'maquinaria__placa',
                      'maquinaria__costo_hora')
            .annotate(
                horas_total=Coalesce(Sum('horas'), Value(0, output_field=DFld())),
                comb_total=Coalesce(Sum('combustible'), Value(0, output_field=DFld())),
                costo_total=Coalesce(Sum('costo'), Value(0, output_field=DFld())),
                partes=Coalesce(Sum(Value(1, output_field=DFld())), Value(0, output_field=DFld())),
            )
            .order_by('-horas_total'))

    items = []
    total_horas = Decimal('0')
    total_comb  = Decimal('0')
    total_costo = Decimal('0')
    for r in rows:
        horas = r['horas_total'] or Decimal('0')
        comb  = r['comb_total'] or Decimal('0')
        costo = r['costo_total'] or Decimal('0')
        items.append({
            'codigo':     r['maquinaria__codigo'] or '',
            'nombre':     r['maquinaria__nombre'] or '',
            'marca':      r['maquinaria__marca'] or '',
            'modelo':     r['maquinaria__modelo'] or '',
            'placa':      r['maquinaria__placa'] or '',
            'costo_hora': r['maquinaria__costo_hora'] or Decimal('0'),
            'horas':      horas,
            'combustible': comb,
            'costo':      costo,
            'partes':     r['partes'] or 0,
        })
        total_horas += horas
        total_comb  += comb
        total_costo += costo
    return items, total_horas, total_comb, total_costo


@requiere('puede_ver_dashboard')
def maquinaria_periodo(request, proyecto_id):
    proyecto = get_object_or_404(Proyecto, pk=proyecto_id)
    if not _acceso(request, proyecto):
        return _no_acceso()
    from apps.maquinaria.models import Maquinaria
    desde, hasta = _rango_fechas(request)
    try:
        maq_id = int(request.GET.get('maquinaria') or 0) or None
    except ValueError:
        maq_id = None
    items, total_horas, total_comb, total_costo = _query_maquinaria(proyecto, desde, hasta, maq_id)
    # Máquinas que tuvieron movimiento en este proyecto (para el selector)
    maq_ids = list(RegistroMaquinaria.objects.filter(proyecto=proyecto)
                   .values_list('maquinaria_id', flat=True).distinct())
    maquinas = Maquinaria.objects.filter(pk__in=maq_ids).order_by('codigo')
    return render(request, 'reportes/maquinaria_periodo.html', {
        'proyecto':    proyecto,
        'desde':       desde,
        'hasta':       hasta,
        'items':       items,
        'total_horas': total_horas,
        'total_comb':  total_comb,
        'total_costo': total_costo,
        'maquinas':    maquinas,
        'maq_id':      maq_id,
    })


@requiere('puede_ver_dashboard')
def maquinaria_periodo_excel(request, proyecto_id):
    proyecto = get_object_or_404(Proyecto, pk=proyecto_id)
    if not _acceso(request, proyecto):
        return _no_acceso()
    desde, hasta = _rango_fechas(request)
    try:
        maq_id = int(request.GET.get('maquinaria') or 0) or None
    except ValueError:
        maq_id = None
    items, total_horas, total_comb, total_costo = _query_maquinaria(proyecto, desde, hasta, maq_id)

    from openpyxl.styles import Font, Alignment, PatternFill
    nombre = f'maquinaria_{proyecto.codigo}_{desde}_{hasta}.xlsx'
    wb, ws, _ = _excel_response(nombre)
    ws.title = 'Maquinaria'
    ws['A1'] = f'Maquinaria trabajada — {proyecto.codigo}'
    ws['A1'].font = Font(bold=True, size=14)
    ws['A2'] = f'Período: {desde.strftime("%d/%m/%Y")} al {hasta.strftime("%d/%m/%Y")}'

    row = 4
    headers = ['Código', 'Máquina', 'Marca/Modelo', 'Placa', 'Partes', 'Horas', 'Combustible (gal)', 'Costo total (S/)']
    for col, h in enumerate(headers, 1):
        c = ws.cell(row=row, column=col, value=h)
        c.font = Font(bold=True, color='FFFFFF')
        c.fill = PatternFill('solid', fgColor='1D4ED8')
        c.alignment = Alignment(horizontal='center', vertical='center')
    row += 1
    for it in items:
        ws.cell(row=row, column=1, value=it['codigo'])
        ws.cell(row=row, column=2, value=it['nombre'])
        ws.cell(row=row, column=3, value=f"{it['marca']} {it['modelo']}".strip())
        ws.cell(row=row, column=4, value=it['placa'])
        ws.cell(row=row, column=5, value=it['partes']).alignment = Alignment(horizontal='center')
        ws.cell(row=row, column=6, value=float(it['horas'])).number_format = '#,##0.00'
        ws.cell(row=row, column=7, value=float(it['combustible'])).number_format = '#,##0.00'
        ws.cell(row=row, column=8, value=float(it['costo'])).number_format = '#,##0.00'
        row += 1
    ws.cell(row=row, column=5, value='TOTAL').font = Font(bold=True)
    for col, val in [(6, float(total_horas)), (7, float(total_comb)), (8, float(total_costo))]:
        c = ws.cell(row=row, column=col, value=val)
        c.font = Font(bold=True)
        c.number_format = '#,##0.00'
    from openpyxl.utils import get_column_letter
    for col, width in enumerate([14, 30, 24, 12, 8, 12, 16, 18], 1):
        ws.column_dimensions[get_column_letter(col)].width = width
    return _flush_wb(wb, nombre)
