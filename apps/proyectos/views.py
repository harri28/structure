from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.contrib.auth.models import User
from .models import Proyecto, ProyectoMiembro
from .forms import ProyectoForm


def _es_admin(user):
    return user.is_superuser or (
        hasattr(user, 'perfil') and user.perfil.rol and user.perfil.rol.es_superadmin
    )


def _sin_dashboard(user):
    """True si el rol del usuario no tiene permiso para ver el dashboard general."""
    if _es_admin(user):
        return False
    try:
        rol = user.perfil.rol
        if rol is None:
            return False
        return not rol.puede_ver_dashboard
    except AttributeError:
        return False


def panel_dashboard(request):
    """Panel de Control general — solo superadmin. URL: /panel/dashboard/"""
    if not _es_admin(request.user):
        return redirect('proyectos:dashboard')
    from django.contrib.auth.models import User as DjangoUser
    proyectos      = Proyecto.objects.all()
    total_usuarios = DjangoUser.objects.count()
    activos        = proyectos.filter(estado='EJECUCION').count()
    return render(request, 'panel/dashboard.html', {
        'proyectos':      proyectos,
        'total_usuarios': total_usuarios,
        'activos':        activos,
    })


def proyecto_dashboard(request, pk):
    """Dashboard de KPIs para un proyecto específico. URL: /proyecto/<pk>/dashboard/"""
    proyecto   = get_object_or_404(Proyecto, pk=pk)
    es_miembro = ProyectoMiembro.objects.filter(proyecto=proyecto, usuario=request.user).exists()
    if not _es_admin(request.user) and not es_miembro:
        messages.error(request, 'No tienes acceso a ese proyecto.')
        return redirect('proyectos:dashboard')

    # Activar en sesión para que el resto de módulos funcione
    request.session['proyecto_id'] = proyecto.pk

    if _sin_dashboard(request.user):
        return redirect('logistica:dashboard', proyecto_id=proyecto.pk)

    from apps.requerimientos.models import Requerimiento
    from apps.almacen.models import Cotizacion, OrdenCompra, Entrada
    from apps.presupuesto.models import Presupuesto

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

    reqs_pendientes    = Requerimiento.objects.filter(proyecto=proyecto, estado='ENVIADO').count()
    cots_pendientes    = Cotizacion.objects.filter(proyecto=proyecto, estado='PENDIENTE').count()
    ocs_activas        = OrdenCompra.objects.filter(proyecto=proyecto, estado__in=['BORRADOR', 'ENVIADA']).count()
    reqs_recientes     = Requerimiento.objects.filter(proyecto=proyecto).order_by('-created_at')[:8]
    entradas_recientes = Entrada.objects.filter(proyecto=proyecto).order_by('-created_at')[:6]

    # ── KPIs de insumos ──────────────────────────────────────────────
    ins_n_total = ins_n_con_req = ins_n_sin_req = ins_n_excedidos = 0
    if presupuesto_obj:
        from django.db.models import Sum, Q, Value, DecimalField as DFld
        from django.db.models.functions import Coalesce
        qs_ins = presupuesto_obj.insumos.annotate(
            total_aprobado=Coalesce(
                Sum(
                    'detallerequerimiento__cantidad_requerida',
                    filter=Q(detallerequerimiento__requerimiento__estado__in=['APROBADO', 'ATENDIDO', 'PARCIAL']),
                ),
                Value(0, output_field=DFld()),
            )
        )
        for ins in qs_ins:
            ins_n_total += 1
            aprobado = ins.total_aprobado or 0
            if aprobado > 0:
                ins_n_con_req += 1
                if aprobado > (ins.cantidad or 0):
                    ins_n_excedidos += 1
            else:
                ins_n_sin_req += 1

    return render(request, 'dashboard.html', {
        'proyecto':            proyecto,
        'presupuesto_obj':     presupuesto_obj,
        'presupuesto_total':   presupuesto_total,
        'pres_detalle':        pres_detalle,
        'reqs_pendientes':     reqs_pendientes,
        'cots_pendientes':     cots_pendientes,
        'ocs_activas':         ocs_activas,
        'reqs_recientes':      reqs_recientes,
        'entradas_recientes':  entradas_recientes,
        'ins_n_total':         ins_n_total,
        'ins_n_con_req':       ins_n_con_req,
        'ins_n_sin_req':       ins_n_sin_req,
        'ins_n_excedidos':     ins_n_excedidos,
    })


