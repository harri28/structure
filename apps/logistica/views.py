from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.views.decorators.http import require_POST
from apps.proyectos.models import Proyecto
from apps.registro.utils import log, notificar
from .models import GuiaRemision, DetalleGuia, Transportista, ESTADOS_GUIA, MOTIVOS_TRASLADO
from .forms import GuiaRemisionForm, DetalleGuiaFormSet, TransportistaForm

# ── REALTIME POLL ──────────────────────────────────────────────────
# Para desactivar completamente: eliminar esta función + el path
# 'ping_reqs' en urls.py + el bloque <!-- REALTIME POLL --> en dashboard.html
def ping_reqs(request, proyecto_id):
    from django.http import JsonResponse
    from apps.requerimientos.models import Requerimiento
    ultimo_id = (
        Requerimiento.objects
        .filter(proyecto_id=proyecto_id, estado__in=['ENVIADO', 'EN_REVISION'])
        .order_by('-pk')
        .values_list('pk', flat=True)
        .first()
    ) or 0
    return JsonResponse({'ultimo_id': ultimo_id})
# ── fin REALTIME POLL ──────────────────────────────────────────────


def _get_proyecto(pk):
    return get_object_or_404(Proyecto, pk=pk)


# ── Dashboard ─────────────────────────────────────────────────────

def dashboard(request, proyecto_id):
    proyecto = _get_proyecto(proyecto_id)
    qs = GuiaRemision.objects.filter(proyecto=proyecto)
    recientes = qs.select_related('transportista').order_by('-creado_en')[:8]

    from apps.requerimientos.models import Requerimiento
    reqs_nuevos = Requerimiento.objects.filter(
        proyecto=proyecto, estado='ENVIADO'
    ).order_by('-created_at')

    return render(request, 'logistica/dashboard.html', {
        'proyecto':    proyecto,
        'total':       qs.count(),
        'pendientes':  qs.filter(estado='PENDIENTE').count(),
        'en_transito': qs.filter(estado='EN_TRANSITO').count(),
        'entregadas':  qs.filter(estado='ENTREGADO').count(),
        'recientes':   recientes,
        'reqs_nuevos': reqs_nuevos,
        'reqs_n':      reqs_nuevos.count(),
    })


# ── Guías de Remisión ─────────────────────────────────────────────

def guia_lista(request, proyecto_id):
    proyecto  = _get_proyecto(proyecto_id)
    qs        = GuiaRemision.objects.filter(proyecto=proyecto).select_related('transportista')
    estado_sel = request.GET.get('estado', '')
    if estado_sel:
        qs = qs.filter(estado=estado_sel)
    return render(request, 'logistica/guia_lista.html', {
        'proyecto':   proyecto,
        'guias':      qs,
        'estados':    ESTADOS_GUIA,
        'estado_sel': estado_sel,
    })


def guia_crear(request, proyecto_id):
    proyecto = _get_proyecto(proyecto_id)
    if request.method == 'POST':
        form    = GuiaRemisionForm(request.POST)
        formset = DetalleGuiaFormSet(request.POST)
        if form.is_valid() and formset.is_valid():
            guia          = form.save(commit=False)
            guia.proyecto = proyecto
            guia.save()
            formset.instance = guia
            formset.save()

            # Auto-crear Entrada en Almacén
            from apps.almacen.models import Entrada, DetalleEntrada
            entrada = Entrada.objects.create(
                proyecto=proyecto,
                guia=guia,
                numero_guia=guia.numero,
                fecha=guia.fecha_traslado,
                proveedor=guia.transportista.razon_social if guia.transportista else '',
                descripcion=guia.get_motivo_display(),
                observaciones=guia.observaciones,
            )
            for det in guia.detalles.all():
                DetalleEntrada.objects.create(
                    entrada=entrada,
                    descripcion=det.descripcion,
                    cantidad=det.cantidad,
                    unidad=det.unidad,
                )

            log(request, 'CREAR', 'Logística', f'Guía {guia.numero} creada en {proyecto.codigo}')
            notificar(f'Nueva guía de remisión {guia.numero}',
                      mensaje=f'{proyecto.codigo} — {guia.get_motivo_display()}. Entrada generada en Almacén.',
                      tipo='info')
            messages.success(request, f'Guía {guia.numero} creada. Entrada generada en Almacén.')
            return redirect('logistica:guia_detalle', pk=guia.pk)
    else:
        form    = GuiaRemisionForm()
        formset = DetalleGuiaFormSet()
    return render(request, 'logistica/guia_form.html', {
        'proyecto': proyecto, 'form': form, 'formset': formset,
        'titulo': 'Nueva Guía de Remisión',
    })


