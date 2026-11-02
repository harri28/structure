import json
from django.shortcuts import render, get_object_or_404, redirect
from django.urls import reverse
from django.contrib import messages
from django.conf import settings
from django.db.models import Sum, Count, Min, Max, Q
from django.http import JsonResponse
from django.views.decorators.http import require_POST

from apps.proyectos.models import Proyecto
from .models import (
    TipoPersonal, Maquinaria, Cuadrilla, IntegranteCuadrilla,
    RegistroDiario, RegistroMaquinaria, Liquidacion,
    Trabajador, DocumentoTrabajador, Asistencia,
)
from .forms import (
    TipoPersonalForm, MaquinariaForm, CuadrillaForm, AgregarIntegranteForm,
    RegistroMaquinariaForm, ParteForm,
    TrabajadorForm, DocumentoTrabajadorForm,
)
from config.permisos import requiere, proyecto_visible


# ── Dashboard ─────────────────────────────────────────────────────────

@requiere('puede_ver_maquinaria', 'puede_gestionar_maquinaria')
@proyecto_visible
def dashboard(request, proyecto_id):
    proyecto = get_object_or_404(Proyecto, pk=proyecto_id)
    registros_cuadrilla  = RegistroDiario.objects.filter(proyecto=proyecto).select_related('partida')
    registros_maquinaria = RegistroMaquinaria.objects.filter(proyecto=proyecto).select_related('maquinaria', 'partida')

    total_hh = sum(r.horas_hombre() for r in registros_cuadrilla.prefetch_related('cuadrilla__integrantes'))
    total_hm = registros_maquinaria.aggregate(t=Sum('horas'))['t'] or 0

    return render(request, 'maquinaria/dashboard.html', {
        'proyecto':          proyecto,
        'total_hh':          total_hh,
        'total_hm':          total_hm,
        'registros_recientes': RegistroDiario.objects.filter(proyecto=proyecto).select_related('cuadrilla', 'partida')[:8],
        'maq_recientes':     registros_maquinaria[:8],
    })


# ── Tipos de Personal ─────────────────────────────────────────────────

@requiere('puede_ver_maquinaria', 'puede_gestionar_maquinaria')
def tipo_personal_lista(request):
    tipos = TipoPersonal.objects.all()
    return render(request, 'maquinaria/tipo_personal_lista.html', {'tipos': tipos})


@requiere('puede_gestionar_maquinaria')
def tipo_personal_crear(request):
    form = TipoPersonalForm(request.POST or None)
    if form.is_valid():
        form.save()
        messages.success(request, 'Tipo de personal creado.')
        return redirect('maquinaria:tipo_personal_lista')
    return render(request, 'maquinaria/tipo_personal_form.html', {'form': form, 'titulo': 'Nuevo Tipo de Personal'})


@requiere('puede_gestionar_maquinaria')
def tipo_personal_editar(request, pk):
    obj  = get_object_or_404(TipoPersonal, pk=pk)
    form = TipoPersonalForm(request.POST or None, instance=obj)
    if form.is_valid():
        form.save()
        messages.success(request, 'Tipo de personal actualizado.')
        return redirect('maquinaria:tipo_personal_lista')
    return render(request, 'maquinaria/tipo_personal_form.html', {'form': form, 'titulo': 'Editar Tipo de Personal', 'obj': obj})


@requiere('puede_gestionar_maquinaria')
def tipo_personal_eliminar(request, pk):
    obj = get_object_or_404(TipoPersonal, pk=pk)
    if request.method == 'POST':
        obj.delete()
        messages.success(request, 'Tipo de personal eliminado.')
        return redirect('maquinaria:tipo_personal_lista')
    return render(request, 'maquinaria/confirmar_eliminar.html', {'obj': obj, 'tipo': 'Tipo de Personal',
        'cancel_url': 'maquinaria:tipo_personal_lista', 'cancel_args': []})


@requiere('puede_gestionar_maquinaria')
@proyecto_visible
@require_POST
def cargo_crear_rapido(request, proyecto_id):
    """Crea un TipoPersonal desde el modal de la pestaña Cargos y vuelve a la lista."""
    codigo = (request.POST.get('codigo') or '').strip().upper()[:20]
    nombre = (request.POST.get('nombre') or '').strip()[:100]
    if not codigo or not nombre:
        messages.error(request, 'Código y nombre son obligatorios.')
    elif TipoPersonal.objects.filter(codigo=codigo).exists():
        messages.error(request, f'Ya existe un cargo con código "{codigo}".')
    else:
        TipoPersonal.objects.create(codigo=codigo, nombre=nombre, costo_hora=0, activo=True)
        messages.success(request, f'Cargo "{nombre}" creado.')
    return redirect(f"{reverse('maquinaria:registro_lista', args=[proyecto_id])}?tab=cargos")


@requiere('puede_gestionar_maquinaria')
@proyecto_visible
@require_POST
def cargo_eliminar_rapido(request, proyecto_id, pk):
    """Elimina un TipoPersonal si no tiene trabajadores asignados; vuelve a la lista."""
    tp = get_object_or_404(TipoPersonal, pk=pk)
    if tp.trabajadores.exists():
        messages.error(request, f'No se puede eliminar "{tp.nombre}": hay trabajadores asignados a este cargo.')
    else:
        nombre = tp.nombre
        tp.delete()
        messages.success(request, f'Cargo "{nombre}" eliminado.')
    return redirect(f"{reverse('maquinaria:registro_lista', args=[proyecto_id])}?tab=cargos")


# ── Maquinaria ────────────────────────────────────────────────────────

def _siguiente_codigo_maq():
    existentes = Maquinaria.objects.filter(codigo__startswith='M').values_list('codigo', flat=True)
    nums = []
    for c in existentes:
        try:
            nums.append(int(c[1:]))
        except (ValueError, IndexError):
            pass
    return f'M{max(nums, default=0) + 1:03d}'


def _volver_a_maquinaria(request, maquinaria_pk=None):
    """Redirige al detalle de la máquina (si hay pk + proyecto activo) o al principal."""
    pid = request.session.get('proyecto_id')
    if pid and maquinaria_pk:
        return redirect('maquinaria:maq_detalle_maquinaria', proyecto_id=pid, maq_pk=maquinaria_pk)
    if pid:
        return redirect('maquinaria:maq_principal', proyecto_id=pid)
    return redirect('proyectos:dashboard')


