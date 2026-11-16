from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.contrib.auth.models import User
from .models import Proyecto, ProyectoMiembro
from .forms import ProyectoForm
from config.permisos import tiene, requiere, proyecto_visible


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


def _dashboard_del_rol(user, proyecto_id):
    """Redirige al dashboard propio del rol del usuario.

    Se usa como fallback cuando el usuario no tiene `puede_ver_dashboard` y por
    tanto no puede ver el dashboard general del proyecto. Prueba en orden:
    logística → almacén → perfil (último recurso, siempre accesible).
    """
    if tiene(user, 'puede_ver_logistica'):
        return redirect('logistica:dashboard', proyecto_id=proyecto_id)
    if tiene(user, 'puede_ver_almacen'):
        return redirect('almacen:dashboard', proyecto_id=proyecto_id)
    return redirect('configuracion:perfil')


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
        return _dashboard_del_rol(request.user, proyecto.pk)

    from apps.requerimientos.models import Requerimiento, ESTADOS_REQ
    from apps.almacen.models import Entrada, DetalleSalida
    from apps.presupuesto.models import Presupuesto
    from apps.maquinaria.models import Cuadrilla, RegistroMaquinaria, Asistencia, Trabajador
    from django.db.models import Sum, Q, Value, F, DecimalField as DFld
    from django.db.models.functions import Coalesce
    from django.utils import timezone
    from datetime import timedelta
    from decimal import Decimal

    # ── Presupuesto base ────────────────────────────────────────────
    presupuesto_obj   = None
    presupuesto_total = None
    try:
        presupuesto_obj   = proyecto.presupuesto
        presupuesto_total = presupuesto_obj.total_presupuesto()
    except Presupuesto.DoesNotExist:
        pass

    # ── Avance del presupuesto (costo ejecutado por aprobados) ──────
    avance_presupuesto = {'total': None, 'ejecutado': Decimal('0'), 'pct': 0}
    insumos_alerta = []
    top_insumos = []
    avance_partidas = []
    if presupuesto_obj:
        # Costo total y ejecutado por insumo
        qs_ins = presupuesto_obj.insumos.annotate(
            total_aprobado=Coalesce(
                Sum(
                    'detallerequerimiento__cantidad_requerida',
                    filter=Q(detallerequerimiento__requerimiento__estado__in=[
                        'APROBADO', 'COTIZADO', 'ATENDIDO', 'PARCIAL'
                    ]),
                ),
                Value(0, output_field=DFld()),
            )
        )
        costo_ejecutado = Decimal('0')
        costo_insumos_total = Decimal('0')
        for ins in qs_ins:
            precio = ins.costo_unitario or Decimal('0')
            cupo   = ins.cantidad_total or ins.cantidad or Decimal('0')
            aprob  = ins.total_aprobado or Decimal('0')
            costo_ejecutado     += Decimal(aprob) * precio
            costo_insumos_total += Decimal(cupo) * precio
            if cupo > 0 and aprob > 0:
                pct = float(Decimal(aprob) * 100 / cupo)
                if pct >= 80 or aprob > cupo:
                    insumos_alerta.append({
                        'nombre':  ins.descripcion[:60],
                        'unidad':  ins.unidad or '',
                        'cupo':    cupo,
                        'aprob':   aprob,
                        'pct':     round(pct, 1),
                        'excede':  aprob > cupo,
                    })
        insumos_alerta.sort(key=lambda x: (-x['pct'],))
        insumos_alerta = insumos_alerta[:10]
        avance_presupuesto['total']     = costo_insumos_total
        avance_presupuesto['ejecutado'] = costo_ejecutado
        avance_presupuesto['pct'] = round(
            float(costo_ejecutado * 100 / costo_insumos_total), 4
        ) if costo_insumos_total > 0 else 0

        # ── Top 10 insumos más consumidos (sumando salidas del proyecto) ──
        top_qs = (DetalleSalida.objects
                  .filter(salida__proyecto=proyecto, insumo__isnull=False)
                  .values('insumo__descripcion', 'insumo__unidad')
                  .annotate(total=Sum('cantidad'))
                  .order_by('-total')[:10])
        top_insumos = [{
            'nombre': (r['insumo__descripcion'] or '')[:55],
            'unidad': r['insumo__unidad'] or '',
            'total':  float(r['total'] or 0),
        } for r in top_qs]

        # ── Avance por partida (nivel 1 — grupos principales) ────────
        partidas_nivel1 = presupuesto_obj.partidas.filter(nivel=1).order_by('orden', 'codigo')[:8]
        for p in partidas_nivel1:
            # Insumos ligados a cualquier partida descendiente
            descendientes_ids = [p.pk]
            def _recolectar(nodo_pk):
                for hijo in Partida_hijos_de(nodo_pk, presupuesto_obj):
                    descendientes_ids.append(hijo)
                    _recolectar(hijo)
            try:
                _recolectar(p.pk)
            except Exception:
                pass
            ins_qs = presupuesto_obj.insumos.filter(
                recursopartida__partida_id__in=descendientes_ids
            ).distinct().annotate(
                aprob=Coalesce(
                    Sum('detallerequerimiento__cantidad_requerida',
                        filter=Q(detallerequerimiento__requerimiento__estado__in=[
                            'APROBADO', 'COTIZADO', 'ATENDIDO', 'PARCIAL'
                        ])),
                    Value(0, output_field=DFld()),
                )
            )
            tot = Decimal('0'); eje = Decimal('0')
            for i in ins_qs:
                precio = i.costo_unitario or Decimal('0')
                cupo   = i.cantidad_total or i.cantidad or Decimal('0')
                tot += Decimal(cupo) * precio
                eje += Decimal(i.aprob or 0) * precio
            pct = round(float(eje * 100 / tot), 1) if tot > 0 else 0
            avance_partidas.append({
                'codigo': p.codigo,
                'nombre': p.nombre[:60],
                'total':  tot,
                'ejec':   eje,
                'pct':    min(pct, 999),
            })

    # ── Requerimientos por estado ───────────────────────────────────
    from django.db.models import Count
    reqs_por_estado_qs = (Requerimiento.objects
                          .filter(proyecto=proyecto)
                          .values('estado')
                          .annotate(n=Count('id'))
                          .order_by('estado'))
    estados_map = dict(ESTADOS_REQ)
    reqs_por_estado = []
    total_reqs = 0
    for r in reqs_por_estado_qs:
        n = int(r['n'] or 0)
        total_reqs += n
        reqs_por_estado.append({
            'estado': r['estado'],
            'label':  estados_map.get(r['estado'], r['estado']),
            'n':      n,
        })

    # ── Cuadrillas / Maquinaria / Trabajadores ──────────────────────
    # Defensivo: si las migraciones de maquinaria no están aplicadas
    # (caso raro en local), devolvemos 0 en lugar de romper el dashboard.
    from django.db import ProgrammingError, OperationalError
    def _safe(fn, default=0):
        try:
            return fn()
        except (ProgrammingError, OperationalError):
            return default

    cuadrillas_activas   = _safe(lambda: Cuadrilla.objects.filter(proyecto=proyecto, activo=True).count())
    hace_30              = timezone.now().date() - timedelta(days=30)
    maquinas_activas     = _safe(lambda: (RegistroMaquinaria.objects
                                          .filter(proyecto=proyecto, fecha__gte=hace_30)
                                          .values('maquinaria').distinct().count()))
    trabajadores_activos = _safe(lambda: Trabajador.objects.filter(proyecto=proyecto, activo=True).count())

    # ── Asistencia semanal (últimos 7 días, Presente + Tardanza) ────
    hoy = timezone.now().date()
    desde = hoy - timedelta(days=6)
    asist_dict = _safe(lambda: {
        r['fecha']: int(r['n'] or 0)
        for r in (Asistencia.objects
                  .filter(trabajador__proyecto=proyecto,
                          fecha__gte=desde, fecha__lte=hoy,
                          estado='P')
                  .values('fecha')
                  .annotate(n=Sum(Value(1, output_field=DFld()))))
    }, default={})
    dias_es = ['L', 'M', 'X', 'J', 'V', 'S', 'D']
    asistencia_semana = []
    for i in range(7):
        d = desde + timedelta(days=i)
        asistencia_semana.append({
            'label':   f"{dias_es[d.weekday()]} {d.day:02d}",
            'fecha':   d.isoformat(),
            'n':       asist_dict.get(d, 0),
        })

    # ── Actividad reciente (tablas de abajo) ────────────────────────
    reqs_recientes     = Requerimiento.objects.filter(proyecto=proyecto).order_by('-created_at')[:8]
    entradas_recientes = Entrada.objects.filter(proyecto=proyecto).order_by('-created_at')[:6]

    # ── Insumos modificados (ampliaciones manuales del presupuesto) ─
    from apps.presupuesto.models import AmpliacionInsumo
    ampliaciones_recientes = (
        AmpliacionInsumo.objects
        .filter(insumo__presupuesto__proyecto=proyecto)
        .select_related('insumo', 'usuario')
        .order_by('-fecha')[:10]
    )

    return render(request, 'dashboard.html', {
        'proyecto':             proyecto,
        'presupuesto_obj':      presupuesto_obj,
        'presupuesto_total':    presupuesto_total,
        'avance_presupuesto':   avance_presupuesto,
        'insumos_alerta':       insumos_alerta,
        'top_insumos':          top_insumos,
        'avance_partidas':      avance_partidas,
        'reqs_por_estado':      reqs_por_estado,
        'total_reqs':           total_reqs,
        'cuadrillas_activas':   cuadrillas_activas,
        'maquinas_activas':     maquinas_activas,
        'trabajadores_activos': trabajadores_activos,
        'asistencia_semana':    asistencia_semana,
        'reqs_recientes':       reqs_recientes,
        'entradas_recientes':   entradas_recientes,
        'ampliaciones_recientes': ampliaciones_recientes,
    })