def guia_detalle(request, pk):
    guia = get_object_or_404(
        GuiaRemision.objects.select_related('proyecto', 'transportista')
                             .prefetch_related('detalles'),
        pk=pk,
    )
    return render(request, 'logistica/guia_detalle.html', {
        'guia':    guia,
        'proyecto': guia.proyecto,
        'estados': ESTADOS_GUIA,
    })


def guia_editar(request, pk):
    guia    = get_object_or_404(GuiaRemision, pk=pk)
    proyecto = guia.proyecto
    if request.method == 'POST':
        form    = GuiaRemisionForm(request.POST, instance=guia)
        formset = DetalleGuiaFormSet(request.POST, instance=guia)
        if form.is_valid() and formset.is_valid():
            form.save()
            formset.save()
            log(request, 'EDITAR', 'Logística', f'Guía {guia.numero} editada')
            messages.success(request, 'Guía actualizada.')
            return redirect('logistica:guia_detalle', pk=guia.pk)
    else:
        form    = GuiaRemisionForm(instance=guia)
        formset = DetalleGuiaFormSet(instance=guia)
    return render(request, 'logistica/guia_form.html', {
        'proyecto': proyecto, 'form': form, 'formset': formset,
        'guia': guia, 'titulo': f'Editar Guía {guia.numero}',
    })


@require_POST
def guia_estado(request, pk):
    guia  = get_object_or_404(GuiaRemision, pk=pk)
    nuevo = request.POST.get('estado', '')
    if nuevo in dict(ESTADOS_GUIA):
        guia.estado = nuevo
        guia.save(update_fields=['estado'])
        log(request, 'EDITAR', 'Logística',
            f'Guía {guia.numero} → {guia.get_estado_display()}')
        messages.success(request, f'Estado cambiado a {guia.get_estado_display()}.')
    return redirect('logistica:guia_detalle', pk=guia.pk)


@require_POST
def guia_eliminar(request, pk):
    guia       = get_object_or_404(GuiaRemision, pk=pk)
    proyecto_id = guia.proyecto_id
    numero     = guia.numero
    guia.delete()
    log(request, 'ELIMINAR', 'Logística', f'Guía {numero} eliminada')
    messages.success(request, f'Guía {numero} eliminada.')
    return redirect('logistica:guia_lista', proyecto_id=proyecto_id)


# ── Transportistas ────────────────────────────────────────────────

def transportista_lista(request):
    qs = Transportista.objects.all()
    return render(request, 'logistica/transportista_lista.html', {'transportistas': qs})


def transportista_crear(request):
    if request.method == 'POST':
        form = TransportistaForm(request.POST)
        if form.is_valid():
            t = form.save()
            log(request, 'CREAR', 'Logística', f'Transportista {t.razon_social} creado')
            messages.success(request, 'Transportista registrado.')
            return redirect('logistica:transportista_lista')
    else:
        form = TransportistaForm()
    return render(request, 'logistica/transportista_form.html',
                  {'form': form, 'titulo': 'Nuevo Transportista'})


def transportista_editar(request, pk):
    t = get_object_or_404(Transportista, pk=pk)
    if request.method == 'POST':
        form = TransportistaForm(request.POST, instance=t)
        if form.is_valid():
            form.save()
            log(request, 'EDITAR', 'Logística', f'Transportista {t.razon_social} editado')
            messages.success(request, 'Transportista actualizado.')
            return redirect('logistica:transportista_lista')
    else:
        form = TransportistaForm(instance=t)
    return render(request, 'logistica/transportista_form.html',
                  {'form': form, 'titulo': f'Editar — {t.razon_social}', 'obj': t})


# ── Sub-módulos Logística ─────────────────────────────────────────

def requerimientos_log(request, proyecto_id):
    from apps.requerimientos.models import Requerimiento, ESTADOS_REQ
    proyecto = _get_proyecto(proyecto_id)
    estado_sel = request.GET.get('estado', '')
    qs = Requerimiento.objects.filter(proyecto=proyecto).order_by('-fecha', '-numero')
    if estado_sel:
        qs = qs.filter(estado=estado_sel)
    return render(request, 'logistica/requerimientos.html', {
        'proyecto':    proyecto,
        'requerimientos': qs,
        'estados':     ESTADOS_REQ,
        'estado_sel':  estado_sel,
        'enviados':    Requerimiento.objects.filter(proyecto=proyecto, estado='ENVIADO').count(),
    })