def _back_ctx(request, obj=None):
    """URL + etiqueta para el back-link del form de maquinaria."""
    from django.urls import reverse
    pid = request.session.get('proyecto_id')
    if not pid:
        return {'back_url': None, 'back_label': None}
    if obj and obj.pk:
        return {
            'back_url':   reverse('maquinaria:maq_detalle_maquinaria', args=[pid, obj.pk]),
            'back_label': obj.nombre,
        }
    return {
        'back_url':   reverse('maquinaria:maq_principal', args=[pid]),
        'back_label': 'Maquinaria',
    }


@requiere('puede_gestionar_maquinaria')
def maquinaria_crear(request):
    initial = {'codigo': _siguiente_codigo_maq()}
    form    = MaquinariaForm(request.POST or None, initial=initial)
    if form.is_valid():
        obj = form.save()
        messages.success(request, 'Equipo/maquinaria creado.')
        return _volver_a_maquinaria(request, maquinaria_pk=obj.pk)
    ctx = {'form': form, 'titulo': 'Nueva Maquinaria', **_back_ctx(request)}
    return render(request, 'maquinaria/maquinaria_form.html', ctx)


@requiere('puede_gestionar_maquinaria')
def maquinaria_editar(request, pk):
    obj  = get_object_or_404(Maquinaria, pk=pk)
    form = MaquinariaForm(request.POST or None, instance=obj)
    if form.is_valid():
        form.save()
        messages.success(request, 'Maquinaria actualizada.')
        return _volver_a_maquinaria(request, maquinaria_pk=obj.pk)
    ctx = {'form': form, 'titulo': 'Editar Maquinaria', 'obj': obj, **_back_ctx(request, obj)}
    return render(request, 'maquinaria/maquinaria_form.html', ctx)


@requiere('puede_gestionar_maquinaria')
def maquinaria_eliminar(request, pk):
    obj = get_object_or_404(Maquinaria, pk=pk)
    if request.method == 'POST':
        obj.delete()
        messages.success(request, 'Maquinaria eliminada.')
        return _volver_a_maquinaria(request)
    pid = request.session.get('proyecto_id')
    return render(request, 'maquinaria/confirmar_eliminar.html', {'obj': obj, 'tipo': 'Maquinaria',
        'cancel_url': 'maquinaria:maq_principal' if pid else 'proyectos:dashboard',
        'cancel_args': [pid] if pid else []})


# ── Cuadrillas (Frentes de trabajo) ───────────────────────────────────

@requiere('puede_gestionar_maquinaria')
@proyecto_visible
def cuadrilla_crear(request, proyecto_id):
    proyecto = get_object_or_404(Proyecto, pk=proyecto_id)
    form     = CuadrillaForm(proyecto=proyecto, data=request.POST or None)
    if form.is_valid():
        cuadrilla          = form.save(commit=False)
        cuadrilla.proyecto = proyecto
        cuadrilla.save()
        messages.success(request, f'Cuadrilla "{cuadrilla.nombre}" creada.')
        return redirect(f"{reverse('maquinaria:registro_lista', args=[proyecto_id])}?tab=cuadrilla")
    # Fallback para GET o para POST inválido fuera del modal
    return render(request, 'maquinaria/cuadrilla_form.html', {
        'form': form, 'proyecto': proyecto, 'titulo': 'Nueva cuadrilla / frente',
    })


@requiere('puede_ver_maquinaria', 'puede_gestionar_maquinaria')
def cuadrilla_detalle(request, pk):
    cuadrilla = get_object_or_404(
        Cuadrilla.objects.select_related('proyecto', 'capataz'),
        pk=pk,
    )
    integrantes = (
        cuadrilla.integrantes
        .select_related('trabajador', 'trabajador__tipo_personal')
    )
    form = AgregarIntegranteForm(cuadrilla=cuadrilla)
    return render(request, 'maquinaria/cuadrilla_detalle.html', {
        'cuadrilla':   cuadrilla,
        'proyecto':    cuadrilla.proyecto,
        'integrantes': integrantes,
        'form':        form,
    })


@requiere('puede_gestionar_maquinaria')
def cuadrilla_editar(request, pk):
    obj  = get_object_or_404(Cuadrilla.objects.select_related('proyecto'), pk=pk)
    form = CuadrillaForm(proyecto=obj.proyecto, data=request.POST or None, instance=obj)
    if form.is_valid():
        form.save()
        messages.success(request, 'Cuadrilla actualizada.')
        return redirect('maquinaria:cuadrilla_detalle', pk=pk)
    return render(request, 'maquinaria/cuadrilla_form.html', {
        'form': form, 'proyecto': obj.proyecto, 'titulo': 'Editar cuadrilla', 'obj': obj,
    })


@requiere('puede_gestionar_maquinaria')
def cuadrilla_eliminar(request, pk):
    obj = get_object_or_404(Cuadrilla, pk=pk)
    proyecto_id = obj.proyecto_id
    if request.method == 'POST':
        nombre = obj.nombre
        obj.delete()
        messages.success(request, f'Cuadrilla "{nombre}" eliminada.')
    return redirect(f"{reverse('maquinaria:registro_lista', args=[proyecto_id])}?tab=cuadrilla")


@requiere('puede_gestionar_maquinaria')
def integrante_agregar(request, pk):
    cuadrilla = get_object_or_404(Cuadrilla, pk=pk)
    if request.method == 'POST':
        form = AgregarIntegranteForm(cuadrilla, request.POST)
        if form.is_valid():
            IntegranteCuadrilla.objects.create(
                cuadrilla=cuadrilla,
                trabajador=form.cleaned_data['trabajador'],
            )
            messages.success(request, 'Personal agregado a la cuadrilla.')
        else:
            messages.error(request, 'Error: ' + str(form.errors))
    return redirect('maquinaria:cuadrilla_detalle', pk=pk)


@requiere('puede_gestionar_maquinaria')
def integrante_eliminar(request, pk):
    integrante   = get_object_or_404(IntegranteCuadrilla, pk=pk)
    cuadrilla_pk = integrante.cuadrilla_id
    if request.method == 'POST':
        integrante.delete()
        messages.success(request, 'Personal retirado de la cuadrilla.')
    return redirect('maquinaria:cuadrilla_detalle', pk=cuadrilla_pk)


