from decimal import Decimal
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from apps.proyectos.models import Proyecto
from apps.registro.utils import log, notificar
from .models import Requerimiento, DetalleRequerimiento, ESTADOS_REQ
from .forms import RequerimientoForm, DetalleRequerimientoFormSet
from config.permisos import requiere, tiene, proyecto_visible


def _siguiente_numero(proyecto):
    ultimo = proyecto.requerimientos.order_by('-pk').first()
    if not ultimo:
        return '001'
    try:
        n = int(''.join(filter(str.isdigit, str(ultimo.numero))))
        return str(n + 1).zfill(3)
    except (ValueError, AttributeError):
        return str(proyecto.requerimientos.count() + 1).zfill(3)


def _siguiente_numero_global():
    total = Requerimiento.objects.count()
    return str(total + 1).zfill(4)


def _sync_snapshot(detalle):
    if detalle.insumo:
        if not detalle.descripcion:
            detalle.descripcion = detalle.insumo.descripcion
        if not detalle.unidad:
            detalle.unidad = detalle.insumo.unidad
        # Siempre actualizar código desde el insumo mientras el FK exista
        detalle.codigo = detalle.insumo.codigo or ''
    detalle.save()


@requiere('puede_crear_requerimientos', 'puede_aprobar_requerimientos')
@proyecto_visible
def lista(request, proyecto_id):
    proyecto = get_object_or_404(Proyecto, pk=proyecto_id)
    estado_sel = request.GET.get('estado', '')
    qs = proyecto.requerimientos.filter(es_ajuste=False).prefetch_related('detalles__insumo')
    if estado_sel:
        qs = qs.filter(estado=estado_sel)
    nuevos = proyecto.requerimientos.filter(
        estado__in=['APROBADO', 'PARCIAL'], aprobacion_vista=False
    )
    return render(request, 'requerimientos/lista.html', {
        'proyecto':    proyecto,
        'requerimientos': qs,
        'estados':     ESTADOS_REQ,
        'estado_sel':  estado_sel,
        'nuevos_aprobados': nuevos,
    })


@requiere('puede_aprobar_requerimientos')
@proyecto_visible
def bandeja_entrada(request, proyecto_id):
    """Bandeja del Administrador de Obra: lista los requerimientos en estado
    `SOLICITADO` que le mandó el Almacenero. Desde aquí puede abrir cada uno
    para editar/aprobar y enviar a Logística. Ver REGLAS_NEGOCIO.md §10.
    """
    proyecto = get_object_or_404(Proyecto, pk=proyecto_id)
    solicitudes = Requerimiento.objects.filter(
        proyecto=proyecto, estado='SOLICITADO'
    ).prefetch_related('detalles').order_by('-fecha', '-numero')
    return render(request, 'requerimientos/bandeja_entrada.html', {
        'proyecto': proyecto,
        'solicitudes': solicitudes,
    })


@requiere('puede_crear_requerimientos', 'puede_aprobar_requerimientos')
def detalle(request, pk):
    req = get_object_or_404(Requerimiento, pk=pk)
    if not req.aprobacion_vista and req.estado in ('APROBADO', 'PARCIAL'):
        req.aprobacion_vista = True
        req.save(update_fields=['aprobacion_vista'])
    return render(request, 'requerimientos/detalle.html', {
        'req': req, 'proyecto': req.proyecto,
    })


