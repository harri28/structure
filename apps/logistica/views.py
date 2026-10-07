from decimal import Decimal
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.views.decorators.http import require_POST
from apps.proyectos.models import Proyecto
from apps.registro.utils import log, notificar
from .models import GuiaRemision, DetalleGuia, Transportista, ESTADOS_GUIA, MOTIVOS_TRASLADO
from .forms import GuiaRemisionForm, DetalleGuiaFormSet, TransportistaForm
from config.permisos import requiere, proyecto_visible

# ── REALTIME POLL ──────────────────────────────────────────────────
# Para desactivar completamente: eliminar esta función + el path
# 'ping_reqs' en urls.py + el bloque <!-- REALTIME POLL --> en dashboard.html
@requiere('puede_revisar_reqs_log')
@proyecto_visible
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

@requiere('puede_ver_logistica')
@proyecto_visible
def dashboard(request, proyecto_id):
    proyecto = _get_proyecto(proyecto_id)
    # Excluir ANULADAS del listado y del total (siguen existiendo en la BD para trazabilidad)
    qs = GuiaRemision.objects.filter(proyecto=proyecto).exclude(estado='ANULADO')
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

@requiere('puede_gestionar_logistica')
@proyecto_visible
def guia_lista(request, proyecto_id):
    proyecto = _get_proyecto(proyecto_id)
    qs = (GuiaRemision.objects.filter(proyecto=proyecto)
          .select_related('transportista', 'requerimiento'))
    return render(request, 'logistica/guia_lista.html', {
        'proyecto': proyecto,
        'guias':    qs,
    })


def _registrar_entrada_almacen(guia, proyecto):
    """Crea el registro de Entrada en Almacén a partir de la guía."""
    from apps.almacen.models import Entrada, DetalleEntrada
    entrada = Entrada.objects.create(
        proyecto=proyecto,
        guia=guia,
        numero_guia=guia.numero,
        fecha=guia.fecha_traslado,
        proveedor=guia.transportista.razon_social if guia.transportista else '',
        descripcion=guia.motivo_texto,
        observaciones=guia.observaciones,
    )
    for det in guia.detalles.all():
        DetalleEntrada.objects.create(
            entrada=entrada,
            descripcion=det.descripcion,
            cantidad=det.cantidad,
            unidad=det.unidad,
        )


def _siguiente_numero_guia(proyecto):
    """Siguiente correlativo de guía del proyecto: GR-{año}-{nnn}."""
    import datetime
    prefijo = f'GR-{datetime.date.today().year}-'
    mayor = 0
    for numero in (GuiaRemision.objects
                   .filter(proyecto=proyecto, numero__startswith=prefijo)
                   .values_list('numero', flat=True)):
        try:
            mayor = max(mayor, int(numero.replace(prefijo, '')))
        except ValueError:
            continue
    return f'{prefijo}{str(mayor + 1).zfill(3)}'


ESTADOS_GUIA_ACTIVA = ['PENDIENTE', 'EN_TRANSITO', 'ENTREGADO']
ESTADOS_GUIA_DESPACHADA = ['EN_TRANSITO', 'ENTREGADO']


def _cotizaciones_disponibles(proyecto):
    """Cotizaciones APROBADAS del proyecto que aún no viajan en una guía activa."""
    from apps.almacen.models import Cotizacion
    return (Cotizacion.objects
            .filter(proyecto=proyecto, estado='APROBADA')
            .exclude(guias_remision__estado__in=ESTADOS_GUIA_ACTIVA)
            .select_related('requerimiento_origen')
            .prefetch_related('detalles__insumo')
            .order_by('-fecha', '-pk'))


def _descripcion_item(d):
    return (d.descripcion or (d.insumo.descripcion if d.insumo_id else '') or '—')[:400]


def _unidad_item(d):
    return (d.unidad or (d.insumo.unidad if d.insumo_id and d.insumo.unidad else ''))[:20]


def _despachar_cotizaciones(guia, cotizaciones):
    """Copia los ítems de las cotizaciones a la guía y descuenta el stock en obra
    (InsumoPresupuesto.cantidad) por la cantidad de cada ítem. Nunca baja de cero."""
    from apps.presupuesto.models import InsumoPresupuesto
    descuentos = {}
    for cot in cotizaciones:
        for d in cot.detalles.all():
            DetalleGuia.objects.create(
                guia=guia,
                descripcion=_descripcion_item(d),
                unidad=_unidad_item(d),
                cantidad=d.cantidad.quantize(Decimal('0.001')),
            )
            if d.insumo_id:
                descuentos[d.insumo_id] = descuentos.get(d.insumo_id, Decimal('0')) + d.cantidad
    for ins in InsumoPresupuesto.objects.select_for_update().filter(pk__in=descuentos):
        ins.cantidad = max(Decimal('0'), ins.cantidad - descuentos[ins.pk])
        ins.save(update_fields=['cantidad'])


