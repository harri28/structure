from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.db.models import Sum, Count

from apps.proyectos.models import Proyecto
from .models import (
    TipoPersonal, Maquinaria, Cuadrilla, IntegranteCuadrilla,
    RegistroDiario, RegistroMaquinaria, Liquidacion,
)
from .forms import (
    TipoPersonalForm, MaquinariaForm, CuadrillaForm,
    IntegranteCuadrillaForm, RegistroDiarioForm, RegistroMaquinariaForm, ParteForm,
)


# ── Dashboard ─────────────────────────────────────────────────────────

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

def tipo_personal_lista(request):
    tipos = TipoPersonal.objects.all()
    return render(request, 'maquinaria/tipo_personal_lista.html', {'tipos': tipos})


def tipo_personal_crear(request):
    form = TipoPersonalForm(request.POST or None)
    if form.is_valid():
        form.save()
        messages.success(request, 'Tipo de personal creado.')
        return redirect('maquinaria:tipo_personal_lista')
    return render(request, 'maquinaria/tipo_personal_form.html', {'form': form, 'titulo': 'Nuevo Tipo de Personal'})


def tipo_personal_editar(request, pk):
    obj  = get_object_or_404(TipoPersonal, pk=pk)
    form = TipoPersonalForm(request.POST or None, instance=obj)
    if form.is_valid():
        form.save()
        messages.success(request, 'Tipo de personal actualizado.')
        return redirect('maquinaria:tipo_personal_lista')
    return render(request, 'maquinaria/tipo_personal_form.html', {'form': form, 'titulo': 'Editar Tipo de Personal', 'obj': obj})


def tipo_personal_eliminar(request, pk):
    obj = get_object_or_404(TipoPersonal, pk=pk)
    if request.method == 'POST':
        obj.delete()
        messages.success(request, 'Tipo de personal eliminado.')
        return redirect('maquinaria:tipo_personal_lista')
    return render(request, 'maquinaria/confirmar_eliminar.html', {'obj': obj, 'tipo': 'Tipo de Personal',
        'cancel_url': 'maquinaria:tipo_personal_lista', 'cancel_args': []})


# ── Maquinaria ────────────────────────────────────────────────────────

def maquinaria_lista(request):
    maquinas = Maquinaria.objects.all()
    return render(request, 'maquinaria/maquinaria_lista.html', {'maquinas': maquinas})


def _siguiente_codigo_maq():
    existentes = Maquinaria.objects.filter(codigo__startswith='M').values_list('codigo', flat=True)
    nums = []
    for c in existentes:
        try:
            nums.append(int(c[1:]))
        except (ValueError, IndexError):
            pass
    return f'M{max(nums, default=0) + 1:03d}'


def maquinaria_crear(request):
    initial = {'codigo': _siguiente_codigo_maq()}
    form    = MaquinariaForm(request.POST or None, initial=initial)
    if form.is_valid():
        form.save()
        messages.success(request, 'Equipo/maquinaria creado.')
        return redirect('maquinaria:maquinaria_lista')
    return render(request, 'maquinaria/maquinaria_form.html', {'form': form, 'titulo': 'Nueva Maquinaria'})


def maquinaria_editar(request, pk):
    obj  = get_object_or_404(Maquinaria, pk=pk)
    form = MaquinariaForm(request.POST or None, instance=obj)
    if form.is_valid():
        form.save()
        messages.success(request, 'Maquinaria actualizada.')
        return redirect('maquinaria:maquinaria_lista')
    return render(request, 'maquinaria/maquinaria_form.html', {'form': form, 'titulo': 'Editar Maquinaria', 'obj': obj})


def maquinaria_eliminar(request, pk):
    obj = get_object_or_404(Maquinaria, pk=pk)
    if request.method == 'POST':
        obj.delete()
        messages.success(request, 'Maquinaria eliminada.')
        return redirect('maquinaria:maquinaria_lista')
    return render(request, 'maquinaria/confirmar_eliminar.html', {'obj': obj, 'tipo': 'Maquinaria',
        'cancel_url': 'maquinaria:maquinaria_lista', 'cancel_args': []})


# ── Cuadrillas ────────────────────────────────────────────────────────