def consolidados_log(request, proyecto_id):
    from apps.requerimientos.models import Requerimiento
    proyecto = _get_proyecto(proyecto_id)
    requerimientos = (Requerimiento.objects
                      .filter(proyecto=proyecto, estado__in=['APROBADO', 'PARCIAL'])
                      .order_by('-fecha', '-numero'))
    return render(request, 'logistica/req_consolidados.html', {
        'proyecto':       proyecto,
        'requerimientos': requerimientos,
    })


def _backfill_codigos(detalles, proyecto):
    """Rellena d.codigo desde el presupuesto cuando está vacío, y persiste el cambio."""
    from apps.requerimientos.models import DetalleRequerimiento
    try:
        codigo_por_desc = {
            ins.descripcion.strip().lower(): ins.codigo
            for ins in proyecto.presupuesto.insumos.all()
            if ins.codigo
        }
    except Exception:
        return
    to_update = []
    for d in detalles:
        if not d.codigo and d.descripcion:
            found = codigo_por_desc.get(d.descripcion.strip().lower(), '')
            if found:
                d.codigo = found
                to_update.append(d)
    if to_update:
        DetalleRequerimiento.objects.bulk_update(to_update, ['codigo'])


def req_detalle_log(request, proyecto_id, pk):
    from apps.requerimientos.models import Requerimiento
    proyecto = _get_proyecto(proyecto_id)
    req = get_object_or_404(Requerimiento, pk=pk, proyecto=proyecto)
    if req.estado == 'ENVIADO':
        req.estado = 'EN_REVISION'
        req.save(update_fields=['estado'])
        log(request, 'EDITAR', 'Logística',
            f'REQ-{req.numero} marcado En revisión por {request.user.get_full_name() or request.user.username}')
    detalles = list(req.detalles.select_related('insumo').all())
    _backfill_codigos(detalles, proyecto)
    return render(request, 'logistica/req_detalle.html', {
        'proyecto': proyecto,
        'req':      req,
    })


def _crear_guia_desde_req(req, proyecto, detalles, aprobaciones):
    """Crea una GuiaRemision automática con los ítems aprobados del requerimiento."""
    import datetime
    from .models import GuiaRemision, DetalleGuia
    from decimal import Decimal

    # Número auto: GR-{año}-{correlativo}
    anio = datetime.date.today().year
    prefijo = f'GR-{anio}-'
    ultimo = (GuiaRemision.objects
              .filter(proyecto=proyecto, numero__startswith=prefijo)
              .order_by('-numero').first())
    if ultimo:
        try:
            n = int(ultimo.numero.replace(prefijo, '')) + 1
        except ValueError:
            n = 1
    else:
        n = 1
    numero = f'{prefijo}{str(n).zfill(3)}'

    hoy = datetime.date.today()
    guia = GuiaRemision.objects.create(
        proyecto=proyecto,
        numero=numero,
        fecha_emision=hoy,
        fecha_traslado=hoy,
        motivo='TRASLADO_OBRA',
        origen='Almacén',
        destino=req.sector_obra or req.obra or proyecto.nombre,
        observaciones=f'Generada automáticamente desde REQ-{req.numero}',
    )

    for det in detalles:
        aprobada = aprobaciones.get(det.pk, Decimal('0'))
        if aprobada > 0:
            DetalleGuia.objects.create(
                guia=guia,
                descripcion=det.descripcion or (det.insumo.descripcion if det.insumo else '—'),
                unidad=det.unidad or '',
                cantidad=aprobada,
            )