def _revertir_descuento(guia):
    """Devuelve al stock en obra lo descontado por la guía (al anularla o eliminarla).
    Nunca supera la cantidad original importada (cantidad_total)."""
    from apps.presupuesto.models import InsumoPresupuesto
    devoluciones = {}
    for cot in guia.cotizaciones.prefetch_related('detalles'):
        for d in cot.detalles.all():
            if d.insumo_id:
                devoluciones[d.insumo_id] = devoluciones.get(d.insumo_id, Decimal('0')) + d.cantidad
    for ins in InsumoPresupuesto.objects.select_for_update().filter(pk__in=devoluciones):
        nueva = ins.cantidad + devoluciones[ins.pk]
        if ins.cantidad_total:
            nueva = min(ins.cantidad_total, nueva)
        ins.cantidad = nueva
        ins.save(update_fields=['cantidad'])


def _clave_item(insumo_id, descripcion):
    return ('i', insumo_id) if insumo_id else ('d', (descripcion or '').strip().lower())


def _recalcular_estado_req(req):
    """Estado del requerimiento según cotizaciones aprobadas y guías despachadas:
    todo salió en guías -> ATENDIDO; salió algo -> PARCIAL; todas las cotizaciones
    APROBADAS cubren lo aprobado sin aún haber guía -> COTIZADO; en otro caso vuelve
    al estado de aprobación (APROBADO / PARCIAL si se aprobó menos de lo requerido)."""
    from apps.almacen.models import DetalleCotizacion
    if req.estado not in ('APROBADO', 'COTIZADO', 'PARCIAL', 'ATENDIDO'):
        return
    aprobado = {}
    aprobado_total_igual_requerido = True
    for det in req.detalles.all():
        if det.cantidad_aprobada and det.cantidad_aprobada > 0:
            k = _clave_item(det.insumo_id, det.descripcion)
            aprobado[k] = aprobado.get(k, Decimal('0')) + det.cantidad_aprobada
        if (det.cantidad_aprobada or Decimal('0')) < det.cantidad_requerida:
            aprobado_total_igual_requerido = False

    despachado = {}
    items = (DetalleCotizacion.objects
             .filter(cotizacion__requerimiento_origen=req,
                     cotizacion__guias_remision__estado__in=ESTADOS_GUIA_DESPACHADA)
             .distinct())
    for d in items:
        k = _clave_item(d.insumo_id, d.descripcion)
        despachado[k] = despachado.get(k, Decimal('0')) + d.cantidad

    cotizado = {}
    for d in DetalleCotizacion.objects.filter(
            cotizacion__requerimiento_origen=req,
            cotizacion__estado='APROBADA'):
        k = _clave_item(d.insumo_id, d.descripcion)
        cotizado[k] = cotizado.get(k, Decimal('0')) + d.cantidad

    hay_despacho   = any(v > 0 for v in despachado.values())
    todo_despachado = bool(aprobado) and all(despachado.get(k, Decimal('0')) >= v for k, v in aprobado.items())
    todo_cotizado   = bool(aprobado) and all(cotizado.get(k,   Decimal('0')) >= v for k, v in aprobado.items())

    if todo_despachado:
        nuevo = 'ATENDIDO'
    elif hay_despacho:
        nuevo = 'PARCIAL'
    elif todo_cotizado:
        nuevo = 'COTIZADO'
    else:
        nuevo = 'APROBADO' if aprobado_total_igual_requerido else 'PARCIAL'
    if nuevo != req.estado:
        req.estado = nuevo
        req.save(update_fields=['estado'])


def _reqs_de_guia(guia):
    return {c.requerimiento_origen for c in guia.cotizaciones.select_related('requerimiento_origen')
            if c.requerimiento_origen_id}