# ── Personal de Obra (Trabajadores) ────────────────────────────────────

@requiere('puede_gestionar_maquinaria')
@proyecto_visible
def trabajador_crear(request, proyecto_id):
    proyecto = get_object_or_404(Proyecto, pk=proyecto_id)
    form = TrabajadorForm(request.POST or None, request.FILES or None)
    if form.is_valid():
        trabajador = form.save(commit=False)
        trabajador.proyecto = proyecto
        trabajador.save()
        messages.success(request, f'{trabajador.nombre_completo()} registrado correctamente.')
        return redirect(f"{reverse('maquinaria:registro_lista', args=[proyecto_id])}?tab=personal")
    return render(request, 'maquinaria/trabajador_form.html', {
        'form': form, 'proyecto': proyecto, 'titulo': 'Nuevo personal',
    })


@requiere('puede_ver_maquinaria', 'puede_gestionar_maquinaria')
def trabajador_detalle(request, pk):
    trabajador = get_object_or_404(Trabajador, pk=pk)
    doc_form = DocumentoTrabajadorForm()
    return render(request, 'maquinaria/trabajador_detalle.html', {
        'trabajador': trabajador,
        'proyecto':   trabajador.proyecto,
        'documentos': trabajador.documentos.all(),
        'doc_form':   doc_form,
    })


@requiere('puede_gestionar_maquinaria')
def trabajador_editar(request, pk):
    trabajador = get_object_or_404(Trabajador, pk=pk)
    form = TrabajadorForm(request.POST or None, request.FILES or None, instance=trabajador)
    if form.is_valid():
        form.save()
        messages.success(request, 'Datos actualizados.')
        return redirect(f"{reverse('maquinaria:registro_lista', args=[trabajador.proyecto_id])}?tab=personal")
    return render(request, 'maquinaria/trabajador_form.html', {
        'form': form, 'proyecto': trabajador.proyecto, 'titulo': 'Editar personal', 'obj': trabajador,
    })


@requiere('puede_gestionar_maquinaria')
def trabajador_eliminar(request, pk):
    """Legacy — Conservada por compatibilidad. El flujo nuevo usa dar de baja."""
    obj = get_object_or_404(Trabajador, pk=pk)
    proyecto_id = obj.proyecto_id
    if request.method == 'POST':
        nombre = obj.nombre_completo()
        obj.delete()
        messages.success(request, f'{nombre} eliminado.')
    return redirect(f"{reverse('maquinaria:registro_lista', args=[proyecto_id])}?tab=personal")


@requiere('puede_gestionar_maquinaria')
def trabajador_dar_baja(request, pk):
    obj = get_object_or_404(Trabajador, pk=pk)
    proyecto_id = obj.proyecto_id
    if request.method == 'POST':
        obj.activo = False
        obj.save(update_fields=['activo'])
        messages.success(request, f'{obj.nombre_completo()} dado de baja.')
    return redirect(f"{reverse('maquinaria:registro_lista', args=[proyecto_id])}?tab=personal")


@requiere('puede_gestionar_maquinaria')
def trabajador_reactivar(request, pk):
    obj = get_object_or_404(Trabajador, pk=pk)
    proyecto_id = obj.proyecto_id
    if request.method == 'POST':
        obj.activo = True
        obj.save(update_fields=['activo'])
        messages.success(request, f'{obj.nombre_completo()} reactivado.')
    return redirect(f"{reverse('maquinaria:registro_lista', args=[proyecto_id])}?tab=inactivos")


@requiere('puede_gestionar_maquinaria')
def documento_agregar(request, pk):
    trabajador = get_object_or_404(Trabajador, pk=pk)
    if request.method == 'POST':
        form = DocumentoTrabajadorForm(request.POST, request.FILES)
        if form.is_valid():
            documento = form.save(commit=False)
            documento.trabajador = trabajador
            documento.save()
            messages.success(request, 'Documento agregado.')
        else:
            messages.error(request, 'Error: ' + str(form.errors))
    return redirect('maquinaria:trabajador_detalle', pk=pk)


@requiere('puede_gestionar_maquinaria')
def documento_eliminar(request, pk):
    documento = get_object_or_404(DocumentoTrabajador, pk=pk)
    trabajador_pk = documento.trabajador_id
    if request.method == 'POST':
        documento.delete()
        messages.success(request, 'Documento eliminado.')
    return redirect('maquinaria:trabajador_detalle', pk=trabajador_pk)


# ── Cuadrilla (Cuadrilla En desarrollo + Personal activo) ─────────────

def _rango_asistencia(periodo, inicio_str):
    """Devuelve (periodo_norm, inicio, fin, fechas[])."""
    from datetime import date, timedelta
    import calendar as _calendar
    hoy = date.today()
    try:
        inicio = date.fromisoformat(inicio_str) if inicio_str else hoy
    except (ValueError, TypeError):
        inicio = hoy

    if periodo == 'diario':
        fin = inicio
    elif periodo == 'quincenal':
        fin = inicio + timedelta(days=14)
    elif periodo == 'mensual':
        inicio = inicio.replace(day=1)
        _, ult = _calendar.monthrange(inicio.year, inicio.month)
        fin = inicio.replace(day=ult)
    else:
        periodo = 'semanal'
        inicio = inicio - timedelta(days=inicio.weekday())  # lunes
        fin = inicio + timedelta(days=6)

    fechas, d = [], inicio
    while d <= fin:
        fechas.append(d)
        d += timedelta(days=1)
    return periodo, inicio, fin, fechas