def req_revisar_log(request, proyecto_id, pk):
    from decimal import Decimal, InvalidOperation
    from apps.requerimientos.models import Requerimiento
    from apps.almacen.models import Cotizacion

    proyecto = _get_proyecto(proyecto_id)
    req = get_object_or_404(Requerimiento, pk=pk, proyecto=proyecto)

    ESTADOS_EDITABLES = ('ENVIADO', 'EN_REVISION', 'APROBADO', 'PARCIAL')
    if req.estado not in ESTADOS_EDITABLES:
        messages.error(request, 'Este requerimiento no puede editarse en su estado actual.')
        return redirect('logistica:requerimientos_log', proyecto_id=proyecto_id)

    # Marcar como EN_REVISION si venía de ENVIADO
    if req.estado == 'ENVIADO':
        req.estado = 'EN_REVISION'
        req.save(update_fields=['estado'])

    cotizaciones = Cotizacion.objects.filter(proyecto=proyecto).order_by('-fecha')
    detalles = list(req.detalles.select_related('insumo').all())
    _backfill_codigos(detalles, proyecto)

    if request.method == 'POST':
        cot_id = request.POST.get('cotizacion_sistema') or None
        pdf = request.FILES.get('cotizacion_pdf') or None

        # Leer y validar cantidades aprobadas
        aprobaciones = {}
        errores = []
        for det in detalles:
            raw = request.POST.get(f'aprobada_{det.pk}', '').strip()
            try:
                aprobada = Decimal(raw) if raw else Decimal('0')
            except InvalidOperation:
                aprobada = Decimal('0')

            if aprobada < 0:
                errores.append(f'Ítem "{det.descripcion or det.pk}": la cantidad no puede ser negativa.')
            elif aprobada > det.cantidad_requerida:
                errores.append(
                    f'Ítem "{det.descripcion or det.pk}": '
                    f'cantidad aprobada ({aprobada}) supera la requerida ({det.cantidad_requerida}).'
                )
            else:
                aprobaciones[det.pk] = aprobada

        if errores:
            for e in errores:
                messages.error(request, e)
            return render(request, 'logistica/req_revisar.html', {
                'proyecto': proyecto, 'req': req,
                'detalles': detalles, 'cotizaciones': cotizaciones,
            })

        # Guardar cotización
        if cot_id:
            req.cotizacion_sistema_id = int(cot_id)
        if pdf:
            req.cotizacion_pdf = pdf

        # Guardar cantidades aprobadas por línea
        es_parcial = False
        for det in detalles:
            aprobada = aprobaciones[det.pk]
            det.cantidad_aprobada = aprobada
            det.save(update_fields=['cantidad_aprobada'])
            if aprobada < det.cantidad_requerida:
                es_parcial = True

        req.estado = 'PARCIAL' if es_parcial else 'APROBADO'
        req.aprobacion_vista = False
        req.save()

        tipo_estado = 'aprobado parcialmente' if es_parcial else 'aprobado'

        # Auto-crear Guía de Remisión con los ítems aprobados
        _crear_guia_desde_req(req, proyecto, detalles, aprobaciones)

        log(request, 'EDITAR', 'Logística',
            f'REQ-{req.numero} {tipo_estado} por {request.user.get_full_name() or request.user.username}')
        notificar(
            f'REQ-{req.numero} {tipo_estado}',
            mensaje=f'{proyecto.codigo} — revisado por Logística.',
            tipo='warning' if es_parcial else 'success',
        )
        # Notificación específica para Almacén
        notificar(
            f'Despacho REQ-{req.numero} listo para recibir',
            mensaje=f'{proyecto.codigo} — Los materiales aprobados han sido registrados en Guías de Remisión. Prepárate para recibirlos en almacén.',
            tipo='info',
        )
        messages.success(request, f'REQ-{req.numero} {tipo_estado} correctamente. Guía de Remisión generada.')
        return redirect('logistica:requerimientos_log', proyecto_id=proyecto_id)

    return render(request, 'logistica/req_revisar.html', {
        'proyecto':     proyecto,
        'req':          req,
        'detalles':     detalles,
        'cotizaciones': cotizaciones,
    })


def inventarios(request, proyecto_id):
    proyecto = _get_proyecto(proyecto_id)
    return render(request, 'logistica/inventarios.html', {'proyecto': proyecto})


def almacen_log(request, proyecto_id):
    proyecto = _get_proyecto(proyecto_id)
    return render(request, 'logistica/almacen_log.html', {'proyecto': proyecto})


def control_maquinaria(request, proyecto_id):
    proyecto = _get_proyecto(proyecto_id)
    return render(request, 'logistica/control_maquinaria.html', {'proyecto': proyecto})


def abastecimiento(request, proyecto_id):
    proyecto = _get_proyecto(proyecto_id)
    return render(request, 'logistica/abastecimiento.html', {'proyecto': proyecto})