@requiere('puede_gestionar_logistica')
@proyecto_visible
def guia_crear(request, proyecto_id):
    import datetime
    from django.db import transaction
    proyecto = _get_proyecto(proyecto_id)
    disponibles = list(_cotizaciones_disponibles(proyecto))
    seleccion = []

    if request.method == 'POST':
        post = request.POST.copy()
        post['numero'] = _siguiente_numero_guia(proyecto)              # siempre automático
        post['fecha_emision'] = datetime.date.today().strftime('%Y-%m-%d')
        form = GuiaRemisionForm(post)

        ids = []
        for raw in request.POST.getlist('cotizaciones'):
            if raw.isdigit() and int(raw) not in ids:
                ids.append(int(raw))
        elegidas = [c for c in disponibles if c.pk in ids]
        seleccion = [c.pk for c in elegidas]

        cots_ok = bool(elegidas) and len(elegidas) == len(ids)
        if not ids:
            messages.error(request, 'Selecciona al menos una cotización aprobada.')
        elif not cots_ok:
            messages.error(request, 'Alguna cotización ya no está disponible (no está aprobada o ya viaja en otra guía).')

        if form.is_valid() and cots_ok:
            with transaction.atomic():
                guia = form.save(commit=False)
                guia.proyecto = proyecto
                guia.estado = 'EN_TRANSITO'
                guia.save()
                guia.cotizaciones.set(elegidas)
                _despachar_cotizaciones(guia, elegidas)
                for req in _reqs_de_guia(guia):
                    _recalcular_estado_req(req)
            # NOTA: la Entrada no se crea automáticamente. El Almacenero la registra
            # manualmente desde Almacén → Guías → Registrar guía.
            log(request, 'CREAR', 'Logística', f'Guía {guia.numero} despachada en {proyecto.codigo}')
            notificar(
                f'Nueva Guía {guia.numero}',
                mensaje=f'{proyecto.codigo} — Despachada por Logística. Registrá su recepción.',
                tipo='info',
                url=f'/almacen/proyecto/{proyecto.pk}/guias/',
            )
            messages.success(request, f'Guía {guia.numero} generada.')
            return redirect('logistica:guia_detalle', pk=guia.pk)
    else:
        form = GuiaRemisionForm(initial={'numero': _siguiente_numero_guia(proyecto)})

    cotizaciones_data = [{
        'pk': c.pk,
        'numero': f'COT{c.numero}',
        'proveedor': c.proveedor or '',
        'req': f'REQ{c.requerimiento_origen.numero}' if c.requerimiento_origen_id else '',
        'items': [{
            'descripcion': _descripcion_item(d),
            'unidad': _unidad_item(d),
            'cantidad': str(d.cantidad.quantize(Decimal('0.001')).normalize()),
        } for d in c.detalles.all()],
    } for c in disponibles]

    return render(request, 'logistica/guia_form.html', {
        'proyecto': proyecto, 'form': form,
        'cotizaciones_data': cotizaciones_data,
        'cotizaciones_seleccion': seleccion,
        'titulo': 'Nueva Guía de Remisión',
    })


@requiere('puede_gestionar_logistica')
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


@requiere('puede_gestionar_logistica')
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
@requiere('puede_gestionar_logistica')
def guia_estado(request, pk):
    from django.db import transaction
    guia  = get_object_or_404(GuiaRemision, pk=pk)
    nuevo = request.POST.get('estado', '')
    if nuevo in dict(ESTADOS_GUIA) and nuevo != guia.estado:
        anterior = guia.estado
        tiene_cots = guia.cotizaciones.exists()
        if tiene_cots and anterior == 'ANULADO':
            messages.error(request, 'Una guía anulada no se puede reactivar; genera una nueva.')
            return redirect('logistica:guia_detalle', pk=guia.pk)
        with transaction.atomic():
            guia.estado = nuevo
            guia.save(update_fields=['estado'])
            if tiene_cots:
                if nuevo == 'ANULADO' and anterior in ESTADOS_GUIA_DESPACHADA:
                    _revertir_descuento(guia)
                for req in _reqs_de_guia(guia):
                    _recalcular_estado_req(req)
        log(request, 'EDITAR', 'Logística',
            f'Guía {guia.numero} → {guia.get_estado_display()}')
        messages.success(request, f'Estado cambiado a {guia.get_estado_display()}.')
    return redirect('logistica:guia_detalle', pk=guia.pk)


