import json
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.conf import settings
from django.db.models import Sum, Count, Min, Max
from django.http import JsonResponse
from django.views.decorators.http import require_POST

from apps.proyectos.models import Proyecto
from .models import (
    TipoPersonal, Maquinaria, Cuadrilla, IntegranteCuadrilla,
    RegistroDiario, RegistroMaquinaria, Liquidacion,
    Trabajador, DocumentoTrabajador,
)
from .forms import (
    TipoPersonalForm, MaquinariaForm, CuadrillaForm,
    IntegranteCuadrillaForm, RegistroDiarioForm, RegistroMaquinariaForm, ParteForm,
    TrabajadorForm, DocumentoTrabajadorForm,
)
from config.permisos import requiere, proyecto_visible


# ── Dashboard ─────────────────────────────────────────────────────────

@requiere('puede_ver_maquinaria', 'puede_gestionar_maquinaria')
@proyecto_visible
def dashboard(request, proyecto_id):
    proyecto = get_object_or_404(Proyecto, pk=proyecto_id)
    registros_cuadrilla  = RegistroDiario.objects.filter(proyecto=proyecto).select_related('cuadrilla__integrantes', 'partida')
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


# ── Cuadrillas ────────────────────────────────────────────────────────

@requiere('puede_ver_maquinaria', 'puede_gestionar_maquinaria')
def cuadrilla_lista(request):
    cuadrillas = Cuadrilla.objects.prefetch_related('integrantes__tipo_personal').all()
    return render(request, 'maquinaria/cuadrilla_lista.html', {'cuadrillas': cuadrillas})


@requiere('puede_gestionar_maquinaria')
def cuadrilla_crear(request):
    form = CuadrillaForm(request.POST or None)
    if form.is_valid():
        cuadrilla = form.save()
        messages.success(request, 'Cuadrilla creada. Ahora agrega los integrantes.')
        return redirect('maquinaria:cuadrilla_detalle', pk=cuadrilla.pk)
    return render(request, 'maquinaria/cuadrilla_form.html', {'form': form, 'titulo': 'Nueva Cuadrilla'})


@requiere('puede_ver_maquinaria', 'puede_gestionar_maquinaria')
def cuadrilla_detalle(request, pk):
    cuadrilla = get_object_or_404(Cuadrilla, pk=pk)
    form = IntegranteCuadrillaForm(cuadrilla=cuadrilla)
    return render(request, 'maquinaria/cuadrilla_detalle.html', {
        'cuadrilla': cuadrilla,
        'form':      form,
    })


@requiere('puede_gestionar_maquinaria')
def cuadrilla_editar(request, pk):
    obj  = get_object_or_404(Cuadrilla, pk=pk)
    form = CuadrillaForm(request.POST or None, instance=obj)
    if form.is_valid():
        form.save()
        messages.success(request, 'Cuadrilla actualizada.')
        return redirect('maquinaria:cuadrilla_detalle', pk=pk)
    return render(request, 'maquinaria/cuadrilla_form.html', {'form': form, 'titulo': 'Editar Cuadrilla', 'obj': obj})


@requiere('puede_gestionar_maquinaria')
def cuadrilla_eliminar(request, pk):
    obj = get_object_or_404(Cuadrilla, pk=pk)
    if request.method == 'POST':
        obj.delete()
        messages.success(request, 'Cuadrilla eliminada.')
        return redirect('maquinaria:cuadrilla_lista')
    return render(request, 'maquinaria/confirmar_eliminar.html', {'obj': obj, 'tipo': 'Cuadrilla',
        'cancel_url': 'maquinaria:cuadrilla_lista', 'cancel_args': []})


@requiere('puede_gestionar_maquinaria')
def integrante_agregar(request, pk):
    cuadrilla = get_object_or_404(Cuadrilla, pk=pk)
    if request.method == 'POST':
        form = IntegranteCuadrillaForm(cuadrilla=cuadrilla, data=request.POST)
        if form.is_valid():
            integrante = form.save(commit=False)
            integrante.cuadrilla = cuadrilla
            integrante.save()
            messages.success(request, 'Integrante agregado.')
        else:
            messages.error(request, 'Error: ' + str(form.errors))
    return redirect('maquinaria:cuadrilla_detalle', pk=pk)