@requiere('puede_crear_requerimientos')
@proyecto_visible
def crear(request, proyecto_id):
    from apps.configuracion.models import ConfigEmpresa
    proyecto = get_object_or_404(Proyecto, pk=proyecto_id)
    empresa  = ConfigEmpresa.get()
    siguiente = _siguiente_numero(proyecto)
    siguiente_global = _siguiente_numero_global()
    modo_ajuste = request.GET.get('ajuste') == '1' or request.POST.get('modo_ajuste') == '1'
    if request.method == 'POST':
        form = RequerimientoForm(request.POST, proyecto=proyecto)
        formset = DetalleRequerimientoFormSet(
            request.POST, prefix='detalles',
            form_kwargs={'modo_ajuste': modo_ajuste},
        )
        accion = request.POST.get('accion', 'borrador')
        if form.is_valid() and formset.is_valid():
            req = form.save(commit=False)
            req.proyecto = proyecto
            req.es_ajuste = modo_ajuste
            puede_enviar = tiene(request.user, 'puede_aprobar_requerimientos')
            req.estado = 'ENVIADO' if accion == 'enviar' and puede_enviar else 'BORRADOR'
            req.numero = siguiente
            req.numero_global = siguiente_global
            req.save()
            for f in formset:
                if f.cleaned_data and not f.cleaned_data.get('DELETE'):
                    d = f.save(commit=False)
                    d.requerimiento = req
                    _sync_snapshot(d)
            tipo_txt = 'Ajuste' if modo_ajuste else 'Requerimiento'
            log(request, 'CREAR', 'Requerimientos',
                f'REQ-{req.numero} ({tipo_txt}) {"enviado" if req.estado == "ENVIADO" else "guardado como borrador"} en {proyecto.codigo}')
            if req.estado == 'ENVIADO':
                notificar(
                    f'Nuevo {tipo_txt.lower()} REQ-{req.numero}',
                    mensaje=f'Enviado por {request.user.get_full_name() or request.user.username} — {proyecto.codigo}. Pendiente en Logística.',
                    tipo='warning' if modo_ajuste else 'info',
                )
                messages.success(request, f'{tipo_txt} REQ-{req.numero} enviado a Logística.')
            else:
                messages.success(request, f'{tipo_txt} REQ-{req.numero} guardado como borrador.')
            return redirect('requerimientos:detalle', pk=req.pk)
    else:
        form = RequerimientoForm(proyecto=proyecto, initial={
            'numero': siguiente,
            'obra': proyecto.nombre,
            'solicitante': proyecto.responsable,
            'cargo_solicitante': proyecto.cargo_responsable,
            'sector_obra': proyecto.sector,
        })
        formset = DetalleRequerimientoFormSet(
            prefix='detalles',
            form_kwargs={'modo_ajuste': modo_ajuste},
        )
    return render(request, 'requerimientos/form.html', {
        'form': form, 'formset': formset, 'proyecto': proyecto,
        'empresa': empresa,
        'titulo': 'Nuevo Ajuste' if modo_ajuste else 'Nuevo Requerimiento',
        'siguiente_numero': siguiente,
        'numero_global': siguiente_global,
        'modo_ajuste': modo_ajuste,
    })


@requiere('puede_crear_requerimientos', 'puede_aprobar_requerimientos')
@proyecto_visible
def ajustes(request, proyecto_id):
    """Lista de requerimientos marcados como ajuste (adicionales fuera de presupuesto).
    Ver REGLAS_NEGOCIO.md §14."""
    proyecto = get_object_or_404(Proyecto, pk=proyecto_id)
    qs = (proyecto.requerimientos
          .filter(es_ajuste=True)
          .prefetch_related('detalles__insumo'))
    return render(request, 'requerimientos/ajustes.html', {
        'proyecto': proyecto,
        'requerimientos': qs,
    })


@requiere('puede_crear_requerimientos')
@proyecto_visible
def solicitar(request, proyecto_id):
    """Vista del Almacenero para crear requerimientos que van al Admin de Obra.

    Formulario atómico: se envía o se cancela, no hay borrador. El requerimiento
    nace en estado `SOLICITADO` y aparece en la Bandeja de Entrada del Admin de
    Obra. Ver REGLAS_NEGOCIO.md §10.
    """
    from apps.configuracion.models import ConfigEmpresa
    # El Admin de Obra usa su propia vista `crear` (con borrador). Si tiene
    # el permiso de aprobación, se le redirige para no confundir flujos.
    if tiene(request.user, 'puede_aprobar_requerimientos'):
        return redirect('requerimientos:crear', proyecto_id=proyecto_id)

    proyecto = get_object_or_404(Proyecto, pk=proyecto_id)
    empresa = ConfigEmpresa.get()
    siguiente = _siguiente_numero(proyecto)
    siguiente_global = _siguiente_numero_global()

    if request.method == 'POST':
        form = RequerimientoForm(request.POST, proyecto=proyecto)
        formset = DetalleRequerimientoFormSet(request.POST, prefix='detalles')
        if form.is_valid() and formset.is_valid():
            req = form.save(commit=False)
            req.proyecto = proyecto
            req.estado = 'SOLICITADO'
            req.numero = siguiente
            req.numero_global = siguiente_global
            req.save()
            for f in formset:
                if f.cleaned_data and not f.cleaned_data.get('DELETE'):
                    d = f.save(commit=False)
                    d.requerimiento = req
                    _sync_snapshot(d)
            log(request, 'CREAR', 'Requerimientos',
                f'REQ-{req.numero} solicitado por {request.user.get_full_name() or request.user.username} en {proyecto.codigo}')
            notificar(
                f'Nueva solicitud REQ-{req.numero}',
                mensaje=f'Solicitada por {request.user.get_full_name() or request.user.username} — {proyecto.codigo}. Pendiente en Bandeja de Entrada.',
                tipo='info',
            )
            messages.success(request, f'Solicitud REQ-{req.numero} enviada al Administrador de Obra.')
            return redirect('requerimientos:lista', proyecto_id=proyecto_id)
    else:
        # Cargo del Almacenero: viene de su PerfilUsuario.cargo; si está vacío,
        # cae al nombre del rol. NUNCA usar proyecto.cargo_responsable —
        # ver feedback-almacenero-req-propio: el requerimiento del Almacenero
        # debe reflejar sus datos, no los del responsable del proyecto.
        cargo_almacenero = ''
        try:
            cargo_almacenero = request.user.perfil.cargo or (
                request.user.perfil.rol.nombre if request.user.perfil.rol else ''
            )
        except AttributeError:
            pass

        form = RequerimientoForm(proyecto=proyecto, initial={
            'numero': siguiente,
            'obra': proyecto.nombre,
            'solicitante': request.user.get_full_name() or request.user.username,
            'cargo_solicitante': cargo_almacenero,
            'sector_obra': proyecto.sector,
        })
        formset = DetalleRequerimientoFormSet(prefix='detalles')

    return render(request, 'requerimientos/solicitar.html', {
        'form': form, 'formset': formset, 'proyecto': proyecto,
        'empresa': empresa,
        'titulo': 'Solicitar material',
        'siguiente_numero': siguiente,
        'numero_global': siguiente_global,
    })