def Partida_hijos_de(partida_pk, presupuesto_obj):
    """Helper: devuelve los PKs de los hijos directos de una partida."""
    return list(
        presupuesto_obj.partidas.filter(padre_id=partida_pk).values_list('pk', flat=True)
    )


def dashboard(request):
    """Router: redirige al panel correcto según rol y sesión."""
    pid = request.session.get('proyecto_id')
    if pid:
        try:
            Proyecto.objects.get(pk=pid)
            if _sin_dashboard(request.user):
                return _dashboard_del_rol(request.user, pid)
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
            return _dashboard_del_rol(request.user, p.pk)
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


@requiere('puede_crear_proyectos', 'puede_eliminar_proyectos')
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


@requiere('puede_crear_proyectos', 'puede_eliminar_proyectos', 'puede_administrar_usuarios')
def detalle(request, pk):
    from apps.configuracion.models import Rol
    proyecto = get_object_or_404(Proyecto, pk=pk)
    miembros = proyecto.miembros.select_related('usuario__perfil__rol', 'rol').all()
    ids_miembros = miembros.values_list('usuario_id', flat=True)
    usuarios_disponibles = User.objects.exclude(pk__in=ids_miembros).order_by('first_name', 'username')
    roles_list = Rol.objects.all().order_by('nombre')

    # Jefe de Obra del equipo: primero por rol específico del miembro, luego por
    # rol global del perfil. Si hay varios, se toma el primero.
    jefe_obra = None
    for m in miembros:
        rol_efectivo = m.rol or (m.usuario.perfil.rol if hasattr(m.usuario, 'perfil') and m.usuario.perfil else None)
        if rol_efectivo and rol_efectivo.es_rol_jefe_obra:
            jefe_obra = m.usuario
            break

    # Valores de "Información del Proyecto": si hay Jefe de Obra con el campo
    # en su perfil, se usa eso; si no, cae al valor guardado en el proyecto.
    perfil_jo = getattr(jefe_obra, 'perfil', None) if jefe_obra else None
    info = {
        'cliente':     (perfil_jo.cliente     if perfil_jo and perfil_jo.cliente     else proyecto.cliente),
        'responsable': ((jefe_obra.get_full_name() or jefe_obra.username) if jefe_obra else proyecto.responsable),
        'ubicacion':   (perfil_jo.ubicacion   if perfil_jo and perfil_jo.ubicacion   else proyecto.ubicacion),
        'descripcion': (perfil_jo.descripcion if perfil_jo and perfil_jo.descripcion else proyecto.descripcion),
    }

    return render(request, 'proyectos/detalle.html', {
        'proyecto':             proyecto,
        'miembros':             miembros,
        'usuarios_disponibles': usuarios_disponibles,
        'roles_list':           roles_list,
        'jefe_obra':            jefe_obra,
        'info':                 info,
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


@requiere('puede_crear_proyectos')
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


@requiere('puede_crear_proyectos')
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


@requiere('puede_eliminar_proyectos')
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

@requiere('puede_administrar_usuarios')
def miembro_agregar(request, pk):
    proyecto = get_object_or_404(Proyecto, pk=pk)
    if request.method == 'POST':
        usuario_id = request.POST.get('usuario_id')
        rol_id     = request.POST.get('rol_id') or None
        if usuario_id:
            from apps.configuracion.models import Rol
            usuario = get_object_or_404(User, pk=usuario_id)
            rol = Rol.objects.filter(pk=rol_id).first() if rol_id else None
            miembro, creado = ProyectoMiembro.objects.get_or_create(
                proyecto=proyecto, usuario=usuario,
                defaults={'rol': rol},
            )
            if creado:
                sufijo = f' con rol "{rol.nombre}"' if rol else ''
                messages.success(request,
                    f'{usuario.get_full_name() or usuario.username} agregado al equipo{sufijo}.')
            else:
                messages.warning(request, 'Ese usuario ya es miembro del proyecto.')
    return redirect('proyectos:detalle', pk=pk)


@requiere('puede_administrar_usuarios')
def miembro_editar_rol(request, pk, usuario_id):
    """Cambia el rol específico de un miembro del proyecto. Responde JSON si
    el request es AJAX (X-Requested-With); en otro caso redirige como antes."""
    from django.http import JsonResponse
    proyecto = get_object_or_404(Proyecto, pk=pk)
    miembro  = get_object_or_404(ProyectoMiembro, proyecto=proyecto, usuario_id=usuario_id)
    es_ajax = request.headers.get('x-requested-with') == 'XMLHttpRequest'
    if request.method == 'POST':
        from apps.configuracion.models import Rol
        rol_id = request.POST.get('rol_id') or None
        rol_viejo_nombre = miembro.rol.nombre if miembro.rol else None
        miembro.rol = Rol.objects.filter(pk=rol_id).first() if rol_id else None
        miembro.save()
        rol_nuevo_nombre = miembro.rol.nombre if miembro.rol else None
        if rol_viejo_nombre != rol_nuevo_nombre:
            try:
                from apps.registro.utils import log
                log(request, 'EDITAR', 'Configuración',
                    f'Rol por proyecto: "{miembro.usuario.username}" en '
                    f'{proyecto.codigo} — "{rol_viejo_nombre or "sin rol"}" → '
                    f'"{rol_nuevo_nombre or "sin rol"}"')
            except Exception:
                pass
            if not es_ajax:
                messages.success(request,
                    f'Rol actualizado para {miembro.usuario.get_full_name() or miembro.usuario.username}.')
        if es_ajax:
            return JsonResponse({
                'ok': True,
                'rol_nombre': rol_nuevo_nombre or '',
                'tiene_rol': bool(miembro.rol_id),
            })
    return redirect('proyectos:detalle', pk=pk)


@requiere('puede_administrar_usuarios')
def miembro_quitar(request, pk, usuario_id):
    proyecto = get_object_or_404(Proyecto, pk=pk)
    if request.method == 'POST':
        ProyectoMiembro.objects.filter(proyecto=proyecto, usuario_id=usuario_id).delete()
        messages.success(request, 'Miembro removido del proyecto.')
    return redirect('proyectos:detalle', pk=pk)


@requiere('puede_eliminar_proyectos')
def proyecto_restablecer(request, pk):
    if not _es_admin(request.user):
        return redirect('proyectos:lista')

    proyecto = get_object_or_404(Proyecto, pk=pk)

    from apps.requerimientos.models import Requerimiento, DetalleRequerimiento
    from apps.almacen.models import Entrada, Salida, Cotizacion, OrdenCompra
    from apps.logistica.models import GuiaRemision
    from apps.maquinaria.models import (
        RegistroDiario, RegistroMaquinaria, Liquidacion,
        Trabajador, DocumentoTrabajador, Cuadrilla, IntegranteCuadrilla, Asistencia,
    )
    from apps.presupuesto.models import Presupuesto, Partida, InsumoPresupuesto

    def _count(qs):
        try:
            return qs.count()
        except Exception:
            return 0

    modulos = {
        'presupuesto': {
            'nombre': 'Presupuesto',
            'icono': 'bi-table',
            'color': '#6366f1',
            'descripcion': 'Partidas, insumos, ACU, modificaciones, ampliaciones y cambios de nombre de insumo.',
            'count': _count(Partida.objects.filter(presupuesto__proyecto=proyecto)),
        },
        'requerimientos': {
            'nombre': 'Requerimientos',
            'icono': 'bi-file-earmark-text',
            'color': '#f59e0b',
            'descripcion': 'Requerimientos, sus ítems e historial de revisión (aprobaciones, sustituciones, anulaciones).',
            'count': _count(Requerimiento.objects.filter(proyecto=proyecto)),
        },
        'cotizaciones': {
            'nombre': 'Cotizaciones y OC',
            'icono': 'bi-tags',
            'color': '#10b981',
            'descripcion': 'Cotizaciones del proyecto con sus ítems y órdenes de compra. No afecta al stock en obra.',
            'count': _count(Cotizacion.objects.filter(proyecto=proyecto)) + _count(OrdenCompra.objects.filter(proyecto=proyecto)),
        },
        'almacen': {
            'nombre': 'Almacén',
            'icono': 'bi-box-seam',
            'color': '#3b82f6',
            'descripcion': 'Entradas y salidas de materiales registradas por el Almacenero.',
            'count': _count(Entrada.objects.filter(proyecto=proyecto)) + _count(Salida.objects.filter(proyecto=proyecto)),
        },
        'logistica': {
            'nombre': 'Logística — Aprobaciones',
            'icono': 'bi-clipboard-check',
            'color': '#0ea5e9',
            'descripcion': 'Revierte estados y aprobaciones de requerimientos, restaura contadores de insumos (stock en obra) y borra guías de remisión asociadas.',
            'count': _count(Requerimiento.objects.filter(proyecto=proyecto, estado__in=['APROBADO', 'COTIZADO', 'PARCIAL', 'ATENDIDO'])),
        },
        'guias': {
            'nombre': 'Guías de Remisión',
            'icono': 'bi-file-earmark-arrow-right',
            'color': '#8b5cf6',
            'descripcion': 'Guías de remisión del proyecto (sin tocar aprobaciones ni cotizaciones). Devuelve el stock descontado.',
            'count': _count(GuiaRemision.objects.filter(proyecto=proyecto)),
        },
        'personal': {
            'nombre': 'Personal (Trabajadores)',
            'icono': 'bi-person-badge',
            'color': '#14b8a6',
            'descripcion': 'Trabajadores de obra + documentos adjuntos (CV, SCTR, etc.). Cascada: asignaciones a cuadrillas y asistencias.',
            'count': _count(Trabajador.objects.filter(proyecto=proyecto)),
        },
        'cuadrillas': {
            'nombre': 'Cuadrillas',
            'icono': 'bi-diagram-3',
            'color': '#2563eb',
            'descripcion': 'Frentes de trabajo del proyecto y asignaciones de personal.',
            'count': _count(Cuadrilla.objects.filter(proyecto=proyecto)),
        },
        'asistencia': {
            'nombre': 'Asistencia',
            'icono': 'bi-calendar-check',
            'color': '#0891b2',
            'descripcion': 'Marcas de asistencia diaria del personal (Presente/Falta/Tardanza/etc.).',
            'count': _count(Asistencia.objects.filter(trabajador__proyecto=proyecto)),
        },
        'maquinaria': {
            'nombre': 'Maquinaria',
            'icono': 'bi-truck',
            'color': '#ec4899',
            'descripcion': 'Registros diarios de maquinaria y liquidaciones del proyecto.',
            'count': _count(RegistroDiario.objects.filter(proyecto=proyecto)) + _count(RegistroMaquinaria.objects.filter(proyecto=proyecto)),
        },
    }

    if request.method == 'POST':
        confirmacion = request.POST.get('confirmacion', '').strip()
        if confirmacion != proyecto.codigo:
            messages.error(request, f'El código ingresado no coincide. Debes escribir exactamente: {proyecto.codigo}')
            return render(request, 'proyectos/restablecer.html', {'proyecto': proyecto, 'modulos': modulos})

        seleccionados = request.POST.getlist('modulos')
        if not seleccionados:
            messages.warning(request, 'No seleccionaste ningún módulo.')
            return render(request, 'proyectos/restablecer.html', {'proyecto': proyecto, 'modulos': modulos})

        eliminados = []

        if 'presupuesto' in seleccionados:
            try:
                proyecto.presupuesto.delete()
                eliminados.append('Presupuesto')
            except Presupuesto.DoesNotExist:
                pass

        if 'requerimientos' in seleccionados:
            Requerimiento.objects.filter(proyecto=proyecto).delete()
            eliminados.append('Requerimientos')

        if 'cotizaciones' in seleccionados:
            Cotizacion.objects.filter(proyecto=proyecto).delete()
            OrdenCompra.objects.filter(proyecto=proyecto).delete()
            eliminados.append('Cotizaciones y OC')

        if 'almacen' in seleccionados:
            Entrada.objects.filter(proyecto=proyecto).delete()
            Salida.objects.filter(proyecto=proyecto).delete()
            eliminados.append('Almacén')

        if 'logistica' in seleccionados:
            # Restaurar contadores usando cantidad_total (fuente de verdad del presupuesto)
            for ins in InsumoPresupuesto.objects.filter(presupuesto__proyecto=proyecto):
                ins.cantidad = ins.cantidad_total
                ins.save(update_fields=['cantidad'])
            # Limpiar aprobaciones en todos los detalles del proyecto
            DetalleRequerimiento.objects.filter(
                requerimiento__proyecto=proyecto
            ).update(cantidad_aprobada=None)
            # Revertir estado de requerimientos revisados a ENVIADO
            Requerimiento.objects.filter(
                proyecto=proyecto,
                estado__in=['APROBADO', 'COTIZADO', 'PARCIAL', 'ATENDIDO'],
            ).update(estado='ENVIADO', aprobacion_vista=False)
            # Eliminar guías de remisión del proyecto
            GuiaRemision.objects.filter(proyecto=proyecto).delete()
            eliminados.append('Logística')

        if 'guias' in seleccionados:
            # Devuelve al stock lo descontado por cada guía despachada antes de borrarla.
            from apps.logistica.views import _revertir_descuento, ESTADOS_GUIA_DESPACHADA
            for g in GuiaRemision.objects.filter(proyecto=proyecto):
                if g.estado in ESTADOS_GUIA_DESPACHADA:
                    _revertir_descuento(g)
            GuiaRemision.objects.filter(proyecto=proyecto).delete()
            eliminados.append('Guías de Remisión')

        if 'personal' in seleccionados:
            # Cascada: borra DocumentoTrabajador, IntegranteCuadrilla y Asistencia asociados
            Trabajador.objects.filter(proyecto=proyecto).delete()
            eliminados.append('Personal (Trabajadores)')

        if 'cuadrillas' in seleccionados:
            # Cascada: borra IntegranteCuadrilla
            Cuadrilla.objects.filter(proyecto=proyecto).delete()
            eliminados.append('Cuadrillas')

        if 'asistencia' in seleccionados:
            Asistencia.objects.filter(trabajador__proyecto=proyecto).delete()
            eliminados.append('Asistencia')

        if 'maquinaria' in seleccionados:
            RegistroDiario.objects.filter(proyecto=proyecto).delete()
            RegistroMaquinaria.objects.filter(proyecto=proyecto).delete()
            Liquidacion.objects.filter(proyecto=proyecto).delete()
            eliminados.append('Maquinaria')

        messages.success(request, f'Restablecido: {", ".join(eliminados)}.')
        return redirect('proyectos:detalle', pk=pk)

    return render(request, 'proyectos/restablecer.html', {
        'proyecto': proyecto,
        'modulos':  modulos,
    })