@requiere('puede_ver_maquinaria', 'puede_gestionar_maquinaria')
@proyecto_visible
def registro_lista(request, proyecto_id):
    proyecto     = get_object_or_404(Proyecto, pk=proyecto_id)
    trabajadores_all = (
        Trabajador.objects
        .filter(proyecto=proyecto)
        .select_related('tipo_personal')
    )
    trabajadores            = trabajadores_all.filter(activo=True)
    trabajadores_inactivos  = trabajadores_all.filter(activo=False).order_by('apellidos', 'nombres')
    cuadrillas = (
        Cuadrilla.objects
        .filter(proyecto=proyecto)
        .select_related('capataz')
        .annotate(n_integrantes=Count('integrantes'))
    )

    # ── Resumen asistencia del mes actual (por trabajador activo) ─────────
    from datetime import date as _date
    hoy = _date.today()
    mes_inicio = hoy.replace(day=1)
    asistencia_qs = Asistencia.objects.filter(
        trabajador__proyecto=proyecto,
        fecha__gte=mes_inicio,
        fecha__lte=hoy,
    )
    conteo_mes = {}
    for trab_id, estado in asistencia_qs.values_list('trabajador_id', 'estado'):
        entry = conteo_mes.setdefault(trab_id, {'asistidas': 0, 'faltas': 0})
        if estado == Asistencia.PRESENTE:
            entry['asistidas'] += 1
        elif estado == Asistencia.FALTA:
            entry['faltas'] += 1

    # Primera cuadrilla asociada por trabajador (si pertenece a varias, se muestra la primera)
    cuadrilla_por_trab = {}
    for ic in (IntegranteCuadrilla.objects
               .filter(cuadrilla__proyecto=proyecto)
               .select_related('cuadrilla')):
        cuadrilla_por_trab.setdefault(ic.trabajador_id, ic.cuadrilla.nombre)

    # Enriquecemos cada trabajador activo con atributos ad-hoc para el template
    trabajadores = list(trabajadores.order_by('apellidos', 'nombres'))
    for t in trabajadores:
        datos = conteo_mes.get(t.pk, {'asistidas': 0, 'faltas': 0})
        t.asistidas_mes = datos['asistidas']
        t.faltas_mes    = datos['faltas']
        t.cuadrilla_nombre = cuadrilla_por_trab.get(t.pk, '')

    tab = request.GET.get('tab', 'personal')
    if tab == 'cuadrilla':
        tab_activa = 'cuadrilla'
    elif tab == 'asistencia':
        tab_activa = 'asistencia'
    elif tab == 'cargos':
        tab_activa = 'cargos'
    elif tab == 'inactivos':
        tab_activa = 'inactivos'
    else:
        tab_activa = 'personal'

    # Catálogo de Cargos (TipoPersonal) con cuántos trabajadores los usan
    cargos = (
        TipoPersonal.objects
        .annotate(n_trabajadores=Count('trabajadores'))
        .order_by('codigo')
    )

    return render(request, 'maquinaria/registro_lista.html', {
        'proyecto':                 proyecto,
        'trabajadores':             trabajadores,
        'trabajadores_inactivos':   trabajadores_inactivos,
        'cuadrillas':               cuadrillas,
        'cargos':                   cargos,
        'tab_activa':               tab_activa,
    })


@requiere('puede_gestionar_maquinaria')
@proyecto_visible
@require_POST
def asistencia_guardar(request, proyecto_id):
    from datetime import date as _date
    proyecto = get_object_or_404(Proyecto, pk=proyecto_id)
    validos  = {code for code, _ in Asistencia.ESTADO_CHOICES}
    trab_ids_proyecto = set(
        Trabajador.objects.filter(proyecto=proyecto).values_list('pk', flat=True)
    )
    cambios = 0
    for key, value in request.POST.items():
        if not key.startswith('estado__'):
            continue
        parts = key.split('__')
        if len(parts) != 3:
            continue
        _, trab_id_str, fecha_iso = parts
        try:
            trab_id = int(trab_id_str)
            fecha   = _date.fromisoformat(fecha_iso)
        except (ValueError, TypeError):
            continue
        if trab_id not in trab_ids_proyecto:
            continue
        if value == '':
            # Vacío → eliminar marca si existe
            borradas, _ = Asistencia.objects.filter(trabajador_id=trab_id, fecha=fecha).delete()
            if borradas:
                cambios += 1
            continue
        if value not in validos:
            continue
        Asistencia.objects.update_or_create(
            trabajador_id=trab_id, fecha=fecha,
            defaults={'estado': value},
        )
        cambios += 1
    messages.success(request, f'Asistencia guardada ({cambios} marcas).')
    periodo = request.POST.get('periodo', 'semanal')
    inicio  = request.POST.get('inicio', '')
    return redirect(
        f"{reverse('maquinaria:registro_lista', args=[proyecto_id])}"
        f"?tab=asistencia&periodo={periodo}&inicio={inicio}"
    )


@requiere('puede_gestionar_maquinaria')
@proyecto_visible
@require_POST
def asistencia_registrar_rapido(request, proyecto_id):
    """Guarda asistencia de una fecha para los trabajadores activos del proyecto.

    POST esperado:
        fecha              → yyyy-mm-dd
        presente__<trab_id>→ 'on' si está marcado el checkbox (si no viene, es FALTA)
        obs__<trab_id>     → observación por trabajador
    """
    from datetime import date as _date
    proyecto = get_object_or_404(Proyecto, pk=proyecto_id)
    fecha_str = (request.POST.get('fecha') or '').strip()
    try:
        fecha = _date.fromisoformat(fecha_str)
    except (ValueError, TypeError):
        messages.error(request, 'Fecha inválida.')
        return redirect(f"{reverse('maquinaria:registro_lista', args=[proyecto_id])}?tab=asistencia")

    trab_ids_activos = set(
        Trabajador.objects.filter(proyecto=proyecto, activo=True).values_list('pk', flat=True)
    )
    obs_general = (request.POST.get('observaciones_generales') or '').strip()[:200]
    cambios = 0
    for trab_id in trab_ids_activos:
        presente = request.POST.get(f'presente__{trab_id}') == 'on'
        estado = Asistencia.PRESENTE if presente else Asistencia.FALTA
        Asistencia.objects.update_or_create(
            trabajador_id=trab_id, fecha=fecha,
            defaults={'estado': estado, 'observacion': obs_general},
        )
        cambios += 1
    messages.success(request, f'Asistencia del {fecha.strftime("%d/%m/%Y")} guardada ({cambios} registros).')
    return redirect(f"{reverse('maquinaria:registro_lista', args=[proyecto_id])}?tab=asistencia")