@requiere('puede_crear_requerimientos', 'puede_aprobar_requerimientos')
def editar(request, pk):
    from apps.configuracion.models import ConfigEmpresa
    req = get_object_or_404(Requerimiento, pk=pk)
    proyecto = req.proyecto
    empresa  = ConfigEmpresa.get()
    if request.method == 'POST':
        form = RequerimientoForm(request.POST, instance=req, proyecto=proyecto)
        formset = DetalleRequerimientoFormSet(request.POST, instance=req, prefix='detalles')
        accion = request.POST.get('accion', '')
        if form.is_valid() and formset.is_valid():
            updated = form.save(commit=False)
            if accion == 'enviar' and req.estado in ('BORRADOR', 'SOLICITADO') and tiene(request.user, 'puede_aprobar_requerimientos'):
                origen = 'solicitud del Almacén' if req.estado == 'SOLICITADO' else 'borrador propio'
                updated.estado = 'ENVIADO'
                notificar(
                    f'Requerimiento REQ-{req.numero} enviado a Logística',
                    mensaje=f'Enviado por {request.user.get_full_name() or request.user.username} — {proyecto.codigo} (desde {origen}).',
                    tipo='info',
                )
            else:
                updated.estado = req.estado
            updated.save()
            for d in formset.save():
                _sync_snapshot(d)
            log(request, 'EDITAR', 'Requerimientos',
                f'REQ-{req.numero} editado en {proyecto.codigo}')
            messages.success(request, 'Requerimiento actualizado.')
            return redirect('requerimientos:detalle', pk=req.pk)
    else:
        form = RequerimientoForm(instance=req, proyecto=proyecto)
        formset = DetalleRequerimientoFormSet(instance=req, prefix='detalles')
    return render(request, 'requerimientos/form.html', {
        'form': form, 'formset': formset, 'proyecto': proyecto,
        'empresa': empresa,
        'titulo': 'Editar Requerimiento', 'req': req,
    })


@requiere('puede_aprobar_requerimientos')
def enviar(request, pk):
    from django.views.decorators.http import require_POST
    req = get_object_or_404(Requerimiento, pk=pk)
    if request.method == 'POST' and req.estado in ('BORRADOR', 'SOLICITADO'):
        estado_previo = req.estado
        req.estado = 'ENVIADO'
        req.save(update_fields=['estado'])
        origen = 'solicitud del Almacén' if estado_previo == 'SOLICITADO' else 'borrador propio'
        log(request, 'EDITAR', 'Requerimientos',
            f'REQ-{req.numero} enviado a Logística por {request.user.get_full_name() or request.user.username} (desde {origen})')
        notificar(
            f'Nuevo requerimiento REQ-{req.numero}',
            mensaje=f'Enviado por {request.user.get_full_name() or request.user.username} — {req.proyecto.codigo}. Pendiente en Logística.',
            tipo='info',
        )
        messages.success(request, f'REQ-{req.numero} enviado a Logística.')
    return redirect('requerimientos:detalle', pk=req.pk)