def dashboard(request):
    """Router: redirige al panel correcto según rol y sesión."""
    pid = request.session.get('proyecto_id')
    if pid:
        try:
            Proyecto.objects.get(pk=pid)
            if _sin_dashboard(request.user):
                return redirect('logistica:dashboard', proyecto_id=pid)
            return redirect('proyecto_dashboard', pk=pid)
        except Proyecto.DoesNotExist:
            del request.session['proyecto_id']

    if _es_admin(request.user):
        return redirect('panel_dashboard')

    # Usuario normal — selector de proyectos
    proyectos = Proyecto.objects.filter(miembros__usuario=request.user)
    if proyectos.count() == 1:
        p = proyectos.first()
        request.session['proyecto_id'] = p.pk
        if _sin_dashboard(request.user):
            return redirect('logistica:dashboard', proyecto_id=p.pk)
        return redirect('proyecto_dashboard', pk=p.pk)

    return render(request, 'proyectos/selector.html', {
        'proyectos': proyectos,
        'es_admin':  False,
    })


def seleccionar(request, pk):
    """Guarda el proyecto en la sesión y va al dashboard del proyecto."""
    proyecto   = get_object_or_404(Proyecto, pk=pk)
    es_miembro = ProyectoMiembro.objects.filter(proyecto=proyecto, usuario=request.user).exists()
    if not _es_admin(request.user) and not es_miembro:
        messages.error(request, 'No tienes acceso a ese proyecto.')
        return redirect('proyectos:dashboard')
    request.session['proyecto_id'] = proyecto.pk
    return redirect('proyecto_dashboard', pk=pk)


def salir_proyecto(request):
    """Limpia el proyecto de la sesión."""
    request.session.pop('proyecto_id', None)
    if _es_admin(request.user):
        return redirect('panel_dashboard')
    return redirect('proyectos:dashboard')


def lista(request):
    """Lista admin de todos los proyectos."""
    if not (request.user.is_superuser or (
        hasattr(request.user, 'perfil') and
        request.user.perfil.rol and
        request.user.perfil.rol.es_superadmin
    )):
        return redirect('proyectos:dashboard')
    proyectos = Proyecto.objects.all()
    return render(request, 'proyectos/lista.html', {'proyectos': proyectos})


def detalle(request, pk):
    proyecto = get_object_or_404(Proyecto, pk=pk)
    miembros = proyecto.miembros.select_related('usuario__perfil__rol').all()
    ids_miembros = miembros.values_list('usuario_id', flat=True)
    usuarios_disponibles = User.objects.exclude(pk__in=ids_miembros).order_by('first_name', 'username')
    return render(request, 'proyectos/detalle.html', {
        'proyecto':             proyecto,
        'miembros':             miembros,
        'usuarios_disponibles': usuarios_disponibles,
    })


def personal(request, pk):
    proyecto = get_object_or_404(Proyecto, pk=pk)
    miembros = proyecto.miembros.select_related('usuario__perfil__rol').all()
    ids_miembros = miembros.values_list('usuario_id', flat=True)
    usuarios_disponibles = User.objects.exclude(pk__in=ids_miembros).order_by('first_name', 'username')
    return render(request, 'proyectos/personal.html', {
        'proyecto':             proyecto,
        'miembros':             miembros,
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
    if not (request.user.is_superuser or (
        hasattr(request.user, 'perfil') and
        request.user.perfil.rol and
        request.user.perfil.rol.es_superadmin
    )):
        return redirect('proyectos:dashboard')
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
        if request.session.get('proyecto_id') == proyecto.pk:
            request.session.pop('proyecto_id', None)
        proyecto.delete()
        Notificacion.objects.all().delete()
        messages.success(request, f'Proyecto "{nombre}" eliminado.')
        return redirect('proyectos:dashboard')
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
    return redirect('proyectos:personal', pk=pk)


def miembro_quitar(request, pk, usuario_id):
    proyecto = get_object_or_404(Proyecto, pk=pk)
    if request.method == 'POST':
        ProyectoMiembro.objects.filter(proyecto=proyecto, usuario_id=usuario_id).delete()
        messages.success(request, 'Miembro removido del proyecto.')
    return redirect('proyectos:personal', pk=pk)