def _reporte_asistencia_contexto(request, proyecto):
    """Prepara los filtros, trabajadores y pivot de asistencia para la vista `Ver` y el export."""
    from datetime import date as _date
    import calendar as _calendar

    hoy = _date.today()
    anio = int(request.GET.get('anio') or hoy.year)
    mes  = int(request.GET.get('mes')  or hoy.month)
    try:
        _date(anio, mes, 1)
    except ValueError:
        anio, mes = hoy.year, hoy.month

    cuadrilla_id  = request.GET.get('cuadrilla') or ''
    trabajador_id = request.GET.get('trabajador') or ''

    primer_dia = _date(anio, mes, 1)
    ult_dia    = _date(anio, mes, _calendar.monthrange(anio, mes)[1])
    dias_mes   = [_date(anio, mes, d) for d in range(1, ult_dia.day + 1)]

    trabajadores_qs = Trabajador.objects.filter(proyecto=proyecto).select_related('tipo_personal')
    if cuadrilla_id:
        trabajadores_qs = trabajadores_qs.filter(membresias__cuadrilla_id=cuadrilla_id).distinct()
    if trabajador_id:
        trabajadores_qs = trabajadores_qs.filter(pk=trabajador_id)
    trabajadores_qs = trabajadores_qs.order_by('apellidos', 'nombres')

    asistencias = Asistencia.objects.filter(
        trabajador__in=trabajadores_qs,
        fecha__gte=primer_dia,
        fecha__lte=ult_dia,
    ).values_list('trabajador_id', 'fecha', 'estado')

    por_trab = {}
    for trab_id, fecha, estado in asistencias:
        por_trab.setdefault(trab_id, {})[fecha] = estado

    filas = []
    for t in trabajadores_qs:
        marcas_dict = por_trab.get(t.pk, {})
        celdas = [marcas_dict.get(d, '') for d in dias_mes]
        asistidas = sum(1 for c in celdas if c == Asistencia.PRESENTE)
        faltas    = sum(1 for c in celdas if c == Asistencia.FALTA)
        filas.append({
            'trab':      t,
            'celdas':    celdas,
            'asistidas': asistidas,
            'faltas':    faltas,
        })

    cuadrillas = Cuadrilla.objects.filter(proyecto=proyecto).order_by('nombre')
    trabajadores_all = Trabajador.objects.filter(proyecto=proyecto, activo=True).order_by('apellidos', 'nombres')

    MESES = [
        (1, 'Enero'), (2, 'Febrero'), (3, 'Marzo'), (4, 'Abril'),
        (5, 'Mayo'),  (6, 'Junio'),   (7, 'Julio'), (8, 'Agosto'),
        (9, 'Septiembre'), (10, 'Octubre'), (11, 'Noviembre'), (12, 'Diciembre'),
    ]

    return {
        'proyecto':         proyecto,
        'anio_sel':         anio,
        'mes_sel':          mes,
        'cuadrilla_sel':    cuadrilla_id,
        'trabajador_sel':   trabajador_id,
        'dias_mes':         dias_mes,
        'filas':            filas,
        'cuadrillas':       cuadrillas,
        'trabajadores_all': trabajadores_all,
        'anios_opciones':   list(range(hoy.year - 3, hoy.year + 1)),
        'meses_opciones':   MESES,
        'nombre_mes':       dict(MESES)[mes],
    }


@requiere('puede_ver_maquinaria', 'puede_gestionar_maquinaria')
@proyecto_visible
def asistencia_ver(request, proyecto_id):
    proyecto = get_object_or_404(Proyecto, pk=proyecto_id)
    ctx = _reporte_asistencia_contexto(request, proyecto)
    # Si ?partial=1 devolvemos solo el bloque de filtros + matriz (para el modal).
    if request.GET.get('partial') == '1':
        return render(request, 'maquinaria/_asistencia_ver_contenido.html', ctx)
    return render(request, 'maquinaria/asistencia_ver.html', ctx)


@requiere('puede_ver_maquinaria', 'puede_gestionar_maquinaria')
@proyecto_visible
def asistencia_exportar(request, proyecto_id):
    """Descarga la matriz de asistencia del mes como .xlsx."""
    from openpyxl import Workbook
    from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
    from django.http import HttpResponse

    proyecto = get_object_or_404(Proyecto, pk=proyecto_id)
    ctx = _reporte_asistencia_contexto(request, proyecto)

    wb = Workbook()
    ws = wb.active
    ws.title = f"{ctx['nombre_mes'][:3]} {ctx['anio_sel']}"

    thin = Side(border_style='thin', color='CBD5E1')
    borde = Border(left=thin, right=thin, top=thin, bottom=thin)
    header_fill = PatternFill('solid', fgColor='1D4ED8')
    header_font = Font(bold=True, color='FFFFFF')
    centro = Alignment(horizontal='center', vertical='center')
    izq    = Alignment(horizontal='left', vertical='center')

    # Título
    ws.cell(row=1, column=1, value=f'Asistencia — {proyecto.codigo} — {ctx["nombre_mes"]} {ctx["anio_sel"]}').font = Font(bold=True, size=13)

    # Encabezados
    headers = ['N°', 'Apellidos y nombres', 'DNI', 'Cargo'] + [str(d.day) for d in ctx['dias_mes']] + ['Asistidas', 'Faltas']
    for col, h in enumerate(headers, start=1):
        c = ws.cell(row=3, column=col, value=h)
        c.fill = header_fill
        c.font = header_font
        c.alignment = centro
        c.border = borde

    # Filas
    for i, fila in enumerate(ctx['filas'], start=1):
        t = fila['trab']
        row_idx = 3 + i
        ws.cell(row=row_idx, column=1, value=i).alignment = centro
        ws.cell(row=row_idx, column=2, value=f'{t.apellidos}, {t.nombres}').alignment = izq
        ws.cell(row=row_idx, column=3, value=t.dni or '').alignment = centro
        ws.cell(row=row_idx, column=4, value=(t.tipo_personal.nombre if t.tipo_personal else '')).alignment = izq
        for j, estado in enumerate(fila['celdas'], start=5):
            cell = ws.cell(row=row_idx, column=j, value=estado or '')
            cell.alignment = centro
            # Pinta por estado
            colores = {'P': 'DCFCE7', 'F': 'FEE2E2', 'T': 'FEF3C7', 'PM': 'DBEAFE', 'D': 'F1F5F9', 'FE': 'F3E8FF'}
            if estado in colores:
                cell.fill = PatternFill('solid', fgColor=colores[estado])
        ws.cell(row=row_idx, column=5 + len(ctx['dias_mes']),     value=fila['asistidas']).alignment = centro
        ws.cell(row=row_idx, column=5 + len(ctx['dias_mes']) + 1, value=fila['faltas']).alignment = centro

    # Anchos
    ws.column_dimensions['A'].width = 4
    ws.column_dimensions['B'].width = 32
    ws.column_dimensions['C'].width = 11
    ws.column_dimensions['D'].width = 16
    for col_idx in range(5, 5 + len(ctx['dias_mes'])):
        ws.column_dimensions[ws.cell(row=1, column=col_idx).column_letter].width = 4
    ws.column_dimensions[ws.cell(row=1, column=5 + len(ctx['dias_mes'])).column_letter].width = 10
    ws.column_dimensions[ws.cell(row=1, column=5 + len(ctx['dias_mes']) + 1).column_letter].width = 8

    # Leyenda abajo
    legenda = 3 + len(ctx['filas']) + 2
    ws.cell(row=legenda, column=1, value='Leyenda:').font = Font(bold=True)
    ws.cell(row=legenda, column=2, value='P=Presente · F=Falta · T=Tardanza · PM=Permiso · D=Descanso · FE=Feriado')

    filename = f'Asistencia_{proyecto.codigo}_{ctx["anio_sel"]}-{ctx["mes_sel"]:02d}.xlsx'
    resp = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    resp['Content-Disposition'] = f'attachment; filename="{filename}"'
    wb.save(resp)
    return resp