@require_POST
@requiere('puede_gestionar_logistica')
def guia_eliminar(request, pk):
    from django.db import transaction
    guia       = get_object_or_404(GuiaRemision, pk=pk)
    proyecto_id = guia.proyecto_id
    numero     = guia.numero
    with transaction.atomic():
        reqs = _reqs_de_guia(guia)
        if guia.estado in ESTADOS_GUIA_DESPACHADA:
            _revertir_descuento(guia)
        guia.delete()
        for req in reqs:
            _recalcular_estado_req(req)
    log(request, 'ELIMINAR', 'Logística', f'Guía {numero} eliminada')
    messages.success(request, f'Guía {numero} eliminada.')
    return redirect('logistica:guia_lista', proyecto_id=proyecto_id)


# ── Transportistas ────────────────────────────────────────────────

@requiere('puede_gestionar_logistica')
def transportista_lista(request):
    qs = Transportista.objects.all()
    return render(request, 'logistica/transportista_lista.html', {'transportistas': qs})


@requiere('puede_gestionar_logistica')
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


@requiere('puede_gestionar_logistica')
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

@requiere('puede_revisar_reqs_log')
@proyecto_visible
def requerimientos_log(request, proyecto_id):
    from apps.requerimientos.models import Requerimiento, ESTADOS_REQ
    proyecto = _get_proyecto(proyecto_id)
    estado_sel = request.GET.get('estado', '')
    qs = (Requerimiento.objects
          .filter(proyecto=proyecto)
          .prefetch_related('detalles__insumo', 'cotizaciones_origen')
          .order_by('-fecha', '-numero'))
    if estado_sel:
        qs = qs.filter(estado=estado_sel)
    return render(request, 'logistica/requerimientos.html', {
        'proyecto':    proyecto,
        'requerimientos': qs,
        'estados':     ESTADOS_REQ,
        'estado_sel':  estado_sel,
        'enviados':    Requerimiento.objects.filter(proyecto=proyecto, estado='ENVIADO').count(),
    })


@requiere('puede_revisar_reqs_log')
@proyecto_visible
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


@requiere('puede_revisar_reqs_log')
@proyecto_visible
def historial_log(request, proyecto_id):
    from apps.requerimientos.models import Requerimiento
    proyecto = _get_proyecto(proyecto_id)
    requerimientos = (Requerimiento.objects
                      .filter(proyecto=proyecto,
                              estado__in=['EN_REVISION', 'APROBADO', 'PARCIAL', 'ANULADO'])
                      .order_by('-fecha', '-numero'))
    return render(request, 'logistica/req_historial.html', {
        'proyecto':       proyecto,
        'requerimientos': requerimientos,
    })


@requiere('puede_revisar_reqs_log')
@proyecto_visible
def por_atender_log(request, proyecto_id):
    from apps.requerimientos.models import Requerimiento
    proyecto = _get_proyecto(proyecto_id)
    requerimientos = (Requerimiento.objects
                      .filter(proyecto=proyecto, estado='PARCIAL')
                      .order_by('-fecha', '-numero'))
    return render(request, 'logistica/req_por_atender.html', {
        'proyecto':       proyecto,
        'requerimientos': requerimientos,
    })