@requiere('puede_revisar_reqs_log')
def aprobar(request, pk):
    from django.views.decorators.http import require_POST
    req = get_object_or_404(Requerimiento, pk=pk)
    if request.method == 'POST' and req.estado == 'ENVIADO':
        req.estado = 'APROBADO'
        req.save()
        log(request, 'EDITAR', 'Requerimientos',
            f'REQ-{req.numero} aprobado por {request.user.get_full_name() or request.user.username}')
        notificar(
            f'Requerimiento REQ-{req.numero} aprobado',
            mensaje=f'Aprobado por {request.user.get_full_name() or request.user.username} en Logística.',
            tipo='success',
        )
        messages.success(request, f'Requerimiento REQ-{req.numero} aprobado.')
    next_url = request.POST.get('next', '')
    return redirect(next_url or 'requerimientos:detalle', pk=req.pk) if not next_url else redirect(next_url)


@requiere('puede_crear_requerimientos', 'puede_aprobar_requerimientos')
@proyecto_visible
def vs_atenciones(request, proyecto_id):
    proyecto = get_object_or_404(Proyecto, pk=proyecto_id)
    estados_incluidos = ['ENVIADO', 'EN_REVISION', 'APROBADO', 'PARCIAL', 'ATENDIDO']
    detalles = (DetalleRequerimiento.objects
                .filter(requerimiento__proyecto=proyecto,
                        requerimiento__estado__in=estados_incluidos)
                .select_related('insumo', 'requerimiento'))

    consolidado = {}
    for det in detalles:
        key = ('insumo', det.insumo_id) if det.insumo_id else ('desc', det.descripcion or det.codigo or '—')
        if key not in consolidado:
            if det.insumo:
                codigo      = det.insumo.codigo or det.codigo or '—'
                descripcion = det.insumo.descripcion
                unidad      = det.insumo.unidad or det.unidad
                tipo        = det.insumo.get_tipo_display() if hasattr(det.insumo, 'get_tipo_display') else ''
                original    = det.insumo.cantidad_total or Decimal('0')
            else:
                codigo      = det.codigo or '—'
                descripcion = det.descripcion
                unidad      = det.unidad
                tipo        = ''
                original    = Decimal('0')
            consolidado[key] = {
                'codigo': codigo, 'descripcion': descripcion,
                'unidad': unidad, 'tipo': tipo,
                'original': original,
                'solicitado': Decimal('0'), 'atendido': Decimal('0'),
                'observaciones': '',
                'insumo_id': det.insumo_id,
            }
        if det.requerimiento.estado in ['APROBADO', 'PARCIAL', 'ATENDIDO']:
            consolidado[key]['solicitado'] += det.cantidad_aprobada or Decimal('0')
        if det.requerimiento.estado == 'ATENDIDO':
            consolidado[key]['atendido'] += det.cantidad_aprobada or Decimal('0')
        if det.observacion:
            consolidado[key]['observaciones'] = det.observacion

    filas = []
    for item in consolidado.values():
        item['presupuestado'] = item['original']
        item['saldo'] = item['original'] - item['atendido']
        filas.append(item)
    filas.sort(key=lambda x: x['codigo'])

    return render(request, 'requerimientos/vs_atenciones.html', {
        'proyecto': proyecto,
        'filas': filas,
    })


@requiere('puede_crear_requerimientos', 'puede_aprobar_requerimientos')
@proyecto_visible
def vs_atenciones_insumo(request, proyecto_id, insumo_id):
    proyecto = get_object_or_404(Proyecto, pk=proyecto_id)
    estados_incluidos = ['ENVIADO', 'EN_REVISION', 'APROBADO', 'PARCIAL', 'ATENDIDO']
    detalles = (DetalleRequerimiento.objects
                .filter(insumo_id=insumo_id,
                        requerimiento__proyecto=proyecto,
                        requerimiento__estado__in=estados_incluidos)
                .select_related('requerimiento', 'insumo')
                .order_by('requerimiento__fecha', 'requerimiento__numero'))
    if not detalles.exists():
        from django.http import Http404
        raise Http404
    primer = detalles.first()
    insumo = primer.insumo
    return render(request, 'requerimientos/vs_atenciones_insumo.html', {
        'proyecto': proyecto,
        'insumo':   insumo,
        'detalles': detalles,
    })


@requiere('puede_aprobar_requerimientos')
def eliminar(request, pk):
    req = get_object_or_404(Requerimiento, pk=pk)
    proyecto = req.proyecto
    if request.method == 'POST':
        num = req.numero
        req.delete()
        log(request, 'ELIMINAR', 'Requerimientos',
            f'REQ-{num} eliminado de {proyecto.codigo}')
        messages.success(request, 'Requerimiento eliminado.')
        return redirect('requerimientos:lista', proyecto_id=proyecto.pk)
    return render(request, 'requerimientos/confirmar_eliminar.html', {
        'obj': req, 'proyecto': proyecto,
    })