# ── Registros Maquinaria ──────────────────────────────────────────────

@requiere('puede_ver_maquinaria', 'puede_gestionar_maquinaria')
@proyecto_visible
def maq_principal(request, proyecto_id):
    """Página principal de Maquinaria: catálogo de máquinas + uso (HM/turnos) en este proyecto."""
    proyecto = get_object_or_404(Proyecto, pk=proyecto_id)
    maquinas = (
        Maquinaria.objects.filter(activo=True)
        .annotate(
            total_hm=Sum('registromaquinaria__horas', filter=Q(registromaquinaria__proyecto=proyecto)),
            n_turnos=Count('registromaquinaria', filter=Q(registromaquinaria__proyecto=proyecto)),
        )
        .order_by('codigo')
    )
    total_hm_proyecto = RegistroMaquinaria.objects.filter(proyecto=proyecto).aggregate(t=Sum('horas'))['t'] or 0
    return render(request, 'maquinaria/maq_principal.html', {
        'proyecto':          proyecto,
        'maquinas':          maquinas,
        'total_hm_proyecto': total_hm_proyecto,
    })


@requiere('puede_ver_maquinaria', 'puede_gestionar_maquinaria')
@proyecto_visible
def maq_detalle_maquinaria(request, proyecto_id, maq_pk):
    """Ficha de una máquina: lista de liquidaciones + registros sin liquidación."""
    proyecto   = get_object_or_404(Proyecto, pk=proyecto_id)
    maquinaria = get_object_or_404(Maquinaria, pk=maq_pk)

    # Crear nueva liquidación (POST desde modal)
    if request.method == 'POST' and request.POST.get('accion') == 'nueva_liq':
        periodo_str = request.POST.get('periodo', '')
        try:
            import datetime as dt_mod
            year, month = map(int, periodo_str.split('-'))
            periodo = dt_mod.date(year, month, 1)
        except (ValueError, TypeError, AttributeError):
            messages.error(request, 'Período inválido.')
            return redirect('maquinaria:maq_detalle_maquinaria', proyecto_id=proyecto_id, maq_pk=maq_pk)
        if Liquidacion.objects.filter(maquinaria=maquinaria, periodo=periodo).exists():
            messages.warning(request, 'Ya existe una liquidación para ese período.')
            return redirect('maquinaria:maq_detalle_maquinaria', proyecto_id=proyecto_id, maq_pk=maq_pk)
        ultimo = (Liquidacion.objects.filter(maquinaria=maquinaria)
                  .order_by('-numero').values_list('numero', flat=True).first() or 0)
        liq = Liquidacion.objects.create(
            proyecto=proyecto, maquinaria=maquinaria,
            numero=ultimo + 1, periodo=periodo,
        )
        messages.success(request, f'Liquidación {liq} creada.')
        return redirect('maquinaria:liquidacion_detalle', pk=liq.pk)

    liquidaciones = (Liquidacion.objects
                     .filter(proyecto=proyecto, maquinaria=maquinaria)
                     .annotate(total_hm=Sum('partes__horas'), n_partes=Count('partes'))
                     .order_by('-periodo'))
    sin_liq = (RegistroMaquinaria.objects
               .filter(proyecto=proyecto, maquinaria=maquinaria, liquidacion__isnull=True)
               .select_related('partida', 'insumo')
               .order_by('-fecha'))
    total_hm = (RegistroMaquinaria.objects
                .filter(proyecto=proyecto, maquinaria=maquinaria)
                .aggregate(t=Sum('horas'))['t'] or 0)

    sin_liq_resumen = sin_liq.aggregate(
        total_hm=Sum('horas'), n_turnos=Count('pk'),
        desde=Min('fecha'), hasta=Max('fecha'),
    )

    import datetime
    return render(request, 'maquinaria/maq_maquinaria_detalle.html', {
        'proyecto':     proyecto,
        'maquinaria':   maquinaria,
        'liquidaciones': liquidaciones,
        'sin_liq':      sin_liq,
        'sin_liq_resumen': sin_liq_resumen,
        'total_hm':     total_hm,
        'hoy':          datetime.date.today().strftime('%Y-%m'),
    })