@requiere('puede_revisar_reqs_log')
@proyecto_visible
def anulados_log(request, proyecto_id):
    from apps.requerimientos.models import Requerimiento
    proyecto = _get_proyecto(proyecto_id)
    requerimientos = (Requerimiento.objects
                      .filter(proyecto=proyecto, estado='ANULADO')
                      .order_by('-fecha', '-numero'))
    return render(request, 'logistica/req_anulados.html', {
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


@requiere('puede_revisar_reqs_log')
@proyecto_visible
def req_detalle_log(request, proyecto_id, pk):
    from apps.requerimientos.models import Requerimiento
    proyecto = _get_proyecto(proyecto_id)
    req = get_object_or_404(Requerimiento, pk=pk, proyecto=proyecto)
    if req.estado == 'ENVIADO':
        req.estado = 'EN_REVISION'
        req.save(update_fields=['estado'])
        log(request, 'EDITAR', 'Logística',
            f'REQ{req.numero} marcado En revisión por {request.user.get_full_name() or request.user.username}')
    detalles = list(req.detalles.select_related('insumo').all())
    _backfill_codigos(detalles, proyecto)
    return render(request, 'logistica/req_detalle.html', {
        'proyecto': proyecto,
        'req':      req,
    })


@requiere('puede_revisar_reqs_log')
@proyecto_visible
def req_revisar_log(request, proyecto_id, pk):
    from decimal import Decimal, InvalidOperation
    from apps.requerimientos.models import Requerimiento, HistorialRevisionReq
    from apps.presupuesto.models import InsumoPresupuesto as _Ins

    proyecto = _get_proyecto(proyecto_id)
    req = get_object_or_404(Requerimiento, pk=pk, proyecto=proyecto)

    ESTADOS_VISIBLES  = ('ENVIADO', 'EN_REVISION', 'APROBADO', 'PARCIAL', 'ANULADO', 'ATENDIDO')
    ESTADOS_EDITABLES = ('ENVIADO', 'EN_REVISION')
    if req.estado not in ESTADOS_VISIBLES:
        messages.error(request, 'Este requerimiento no puede visualizarse en su estado actual.')
        return redirect('logistica:requerimientos_log', proyecto_id=proyecto_id)

    editable = req.estado in ESTADOS_EDITABLES

    if req.estado == 'ENVIADO':
        req.estado = 'EN_REVISION'
        req.save(update_fields=['estado'])

    detalles = list(req.detalles.select_related('insumo').all())
    _backfill_codigos(detalles, proyecto)

    if request.method == 'POST':
        if not editable:
            messages.error(request, 'Este requerimiento ya fue aprobado; usa Anular o Recuperar.')
            return redirect('logistica:req_revisar_log', proyecto_id=proyecto_id, pk=pk)

        errores = []

        # ── Procesar ítems existentes ────────────────────────────────
        aprobaciones = {}
        eliminados   = {}   # det.pk → justificacion

        for det in detalles:
            if request.POST.get(f'eliminar_{det.pk}'):
                aprobaciones[det.pk] = Decimal('0')
                eliminados[det.pk]   = request.POST.get(f'justif_eliminar_{det.pk}', '').strip()
            else:
                raw = request.POST.get(f'aprobada_{det.pk}', '').strip()
                try:
                    aprobada = Decimal(raw) if raw else Decimal('0')
                except InvalidOperation:
                    aprobada = Decimal('0')
                if aprobada < 0:
                    errores.append(f'Ítem "{det.descripcion or det.pk}": cantidad negativa.')
                elif aprobada > det.cantidad_requerida:
                    errores.append(
                        f'Ítem "{det.descripcion or det.pk}": '
                        f'cantidad ({aprobada}) supera la requerida ({det.cantidad_requerida}).'
                    )
                else:
                    aprobaciones[det.pk] = aprobada

        # ── Validar nuevos ítems ─────────────────────────────────────
        nuevo_count = int(request.POST.get('nuevo_count', '0') or 0)
        nuevos = []
        for n in range(nuevo_count):
            ins_pk   = request.POST.get(f'nuevo_{n}_insumo', '').strip()
            cant_str = request.POST.get(f'nuevo_{n}_cantidad', '').strip()
            desc     = request.POST.get(f'nuevo_{n}_desc', '').strip()
            unidad   = request.POST.get(f'nuevo_{n}_unidad', '').strip()
            justif   = request.POST.get(f'nuevo_{n}_justif', '').strip()
            if not ins_pk or not cant_str:
                continue
            try:
                insumo = _Ins.objects.get(pk=int(ins_pk))
                cant   = Decimal(cant_str)
                if cant <= 0:
                    errores.append(f'Ítem nuevo "{desc}": la cantidad debe ser mayor a 0.')
                else:
                    nuevos.append({'insumo': insumo, 'cantidad': cant,
                                   'desc': desc or insumo.descripcion,
                                   'unidad': unidad or insumo.unidad or '',
                                   'justif': justif})
            except (ValueError, _Ins.DoesNotExist, InvalidOperation):
                errores.append(f'Ítem nuevo "{desc}": insumo o cantidad inválidos.')

        if errores:
            for e in errores:
                messages.error(request, e)
            historial = req.historial_revision.select_related('insumo', 'usuario').all()
            return render(request, 'logistica/req_revisar.html', {
                'proyecto': proyecto, 'req': req,
                'detalles': detalles, 'historial': historial,
                'editable': editable,
            })

        # ── Guardar aprobaciones y registrar eliminaciones ───────────
        es_parcial = False
        for det in detalles:
            aprobada = aprobaciones[det.pk]
            det.cantidad_aprobada = aprobada
            det.save(update_fields=['cantidad_aprobada'])
            if aprobada < det.cantidad_requerida:
                es_parcial = True
            if det.pk in eliminados:
                HistorialRevisionReq.objects.create(
                    requerimiento=req,
                    accion='ELIMINAR',
                    insumo=det.insumo,
                    descripcion=det.descripcion or (det.insumo.descripcion if det.insumo else '—'),
                    unidad=det.unidad or '',
                    cantidad=det.cantidad_requerida,
                    justificacion=eliminados[det.pk],
                    usuario=request.user,
                )

        # ── Crear nuevos ítems ───────────────────────────────────────
        from apps.requerimientos.models import DetalleRequerimiento as _Det
        for n in nuevos:
            _Det.objects.create(
                requerimiento=req,
                insumo=n['insumo'],
                codigo=n['insumo'].codigo or '',
                descripcion=n['desc'],
                unidad=n['unidad'],
                cantidad=n['cantidad'],
                cantidad_requerida=n['cantidad'],
                cantidad_aprobada=n['cantidad'],
            )
            HistorialRevisionReq.objects.create(
                requerimiento=req,
                accion='AGREGAR',
                insumo=n['insumo'],
                descripcion=n['desc'],
                unidad=n['unidad'],
                cantidad=n['cantidad'],
                justificacion=n['justif'],
                usuario=request.user,
            )

        # ── Estado del requerimiento ─────────────────────────────────
        if nuevos and not es_parcial:
            pass  # nuevos siempre tienen aprobada == requerida, no cambia es_parcial
        req.estado = 'PARCIAL' if es_parcial else 'APROBADO'
        req.aprobacion_vista = False
        req.save()

        # Guías PENDIENTE heredadas del flujo anterior (ya no se generan al aprobar)
        GuiaRemision.objects.filter(requerimiento=req, estado='PENDIENTE').delete()

        tipo_estado = 'aprobado parcialmente' if es_parcial else 'aprobado'
        log(request, 'EDITAR', 'Logística',
            f'REQ{req.numero} {tipo_estado} por {request.user.get_full_name() or request.user.username}')
        notificar(f'REQ{req.numero} {tipo_estado}',
                  mensaje=f'{proyecto.codigo} — revisado por Logística.',
                  tipo='warning' if es_parcial else 'success')
        messages.success(request, f'REQ{req.numero} {tipo_estado} correctamente.')
        return redirect('logistica:requerimientos_log', proyecto_id=proyecto_id)

    historial = req.historial_revision.select_related('insumo', 'usuario').all()

    # Suma de cantidad cotizada-y-aprobada por ítem (para la columna "Aprobado" de
    # la tabla), independientemente del estado del REQ. Si no hay cotizaciones
    # APROBADAS, queda en 0 para todos los ítems.
    from apps.almacen.views import _clave_item_cot
    from apps.almacen.models import DetalleCotizacion as _DetCot
    sumas_cot_aprobada = {}
    for d in _DetCot.objects.filter(
            cotizacion__requerimiento_origen=req,
            cotizacion__estado='APROBADA'):
        k = _clave_item_cot(d.insumo_id, d.descripcion)
        sumas_cot_aprobada[k] = sumas_cot_aprobada.get(k, Decimal('0')) + d.cantidad
    for det in detalles:
        k = _clave_item_cot(det.insumo_id, det.descripcion)
        det.cot_aprobada = sumas_cot_aprobada.get(k, Decimal('0'))

    # Ítems candidatos para una nueva cotización desde este REQ: cantidad sugerida =
    # min(cantidad_aprobada, saldo cotizable restante). Se filtran los que ya están
    # completamente cotizados (saldo = 0). Solo tiene sentido cuando el REQ ya fue aprobado.
    items_para_cotizar = []
    siguiente_numero_cot = ''
    if req.estado in ('APROBADO', 'COTIZADO', 'PARCIAL'):
        from apps.almacen.views import _saldo_cotizable
        from apps.almacen.models import Cotizacion as _Cot
        saldos = _saldo_cotizable(req)
        for det in detalles:
            if not det.cantidad_aprobada or det.cantidad_aprobada <= 0:
                continue
            k = _clave_item_cot(det.insumo_id, det.descripcion)
            saldo = saldos.get(k, Decimal('0'))
            if saldo <= 0:
                continue
            sugerida = min(det.cantidad_aprobada, saldo)
            items_para_cotizar.append({
                'det_pk': det.pk,
                'insumo_id': det.insumo_id or '',
                'codigo': det.codigo or (det.insumo.codigo if det.insumo_id else ''),
                'descripcion': det.descripcion or (det.insumo.descripcion if det.insumo_id else ''),
                'unidad': det.unidad or (det.insumo.unidad if det.insumo_id and det.insumo.unidad else ''),
                'cantidad': sugerida,
                'saldo': saldo,
            })
        # Previsualización del próximo N° COT (misma lógica que cot_desde_req).
        base = str(req.numero)
        cots_previas = req.cotizaciones_origen.count()
        numero = base if cots_previas == 0 else f'{base}-{cots_previas + 1}'
        while _Cot.objects.filter(proyecto=proyecto, numero=numero).exists():
            cots_previas += 1
            numero = f'{base}-{cots_previas + 1}'
        siguiente_numero_cot = f'COT{numero}'

    return render(request, 'logistica/req_revisar.html', {
        'proyecto': proyecto,
        'req':      req,
        'detalles': detalles,
        'historial': historial,
        'editable': editable,
        'items_para_cotizar': items_para_cotizar,
        'siguiente_numero_cot': siguiente_numero_cot,
    })


def _guia_bloqueante(req):
    """Retorna la primera guía en EN_TRANSITO o ENTREGADO ligada al req (directamente
    o a través de sus cotizaciones), si existe."""
    directa = req.guias_remision.filter(estado__in=ESTADOS_GUIA_DESPACHADA).first()
    if directa:
        return directa
    return (GuiaRemision.objects
            .filter(cotizaciones__requerimiento_origen=req, estado__in=ESTADOS_GUIA_DESPACHADA)
            .distinct().first())


@requiere('puede_revisar_reqs_log')
@proyecto_visible
def req_anular_log(request, proyecto_id, pk):
    from decimal import Decimal
    from apps.requerimientos.models import Requerimiento, HistorialRevisionReq

    if request.method != 'POST':
        return redirect('logistica:req_revisar_log', proyecto_id=proyecto_id, pk=pk)

    proyecto = _get_proyecto(proyecto_id)
    req = get_object_or_404(Requerimiento, pk=pk, proyecto=proyecto)

    if req.estado not in ('APROBADO', 'PARCIAL'):
        messages.error(request, 'Solo se pueden anular requerimientos aprobados.')
        return redirect('logistica:req_revisar_log', proyecto_id=proyecto_id, pk=pk)

    guia_bloq = _guia_bloqueante(req)
    if guia_bloq:
        messages.error(request, f'No se puede anular: la guía {guia_bloq.numero} ya está {guia_bloq.get_estado_display()}.')
        return redirect('logistica:req_revisar_log', proyecto_id=proyecto_id, pk=pk)

    justificacion = request.POST.get('justificacion', '').strip()
    if not justificacion:
        messages.error(request, 'La justificación es obligatoria para anular.')
        return redirect('logistica:req_revisar_log', proyecto_id=proyecto_id, pk=pk)

    req.estado = 'ANULADO'
    req.save(update_fields=['estado'])

    req.guias_remision.filter(estado='PENDIENTE').update(estado='ANULADO')

    HistorialRevisionReq.objects.create(
        requerimiento=req,
        accion='ANULAR',
        descripcion=f'Requerimiento REQ{req.numero} anulado',
        unidad='',
        cantidad=Decimal('0'),
        justificacion=justificacion,
        usuario=request.user,
    )

    log(request, 'ANULAR', 'Logística',
        f'REQ{req.numero} anulado por {request.user.get_full_name() or request.user.username}')
    notificar(f'REQ{req.numero} anulado',
              mensaje=f'{proyecto.codigo} — {justificacion[:80]}',
              tipo='danger')
    messages.success(request, f'REQ{req.numero} anulado.')
    return redirect('logistica:requerimientos_log', proyecto_id=proyecto_id)


@requiere('puede_revisar_reqs_log')
@proyecto_visible
def req_recuperar_log(request, proyecto_id, pk):
    from decimal import Decimal
    from apps.requerimientos.models import Requerimiento, HistorialRevisionReq

    if request.method != 'POST':
        return redirect('logistica:req_revisar_log', proyecto_id=proyecto_id, pk=pk)

    proyecto = _get_proyecto(proyecto_id)
    req = get_object_or_404(Requerimiento, pk=pk, proyecto=proyecto)

    if req.estado != 'ANULADO':
        messages.error(request, 'Solo se pueden recuperar requerimientos anulados.')
        return redirect('logistica:req_revisar_log', proyecto_id=proyecto_id, pk=pk)

    guia_bloq = _guia_bloqueante(req)
    if guia_bloq:
        messages.error(request, f'No se puede recuperar: la guía {guia_bloq.numero} ya está {guia_bloq.get_estado_display()}.')
        return redirect('logistica:req_revisar_log', proyecto_id=proyecto_id, pk=pk)

    justificacion = request.POST.get('justificacion', '').strip()
    if not justificacion:
        messages.error(request, 'La justificación es obligatoria para recuperar.')
        return redirect('logistica:req_revisar_log', proyecto_id=proyecto_id, pk=pk)

    req.estado = 'EN_REVISION'
    req.save(update_fields=['estado'])

    HistorialRevisionReq.objects.create(
        requerimiento=req,
        accion='RECUPERAR',
        descripcion=f'Requerimiento REQ{req.numero} recuperado a EN_REVISION',
        unidad='',
        cantidad=Decimal('0'),
        justificacion=justificacion,
        usuario=request.user,
    )

    log(request, 'RECUPERAR', 'Logística',
        f'REQ{req.numero} recuperado por {request.user.get_full_name() or request.user.username}')
    notificar(f'REQ{req.numero} recuperado',
              mensaje=f'{proyecto.codigo} — devuelto a revisión.',
              tipo='info')
    messages.success(request, f'REQ{req.numero} recuperado. Vuelve a estar en revisión.')
    return redirect('logistica:req_revisar_log', proyecto_id=proyecto_id, pk=pk)


@requiere('puede_gestionar_logistica')
def guia_imprimir(request, pk):
    from apps.configuracion.models import ConfigEmpresa
    guia = get_object_or_404(
        GuiaRemision.objects.select_related('proyecto', 'transportista')
                             .prefetch_related('detalles'),
        pk=pk,
    )
    return render(request, 'logistica/guia_imprimir.html', {
        'guia':     guia,
        'proyecto': guia.proyecto,
        'empresa':  ConfigEmpresa.get(),
    })


@requiere('puede_gestionar_logistica')
def guia_bienes_api(request, pk):
    from django.http import JsonResponse
    guia = get_object_or_404(GuiaRemision, pk=pk)
    bienes = list(guia.detalles.values('descripcion', 'unidad', 'cantidad'))
    return JsonResponse({'bienes': bienes})


@requiere('puede_gestionar_almacen_log')
@proyecto_visible
def almacen_log(request, proyecto_id):
    """Vista informativa del stock del Almacenero desde Logística.
    Solo lectura — reusa los helpers de apps.almacen.views.stock."""
    from django.core.paginator import Paginator
    from apps.almacen.views import _stock_query, _build_items, PAGE_SIZE_STOCK
    from apps.presupuesto.models import TIPOS_RECURSO

    proyecto = _get_proyecto(proyecto_id)
    tipo_sel = request.GET.get('tipo', '')
    q        = request.GET.get('q', '').strip()
    order    = request.GET.get('order', 'codigo')

    qs, entradas_agg, salidas_agg = _stock_query(proyecto, tipo_sel, q, order)
    paginator = Paginator(qs, PAGE_SIZE_STOCK)
    page      = paginator.get_page(request.GET.get('page') or 1)
    items     = _build_items(page.object_list, entradas_agg, salidas_agg)

    return render(request, 'logistica/almacen_log.html', {
        'proyecto':   proyecto,
        'items':      items,
        'tipos':      TIPOS_RECURSO,
        'tipo_sel':   tipo_sel,
        'q':          q,
        'page':       page,
        'total':      paginator.count,
        'tiene_presupuesto': hasattr(proyecto, 'presupuesto') and proyecto.presupuesto is not None,
    })


@requiere('puede_gestionar_ctrl_maq_log')
@proyecto_visible
def control_maquinaria(request, proyecto_id):
    proyecto = _get_proyecto(proyecto_id)
    return render(request, 'logistica/control_maquinaria.html', {'proyecto': proyecto})


@requiere('puede_gestionar_abastecimiento')
@proyecto_visible
def abastecimiento(request, proyecto_id):
    proyecto = _get_proyecto(proyecto_id)
    return render(request, 'logistica/abastecimiento.html', {'proyecto': proyecto})


@requiere('puede_ver_logistica')
@proyecto_visible
def reportes(request, proyecto_id):
    proyecto = _get_proyecto(proyecto_id)
    return render(request, 'logistica/reportes.html', {'proyecto': proyecto})
