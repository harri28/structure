from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.contrib.auth.models import User
from .models import Proyecto, ProyectoMiembro
from .forms import ProyectoForm


def dashboard(request):
    from apps.requerimientos.models import Requerimiento
    from apps.almacen.models import Cotizacion, OrdenCompra, Entrada
    from apps.presupuesto.models import Presupuesto

    proyecto = Proyecto.objects.filter(activo=True).first()

    if not proyecto:
        return render(request, 'dashboard.html', {'sin_proyecto': True})

    # ── KPIs del proyecto activo ───────────────────────────────────
    presupuesto_obj   = None
    presupuesto_total = None
    pres_detalle      = {}
    try:
        presupuesto_obj   = proyecto.presupuesto
        presupuesto_total = presupuesto_obj.total_presupuesto()
        pres_detalle = {
            'costo_directo':    presupuesto_obj.costo_directo(),
            'gg_pct':           presupuesto_obj.gastos_generales_pct,
            'gastos_generales': presupuesto_obj.gastos_generales(),
            'ut_pct':           presupuesto_obj.utilidad_pct,
            'utilidad':         presupuesto_obj.utilidad(),
            'sub_total':        presupuesto_obj.sub_total(),
            'igv_pct':          presupuesto_obj.igv_pct,
            'igv':              presupuesto_obj.igv(),
            'total':            presupuesto_total,
        }
    except Presupuesto.DoesNotExist:
        pass

    reqs_pendientes = Requerimiento.objects.filter(proyecto=proyecto, estado='ENVIADO').count()
    cots_pendientes = Cotizacion.objects.filter(proyecto=proyecto, estado='PENDIENTE').count()
    ocs_activas     = OrdenCompra.objects.filter(
        proyecto=proyecto, estado__in=['BORRADOR', 'ENVIADA']
    ).count()

    # ── Actividad reciente del proyecto ───────────────────────────
    reqs_recientes     = (Requerimiento.objects
                          .filter(proyecto=proyecto)
                          .order_by('-created_at')[:8])
    entradas_recientes = (Entrada.objects
                          .filter(proyecto=proyecto)
                          .order_by('-created_at')[:6])

    return render(request, 'dashboard.html', {
        'proyecto':           proyecto,
        'presupuesto_obj':    presupuesto_obj,
        'presupuesto_total':  presupuesto_total,
        'pres_detalle':       pres_detalle,
        'reqs_pendientes':    reqs_pendientes,
        'cots_pendientes':    cots_pendientes,
        'ocs_activas':        ocs_activas,
        'reqs_recientes':     reqs_recientes,
        'entradas_recientes': entradas_recientes,
    })


def lista(request):
    proyectos = Proyecto.objects.all()
    return render(request, 'proyectos/lista.html', {'proyectos': proyectos})


def activar(request, pk):
    if request.method == 'POST':
        proyecto = get_object_or_404(Proyecto, pk=pk)
        proyecto.activo = True
        proyecto.save()
        messages.success(request, f'"{proyecto.nombre}" es ahora el proyecto activo.')
    return redirect('proyectos:lista')


def detalle(request, pk):
    proyecto = get_object_or_404(Proyecto, pk=pk)
    from django.contrib.auth.models import User
    miembros = proyecto.miembros.select_related('usuario__perfil__rol').all()
    ids_miembros = miembros.values_list('usuario_id', flat=True)
    usuarios_disponibles = User.objects.exclude(pk__in=ids_miembros).order_by('first_name', 'username')
    return render(request, 'proyectos/detalle.html', {
        'proyecto':            proyecto,
        'miembros':            miembros,
        'usuarios_disponibles': usuarios_disponibles,
    })


def _siguiente_codigo_proyecto():
    existentes = Proyecto.objects.filter(codigo__startswith='PRY-').values_list('codigo', flat=True)
    nums = []
    for c in existentes:
        try:
            nums.append(int(c[4:]))
        except ValueError:
            pass
    return f'PRY-{max(nums, default=0) + 1:03d}'


def crear(request):
    if request.method == 'POST':
        form = ProyectoForm(request.POST)
        if form.is_valid():
            proyecto = form.save()
            messages.success(request, f'Proyecto "{proyecto.nombre}" creado correctamente.')
            return redirect('proyectos:detalle', pk=proyecto.pk)
    else:
        form = ProyectoForm(initial={'codigo': _siguiente_codigo_proyecto()})
    return render(request, 'proyectos/form.html', {'form': form, 'titulo': 'Nuevo Proyecto'})


def editar(request, pk):
    proyecto = get_object_or_404(Proyecto, pk=pk)
    if request.method == 'POST':
        form = ProyectoForm(request.POST, instance=proyecto)
        if form.is_valid():
            form.save()
            messages.success(request, 'Proyecto actualizado correctamente.')
            return redirect('proyectos:detalle', pk=proyecto.pk)
    else:
        form = ProyectoForm(instance=proyecto)
    return render(request, 'proyectos/form.html', {'form': form, 'titulo': 'Datos Generales', 'proyecto': proyecto})


def eliminar(request, pk):
    proyecto = get_object_or_404(Proyecto, pk=pk)
    if request.method == 'POST':
        from apps.registro.models import Notificacion
        nombre = proyecto.nombre
        proyecto.delete()
        Notificacion.objects.all().delete()
        messages.success(request, f'Proyecto "{nombre}" eliminado.')
        return redirect('proyectos:lista')
    return render(request, 'proyectos/confirmar_eliminar.html', {'proyecto': proyecto})


# ── Equipo del proyecto ───────────────────────────────────────────

def miembro_agregar(request, pk):
    proyecto = get_object_or_404(Proyecto, pk=pk)
    if request.method == 'POST':
        usuario_id = request.POST.get('usuario_id')
        if usuario_id:
            usuario = get_object_or_404(User, pk=usuario_id)
            _, creado = ProyectoMiembro.objects.get_or_create(proyecto=proyecto, usuario=usuario)
            if creado:
                messages.success(request, f'{usuario.get_full_name() or usuario.username} agregado al equipo.')
            else:
                messages.warning(request, 'Ese usuario ya es miembro del proyecto.')
    return redirect('proyectos:detalle', pk=pk)


def miembro_quitar(request, pk, usuario_id):
    proyecto = get_object_or_404(Proyecto, pk=pk)
    if request.method == 'POST':
        ProyectoMiembro.objects.filter(proyecto=proyecto, usuario_id=usuario_id).delete()
        messages.success(request, 'Miembro removido del proyecto.')
    return redirect('proyectos:detalle', pk=pk)