@requiere('puede_ver_maquinaria', 'puede_gestionar_maquinaria')
def liquidacion_detalle(request, pk):
    """Parte diario de una liquidación — imprimible A4 landscape."""
    import datetime
    from apps.configuracion.models import ConfigEmpresa
    liq       = get_object_or_404(Liquidacion, pk=pk)
    proyecto  = liq.proyecto
    maquinaria = liq.maquinaria

    if request.method == 'POST' and liq.estado == 'ABIERTA':
        form = ParteForm(proyecto=proyecto, maquinaria=maquinaria, data=request.POST)
        if form.is_valid():
            reg             = form.save(commit=False)
            reg.proyecto    = proyecto
            reg.maquinaria  = maquinaria
            reg.liquidacion = liq
            reg.nombre      = maquinaria.nombre
            reg.placa       = maquinaria.placa
            reg.propietario = maquinaria.propietario_razon_social
            if not reg.operador:
                reg.operador = maquinaria.operador
            reg.save()
            messages.success(request, f'Parte N°{reg.numero_parte} registrado.')
            return redirect('maquinaria:liquidacion_detalle', pk=pk)
    else:
        form = ParteForm(
            proyecto=proyecto, maquinaria=maquinaria,
            initial={'fecha': datetime.date.today()},
        )

    partes = liq.partes.select_related('insumo', 'partida').order_by('fecha', 'created_at')
    return render(request, 'maquinaria/liquidacion_detalle.html', {
        'liq':              liq,
        'proyecto':         proyecto,
        'maquinaria':       maquinaria,
        'partes':           partes,
        'form':             form,
        'total_horas':      liq.total_horas(),
        'total_combustible': liq.total_combustible(),
        'monto_a_pagar':    liq.monto_a_pagar(),
        'config':           ConfigEmpresa.get(),
    })


@requiere('puede_gestionar_maquinaria')
def liquidacion_cerrar(request, pk):
    """Cierra una liquidación (no se pueden agregar más partes)."""
    liq = get_object_or_404(Liquidacion, pk=pk)
    if request.method == 'POST':
        accion = request.POST.get('accion')
        if accion == 'cerrar' and liq.estado == 'ABIERTA':
            liq.estado = 'CERRADA'
            liq.save(update_fields=['estado'])
            messages.success(request, f'{liq} cerrada.')
        elif accion == 'reabrir' and liq.estado == 'CERRADA':
            liq.estado = 'ABIERTA'
            liq.save(update_fields=['estado'])
            messages.success(request, f'{liq} reabierta.')
    return redirect('maquinaria:liquidacion_detalle', pk=pk)


@requiere('puede_ver_maquinaria', 'puede_gestionar_maquinaria')
@proyecto_visible
def resumen_mensual(request, proyecto_id):
    """Resumen de todas las liquidaciones de un período — imprimible A4."""
    import datetime
    from apps.configuracion.models import ConfigEmpresa
    proyecto = get_object_or_404(Proyecto, pk=proyecto_id)

    mes_str = request.GET.get('mes', datetime.date.today().strftime('%Y-%m'))
    try:
        year, month = map(int, mes_str.split('-'))
        periodo = datetime.date(year, month, 1)
    except (ValueError, TypeError):
        periodo = datetime.date.today().replace(day=1)
        mes_str = periodo.strftime('%Y-%m')

    liquidaciones = (Liquidacion.objects
                     .filter(proyecto=proyecto, periodo=periodo)
                     .select_related('maquinaria')
                     .prefetch_related('partes')
                     .order_by('maquinaria__codigo'))

    items = []
    total_monto = 0
    for idx, liq in enumerate(liquidaciones, 1):
        monto = liq.monto_a_pagar()
        total_monto += monto
        items.append({
            'idx':        idx,
            'liq':        liq,
            'maquinaria': liq.maquinaria,
            'total_horas': liq.total_horas(),
            'monto':      monto,
        })

    return render(request, 'maquinaria/resumen_mensual.html', {
        'proyecto':     proyecto,
        'items':        items,
        'periodo':      periodo,
        'mes_str':      mes_str,
        'total_monto':  total_monto,
        'config':       ConfigEmpresa.get(),
    })


@requiere('puede_gestionar_maquinaria')
@proyecto_visible
def maq_registro_crear(request, proyecto_id, maq_pk=None):
    proyecto = get_object_or_404(Proyecto, pk=proyecto_id)
    maquinaria_fija = get_object_or_404(Maquinaria, pk=maq_pk) if maq_pk else None
    form     = RegistroMaquinariaForm(
        proyecto=proyecto,
        maquinaria=maquinaria_fija,
        validar_horometro=True,
        data=request.POST or None,
        initial={'fecha': __import__('datetime').date.today()},
    )
    if form.is_valid():
        reg = form.save(commit=False)
        reg.proyecto = proyecto
        maq = form.cleaned_data.get('maquinaria')
        if maq:
            reg.nombre = maq.nombre
            reg.placa  = maq.placa
            # Vincular automáticamente a la liquidación ABIERTA del período (mes) de la
            # fecha del turno, si existe, para que no quede huérfano en "sin liquidación".
            reg.liquidacion = Liquidacion.objects.filter(
                proyecto=proyecto, maquinaria=maq, estado='ABIERTA',
                periodo__year=reg.fecha.year, periodo__month=reg.fecha.month,
            ).first()
        reg.save()
        if maq and not reg.liquidacion_id:
            messages.warning(
                request,
                f'Turno guardado, pero no hay una liquidación abierta para {reg.fecha.strftime("%B %Y")} '
                f'en esta máquina — no se sumará a ningún total hasta que crees una.'
            )
        else:
            messages.success(request, 'Registro guardado.')
        if maq:
            return redirect('maquinaria:maq_detalle_maquinaria', proyecto_id=proyecto_id, maq_pk=maq.pk)
        return redirect('maquinaria:maq_principal', proyecto_id=proyecto_id)
    # Último horómetro de salida registrado para esta máquina (si existe)
    ultimo_horometro = None
    if maquinaria_fija:
        from django.db.models import Max
        ultimo_horometro = RegistroMaquinaria.objects.filter(
            maquinaria=maquinaria_fija
        ).aggregate(m=Max('hora_salida'))['m']

    return render(request, 'maquinaria/maq_registro_form.html', {
        'form':             form,
        'proyecto':         proyecto,
        'maquinaria_fija':  maquinaria_fija,
        'ultimo_horometro': ultimo_horometro,
        'titulo':           f'Nuevo Turno — {maquinaria_fija.nombre} ({maquinaria_fija.codigo})' if maquinaria_fija else 'Nuevo Registro de Maquinaria',
    })


@requiere('puede_ver_maquinaria', 'puede_gestionar_maquinaria')
def maq_registro_detalle(request, pk):
    registro = get_object_or_404(RegistroMaquinaria, pk=pk)
    return render(request, 'maquinaria/maq_registro_detalle.html', {
        'registro': registro,
        'proyecto': registro.proyecto,
    })