def cuadrilla_lista(request):
    cuadrillas = Cuadrilla.objects.prefetch_related('integrantes__tipo_personal').all()
    return render(request, 'maquinaria/cuadrilla_lista.html', {'cuadrillas': cuadrillas})


def cuadrilla_crear(request):
    form = CuadrillaForm(request.POST or None)
    if form.is_valid():
        cuadrilla = form.save()
        messages.success(request, 'Cuadrilla creada. Ahora agrega los integrantes.')
        return redirect('maquinaria:cuadrilla_detalle', pk=cuadrilla.pk)
    return render(request, 'maquinaria/cuadrilla_form.html', {'form': form, 'titulo': 'Nueva Cuadrilla'})


def cuadrilla_detalle(request, pk):
    cuadrilla = get_object_or_404(Cuadrilla, pk=pk)
    form = IntegranteCuadrillaForm(cuadrilla=cuadrilla)
    return render(request, 'maquinaria/cuadrilla_detalle.html', {
        'cuadrilla': cuadrilla,
        'form':      form,
    })


def cuadrilla_editar(request, pk):
    obj  = get_object_or_404(Cuadrilla, pk=pk)
    form = CuadrillaForm(request.POST or None, instance=obj)
    if form.is_valid():
        form.save()
        messages.success(request, 'Cuadrilla actualizada.')
        return redirect('maquinaria:cuadrilla_detalle', pk=pk)
    return render(request, 'maquinaria/cuadrilla_form.html', {'form': form, 'titulo': 'Editar Cuadrilla', 'obj': obj})


def cuadrilla_eliminar(request, pk):
    obj = get_object_or_404(Cuadrilla, pk=pk)
    if request.method == 'POST':
        obj.delete()
        messages.success(request, 'Cuadrilla eliminada.')
        return redirect('maquinaria:cuadrilla_lista')
    return render(request, 'maquinaria/confirmar_eliminar.html', {'obj': obj, 'tipo': 'Cuadrilla',
        'cancel_url': 'maquinaria:cuadrilla_lista', 'cancel_args': []})


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


def integrante_eliminar(request, pk):
    integrante = get_object_or_404(IntegranteCuadrilla, pk=pk)
    cuadrilla_pk = integrante.cuadrilla_id
    if request.method == 'POST':
        integrante.delete()
        messages.success(request, 'Integrante eliminado.')
    return redirect('maquinaria:cuadrilla_detalle', pk=cuadrilla_pk)


# ── Registros Diarios (Cuadrilla) ─────────────────────────────────────

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


def registro_eliminar(request, pk):
    registro     = get_object_or_404(RegistroDiario, pk=pk)
    proyecto_id  = registro.proyecto_id
    if request.method == 'POST':
        registro.delete()
        messages.success(request, 'Registro eliminado.')
    return redirect('maquinaria:registro_lista', proyecto_id=proyecto_id)


# ── Registros Maquinaria ──────────────────────────────────────────────

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

    import datetime
    return render(request, 'maquinaria/maq_maquinaria_detalle.html', {
        'proyecto':     proyecto,
        'maquinaria':   maquinaria,
        'liquidaciones': liquidaciones,
        'sin_liq':      sin_liq,
        'total_hm':     total_hm,
        'hoy':          datetime.date.today().strftime('%Y-%m'),
    })


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
            reg.propietario = maquinaria.propietario
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


def maq_registro_crear(request, proyecto_id):
    proyecto = get_object_or_404(Proyecto, pk=proyecto_id)
    form     = RegistroMaquinariaForm(
        proyecto=proyecto,
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
        reg.save()
        messages.success(request, 'Registro guardado.')
        if maq:
            return redirect('maquinaria:maq_detalle_maquinaria', proyecto_id=proyecto_id, maq_pk=maq.pk)
        return redirect('maquinaria:maq_registro_lista', proyecto_id=proyecto_id)
    return render(request, 'maquinaria/maq_registro_form.html', {
        'form':     form,
        'proyecto': proyecto,
        'titulo':   'Nuevo Registro de Maquinaria',
    })


def maq_registro_detalle(request, pk):
    registro = get_object_or_404(RegistroMaquinaria, pk=pk)
    return render(request, 'maquinaria/maq_registro_detalle.html', {
        'registro': registro,
        'proyecto': registro.proyecto,
    })


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
