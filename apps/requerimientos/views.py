from decimal import Decimal
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from apps.proyectos.models import Proyecto
from apps.registro.utils import log, notificar
from .models import Requerimiento, DetalleRequerimiento, ESTADOS_REQ
from .forms import RequerimientoForm, DetalleRequerimientoFormSet


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


def lista(request, proyecto_id):
    proyecto = get_object_or_404(Proyecto, pk=proyecto_id)
    estado_sel = request.GET.get('estado', '')
    qs = proyecto.requerimientos.all()
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


def detalle(request, pk):
    req = get_object_or_404(Requerimiento, pk=pk)
    if not req.aprobacion_vista and req.estado in ('APROBADO', 'PARCIAL'):
        req.aprobacion_vista = True
        req.save(update_fields=['aprobacion_vista'])
    return render(request, 'requerimientos/detalle.html', {
        'req': req, 'proyecto': req.proyecto,
    })


def crear(request, proyecto_id):
    from apps.configuracion.models import ConfigEmpresa
    proyecto = get_object_or_404(Proyecto, pk=proyecto_id)
    empresa  = ConfigEmpresa.get()
    siguiente = _siguiente_numero(proyecto)
    siguiente_global = _siguiente_numero_global()
    if request.method == 'POST':
        form = RequerimientoForm(request.POST, proyecto=proyecto)
        formset = DetalleRequerimientoFormSet(request.POST, prefix='detalles')
        accion = request.POST.get('accion', 'borrador')
        if form.is_valid() and formset.is_valid():
            req = form.save(commit=False)
            req.proyecto = proyecto
            req.estado = 'ENVIADO' if accion == 'enviar' else 'BORRADOR'
            req.numero = siguiente
            req.numero_global = siguiente_global
            req.save()
            for f in formset:
                if f.cleaned_data and not f.cleaned_data.get('DELETE'):
                    d = f.save(commit=False)
                    d.requerimiento = req
                    _sync_snapshot(d)
            log(request, 'CREAR', 'Requerimientos',
                f'REQ-{req.numero} {"enviado" if req.estado == "ENVIADO" else "guardado como borrador"} en {proyecto.codigo}')
            if req.estado == 'ENVIADO':
                notificar(
                    f'Nuevo requerimiento REQ-{req.numero}',
                    mensaje=f'Enviado por {request.user.get_full_name() or request.user.username} — {proyecto.codigo}. Pendiente en Logística.',
                    tipo='info',
                )
                messages.success(request, f'Requerimiento REQ-{req.numero} enviado a Logística.')
            else:
                messages.success(request, f'Requerimiento REQ-{req.numero} guardado como borrador.')
            return redirect('requerimientos:detalle', pk=req.pk)
    else:
        form = RequerimientoForm(proyecto=proyecto, initial={
            'numero': siguiente,
            'obra': proyecto.nombre,
            'solicitante': proyecto.responsable,
        })
        formset = DetalleRequerimientoFormSet(prefix='detalles')
    return render(request, 'requerimientos/form.html', {
        'form': form, 'formset': formset, 'proyecto': proyecto,
        'empresa': empresa,
        'titulo': 'Nuevo Requerimiento', 'siguiente_numero': siguiente,
        'numero_global': siguiente_global,
    })


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
            if accion == 'enviar' and req.estado == 'BORRADOR':
                updated.estado = 'ENVIADO'
                notificar(
                    f'Requerimiento REQ-{req.numero} enviado',
                    mensaje=f'Enviado por {request.user.get_full_name() or request.user.username} — {proyecto.codigo}.',
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
                original = det.insumo.cantidad_total or Decimal('0')
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
            }
        if det.requerimiento.estado in ['ENVIADO', 'EN_REVISION']:
            consolidado[key]['solicitado'] += det.cantidad_requerida or Decimal('0')
        if det.requerimiento.estado in ['APROBADO', 'PARCIAL', 'ATENDIDO']:
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