@requiere('puede_gestionar_maquinaria')
def maq_registro_editar(request, pk):
    registro = get_object_or_404(RegistroMaquinaria, pk=pk)
    form     = RegistroMaquinariaForm(
        proyecto=registro.proyecto,
        validar_horometro=True,
        data=request.POST or None,
        instance=registro,
    )
    if form.is_valid():
        form.save()
        messages.success(request, 'Registro actualizado.')
        if registro.maquinaria_id:
            return redirect('maquinaria:maq_detalle_maquinaria',
                            proyecto_id=registro.proyecto_id, maq_pk=registro.maquinaria_id)
        return redirect('maquinaria:maq_principal', proyecto_id=registro.proyecto_id)
    # Último horómetro de salida de otros registros de la misma máquina (excluye el actual)
    ultimo_horometro = None
    if registro.maquinaria_id:
        from django.db.models import Max
        ultimo_horometro = (
            RegistroMaquinaria.objects
            .filter(maquinaria_id=registro.maquinaria_id)
            .exclude(pk=registro.pk)
            .aggregate(m=Max('hora_salida'))['m']
        )

    return render(request, 'maquinaria/maq_registro_form.html', {
        'form':             form,
        'proyecto':         registro.proyecto,
        'titulo':           'Editar Registro de Maquinaria',
        'registro':         registro,
        'ultimo_horometro': ultimo_horometro,
    })


@requiere('puede_gestionar_maquinaria')
def maq_registro_eliminar(request, pk):
    registro    = get_object_or_404(RegistroMaquinaria, pk=pk)
    proyecto_id = registro.proyecto_id
    maq_pk      = registro.maquinaria_id
    if request.method == 'POST':
        registro.delete()
        messages.success(request, 'Registro eliminado.')
    if maq_pk:
        return redirect('maquinaria:maq_detalle_maquinaria', proyecto_id=proyecto_id, maq_pk=maq_pk)
    return redirect('maquinaria:maq_principal', proyecto_id=proyecto_id)


# ── Resumen HH / HM por partida ───────────────────────────────────────

@requiere('puede_ver_maquinaria', 'puede_gestionar_maquinaria')
@proyecto_visible
def resumen(request, proyecto_id):
    from apps.presupuesto.models import Partida
    proyecto  = get_object_or_404(Proyecto, pk=proyecto_id)
    partidas  = (Partida.objects
                 .annotate(n_hijos=Count('hijos'))
                 .filter(presupuesto__proyecto=proyecto, n_hijos=0)
                 .prefetch_related(
                     'registros_cuadrilla__cuadrilla__integrantes',
                     'registros_maquinaria',
                 ))

    resumen_list = []
    for p in partidas:
        hh = sum(r.horas_hombre() for r in p.registros_cuadrilla.all())
        hm = sum(r.horas for r in p.registros_maquinaria.all())
        if hh or hm:
            resumen_list.append({'partida': p, 'hh': hh, 'hm': hm})

    return render(request, 'maquinaria/resumen.html', {
        'proyecto':      proyecto,
        'resumen_list':  resumen_list,
    })


# ── Consulta RUC/DNI (Factiliza) ──────────────────────────────────────

@require_POST
@requiere('puede_gestionar_maquinaria', 'puede_gestionar_cotizaciones', 'puede_gestionar_cotizaciones_log')
def consulta_documento(request):
    """Endpoint AJAX: POST {numero} -> {ok, razon_social, direccion} o {ok:false, error}."""
    import requests as _requests

    try:
        payload = json.loads(request.body or b'{}')
    except (ValueError, json.JSONDecodeError):
        return JsonResponse({'ok': False, 'error': 'Payload inválido.'}, status=400)

    numero = str(payload.get('numero', '')).strip()
    if len(numero) == 8 and numero.isdigit():
        tipo = 'dni'
    elif len(numero) == 11 and numero.isdigit():
        tipo = 'ruc'
    else:
        return JsonResponse({'ok': False, 'error': 'DNI = 8 dígitos, RUC = 11 dígitos.'}, status=400)

    token = getattr(settings, 'FACTILIZA_TOKEN', '')
    if not token:
        return JsonResponse({'ok': False, 'error': 'Servicio de consulta no configurado.'}, status=500)

    url = f'https://api.factiliza.com/pe/v1/{tipo}/info/{numero}'
    try:
        r = _requests.get(
            url,
            headers={'Authorization': f'Bearer {token}', 'Accept': 'application/json'},
            timeout=20,
        )
    except _requests.RequestException as e:
        return JsonResponse({'ok': False, 'error': f'Error de conexión: {e}'}, status=502)

    try:
        body = r.json()
    except (ValueError, json.JSONDecodeError):
        return JsonResponse({'ok': False, 'error': 'Respuesta inválida del servicio.'}, status=502)

    if r.status_code >= 400 or int(body.get('status') or 200) >= 400:
        return JsonResponse({
            'ok': False,
            'error': body.get('message') or 'No se encontró información para el documento.',
        }, status=404)

    data = body.get('data') or {}
    nombres          = (data.get('nombres') or '').strip()
    apellido_paterno = (data.get('apellido_paterno') or '').strip()
    apellido_materno = (data.get('apellido_materno') or '').strip()

    if tipo == 'ruc':
        razon = (data.get('nombre_o_razon_social') or '').strip()
    else:
        razon = ' '.join(filter(None, [nombres, apellido_paterno, apellido_materno])).strip()

    direccion = (data.get('direccion') or '').strip()
    ubigeo    = data.get('ubigeo_sunat') or ''
    if ubigeo == '-':
        ubigeo = ''

    return JsonResponse({
        'ok': True,
        'tipo': tipo,
        # Para clientes antiguos (cot_form, req_revisar, maquinaria_form)
        'razon_social': razon,
        'direccion':    direccion,
        'ubigeo':       ubigeo,
        # Campos extra para el form de Trabajador (y futuros usos)
        'nombres':          nombres,
        'apellido_paterno': apellido_paterno,
        'apellido_materno': apellido_materno,
        'apellidos':        (apellido_paterno + ' ' + apellido_materno).strip(),
        'departamento':     (data.get('departamento') or '').strip(),
        'provincia':        (data.get('provincia') or '').strip(),
        'distrito':         (data.get('distrito') or '').strip(),
        # Estos solo vienen si el plan de Factiliza los expone; si no, string vacío
        'fecha_nacimiento': (data.get('fecha_nacimiento') or '').strip(),
        'sexo':             (data.get('sexo') or '').strip(),
    })