@requiere('puede_gestionar_maquinaria')
def integrante_eliminar(request, pk):
    integrante = get_object_or_404(IntegranteCuadrilla, pk=pk)
    cuadrilla_pk = integrante.cuadrilla_id
    if request.method == 'POST':
        integrante.delete()
        messages.success(request, 'Integrante eliminado.')
    return redirect('maquinaria:cuadrilla_detalle', pk=cuadrilla_pk)


# ── Personal de Obra (Trabajadores) ────────────────────────────────────

@requiere('puede_ver_maquinaria', 'puede_gestionar_maquinaria')
@proyecto_visible
def trabajador_lista(request, proyecto_id):
    proyecto = get_object_or_404(Proyecto, pk=proyecto_id)
    trabajadores = (
        Trabajador.objects.filter(proyecto=proyecto)
        .select_related('tipo_personal')
        .prefetch_related('documentos')
    )
    return render(request, 'maquinaria/trabajador_lista.html', {
        'proyecto':     proyecto,
        'trabajadores': trabajadores,
    })


@requiere('puede_gestionar_maquinaria')
@proyecto_visible
def trabajador_crear(request, proyecto_id):
    proyecto = get_object_or_404(Proyecto, pk=proyecto_id)
    form = TrabajadorForm(request.POST or None, request.FILES or None)
    if form.is_valid():
        trabajador = form.save(commit=False)
        trabajador.proyecto = proyecto
        trabajador.save()
        messages.success(request, 'Trabajador registrado. Ahora puedes subir su CV y documentos.')
        return redirect('maquinaria:trabajador_detalle', pk=trabajador.pk)
    return render(request, 'maquinaria/trabajador_form.html', {
        'form': form, 'proyecto': proyecto, 'titulo': 'Nuevo Trabajador',
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
        messages.success(request, 'Trabajador actualizado.')
        return redirect('maquinaria:trabajador_detalle', pk=pk)
    return render(request, 'maquinaria/trabajador_form.html', {
        'form': form, 'proyecto': trabajador.proyecto, 'titulo': 'Editar Trabajador', 'obj': trabajador,
    })


@requiere('puede_gestionar_maquinaria')
def trabajador_eliminar(request, pk):
    obj = get_object_or_404(Trabajador, pk=pk)
    proyecto_id = obj.proyecto_id
    if request.method == 'POST':
        obj.delete()
        messages.success(request, 'Trabajador eliminado.')
        return redirect('maquinaria:trabajador_lista', proyecto_id=proyecto_id)
    return render(request, 'maquinaria/confirmar_eliminar.html', {'obj': obj, 'tipo': 'Trabajador',
        'cancel_url': 'maquinaria:trabajador_detalle', 'cancel_args': [pk]})


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


# ── Registros Diarios (Cuadrilla) ─────────────────────────────────────

@requiere('puede_ver_maquinaria', 'puede_gestionar_maquinaria')
@proyecto_visible
def registro_lista(request, proyecto_id):
    proyecto  = get_object_or_404(Proyecto, pk=proyecto_id)
    registros = (RegistroDiario.objects
                 .filter(proyecto=proyecto)
                 .select_related('cuadrilla', 'partida')
                 .prefetch_related('cuadrilla__integrantes'))
    total_hh  = sum(r.horas_hombre() for r in registros)
    return render(request, 'maquinaria/registro_lista.html', {
        'proyecto':  proyecto,
        'registros': registros,
        'total_hh':  total_hh,
    })


@requiere('puede_gestionar_maquinaria')
@proyecto_visible
def registro_crear(request, proyecto_id):
    proyecto = get_object_or_404(Proyecto, pk=proyecto_id)
    form     = RegistroDiarioForm(proyecto=proyecto, data=request.POST or None)
    if form.is_valid():
        reg = form.save(commit=False)
        reg.proyecto = proyecto
        reg.save()
        messages.success(request, 'Registro guardado.')
        return redirect('maquinaria:registro_lista', proyecto_id=proyecto_id)
    return render(request, 'maquinaria/registro_form.html', {
        'form':    form,
        'proyecto': proyecto,
        'titulo':  'Nuevo Registro de Cuadrilla',
    })


@requiere('puede_gestionar_maquinaria')
def registro_editar(request, pk):
    registro = get_object_or_404(RegistroDiario, pk=pk)
    form     = RegistroDiarioForm(proyecto=registro.proyecto, data=request.POST or None, instance=registro)
    if form.is_valid():
        form.save()
        messages.success(request, 'Registro actualizado.')
        return redirect('maquinaria:registro_lista', proyecto_id=registro.proyecto_id)
    return render(request, 'maquinaria/registro_form.html', {
        'form':    form,
        'proyecto': registro.proyecto,
        'titulo':  'Editar Registro de Cuadrilla',
    })


@requiere('puede_gestionar_maquinaria')
def registro_eliminar(request, pk):
    registro     = get_object_or_404(RegistroDiario, pk=pk)
    proyecto_id  = registro.proyecto_id
    if request.method == 'POST':
        registro.delete()
        messages.success(request, 'Registro eliminado.')
    return redirect('maquinaria:registro_lista', proyecto_id=proyecto_id)


# ── Registros Maquinaria ──────────────────────────────────────────────

@requiere('puede_ver_maquinaria', 'puede_gestionar_maquinaria')
@proyecto_visible
def maq_principal(request, proyecto_id):
    """Página principal de Maquinaria: catálogo de máquinas del proyecto."""
    proyecto = get_object_or_404(Proyecto, pk=proyecto_id)
    maquinas = Maquinaria.objects.filter(activo=True).order_by('codigo')
    return render(request, 'maquinaria/maq_principal.html', {
        'proyecto': proyecto,
        'maquinas': maquinas,
    })


@requiere('puede_ver_maquinaria', 'puede_gestionar_maquinaria')
@proyecto_visible
def maq_registro_lista(request, proyecto_id):
    """Lista de máquinas usadas en el proyecto, agrupadas con total HM."""
    proyecto = get_object_or_404(Proyecto, pk=proyecto_id)
    # Máquinas del catálogo que tienen al menos un registro en este proyecto
    maquinas_usadas = (
        Maquinaria.objects
        .filter(registromaquinaria__proyecto=proyecto)
        .annotate(
            total_hm=Sum('registromaquinaria__horas'),
            n_registros=Count('registromaquinaria'),
        )
        .order_by('nombre')
    )
    # Máquinas del catálogo sin registros aún (para poder registrar)
    ids_usadas = maquinas_usadas.values_list('pk', flat=True)
    maquinas_sin_uso = Maquinaria.objects.filter(activo=True).exclude(pk__in=ids_usadas).order_by('nombre')

    total_hm = RegistroMaquinaria.objects.filter(proyecto=proyecto).aggregate(t=Sum('horas'))['t'] or 0
    return render(request, 'maquinaria/maq_registro_lista.html', {
        'proyecto':        proyecto,
        'maquinas_usadas': maquinas_usadas,
        'maquinas_sin_uso': maquinas_sin_uso,
        'total_hm':        total_hm,
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
        return redirect('maquinaria:maq_registro_lista', proyecto_id=proyecto_id)
    return render(request, 'maquinaria/maq_registro_form.html', {
        'form':            form,
        'proyecto':        proyecto,
        'maquinaria_fija': maquinaria_fija,
        'titulo':          f'Nuevo Turno — {maquinaria_fija.nombre} ({maquinaria_fija.codigo})' if maquinaria_fija else 'Nuevo Registro de Maquinaria',
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
    form     = RegistroMaquinariaForm(proyecto=registro.proyecto, data=request.POST or None, instance=registro)
    if form.is_valid():
        form.save()
        messages.success(request, 'Registro actualizado.')
        if registro.maquinaria_id:
            return redirect('maquinaria:maq_detalle_maquinaria',
                            proyecto_id=registro.proyecto_id, maq_pk=registro.maquinaria_id)
        return redirect('maquinaria:maq_registro_lista', proyecto_id=registro.proyecto_id)
    return render(request, 'maquinaria/maq_registro_form.html', {
        'form':     form,
        'proyecto': registro.proyecto,
        'titulo':   'Editar Registro de Maquinaria',
        'registro': registro,
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
    return redirect('maquinaria:maq_registro_lista', proyecto_id=proyecto_id)


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
@requiere('puede_gestionar_maquinaria')
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
    if tipo == 'ruc':
        razon = (data.get('nombre_o_razon_social') or '').strip()
    else:
        razon = ' '.join(filter(None, [
            data.get('nombres') or '',
            data.get('apellido_paterno') or '',
            data.get('apellido_materno') or '',
        ])).strip()

    direccion = (data.get('direccion') or '').strip()
    ubigeo = data.get('ubigeo_sunat') or ''
    if ubigeo == '-':
        ubigeo = ''

    return JsonResponse({
        'ok': True,
        'tipo': tipo,
        'razon_social': razon,
        'direccion': direccion,
        'ubigeo': ubigeo,
    })
