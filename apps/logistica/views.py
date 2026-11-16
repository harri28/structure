from decimal import Decimal
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from apps.proyectos.models import Proyecto
from apps.registro.utils import log, notificar
from .models import (
    GuiaRemision, DetalleGuia, Transportista, Proveedor,
    OrdenCompraLog, DetalleOrdenCompraLog, TIPOS_PAGO_OC,
    ESTADOS_GUIA, MOTIVOS_TRASLADO,
)
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

    # Datos para el modal "Nueva Guía"
    ocs_data = [{
        'pk': oc.pk,
        'numero': oc.numero,
        'proveedor': (oc.proveedor.razon_social if oc.proveedor_id else '') or '',
        'items': [{
            'codigo': (d.insumo.codigo if d.insumo_id and d.insumo.codigo else '') or '',
            'insumo_id': d.insumo_id,
            'descripcion': _descripcion_item(d),
            'unidad': _unidad_item(d),
            'cantidad': '{:f}'.format(d.cantidad.quantize(Decimal('0.001')).normalize()),
        } for d in oc.detalles.all()],
    } for oc in _ocs_disponibles(proyecto)]

    return render(request, 'logistica/guia_lista.html', {
        'proyecto': proyecto,
        'guias':    qs,
        'siguiente_numero_guia': _siguiente_numero_guia(proyecto),
        'ocs_data': ocs_data,
        'MOTIVOS_TRASLADO': MOTIVOS_TRASLADO,
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
    """Correlativo anual por proyecto: RG{nnnnn}-{YYYY}."""
    import datetime
    anio = datetime.date.today().year
    sufijo = f'-{anio}'
    mayor = 0
    for numero in (GuiaRemision.objects
                   .filter(proyecto=proyecto, numero__endswith=sufijo)
                   .values_list('numero', flat=True)):
        try:
            correlativo = numero.replace(sufijo, '').replace('RG', '')
            mayor = max(mayor, int(correlativo))
        except ValueError:
            continue
    return f'RG{str(mayor + 1).zfill(5)}{sufijo}'


ESTADOS_GUIA_ACTIVA = ['PENDIENTE', 'EN_TRANSITO', 'ENTREGADO']
ESTADOS_GUIA_DESPACHADA = ['EN_TRANSITO', 'ENTREGADO']


def _cotizaciones_disponibles(proyecto):
    """Cotizaciones APROBADAS del proyecto que aún no viajan en una guía activa.
    LEGACY — el flujo nuevo usa `_ocs_disponibles` (Órdenes de Compra)."""
    from apps.almacen.models import Cotizacion
    return (Cotizacion.objects
            .filter(proyecto=proyecto, estado='APROBADA')
            .exclude(guias_remision__estado__in=ESTADOS_GUIA_ACTIVA)
            .select_related('requerimiento_origen')
            .prefetch_related('detalles__insumo')
            .order_by('-fecha', '-pk'))


def _ocs_disponibles(proyecto):
    """Órdenes de Compra del proyecto que aún no viajan en una guía activa.
    Excluye OCs eliminadas (soft delete)."""
    from apps.logistica.models import OrdenCompraLog
    return (OrdenCompraLog.objects
            .filter(proyecto=proyecto, deleted_at__isnull=True)
            .exclude(guias_remision__estado__in=ESTADOS_GUIA_ACTIVA)
            .select_related('proveedor')
            .prefetch_related('detalles__insumo')
            .order_by('-created_at', '-pk'))


def _descripcion_item(d):
    return (d.descripcion or (d.insumo.descripcion if d.insumo_id else '') or '—')[:400]


def _unidad_item(d):
    return (d.unidad or (d.insumo.unidad if d.insumo_id and d.insumo.unidad else ''))[:20]


def _despachar_cotizaciones(guia, cotizaciones):
    """Copia los ítems de las cotizaciones a la guía y descuenta el stock en obra
    (InsumoPresupuesto.cantidad) por la cantidad de cada ítem. Nunca baja de cero.
    LEGACY — ahora las guías se arman desde Órdenes de Compra."""
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


def _despachar_ocs(guia, ocs, unir_duplicados=False):
    """Copia los ítems de las Órdenes de Compra a la guía y descuenta el stock en
    obra (InsumoPresupuesto.cantidad) por la cantidad de cada ítem. Nunca baja de
    cero. Si unir_duplicados=True, los ítems con el mismo código de insumo o la
    misma descripción se fusionan en una sola fila sumando cantidades."""
    from apps.presupuesto.models import InsumoPresupuesto
    descuentos = {}
    if unir_duplicados:
        agrupados = {}  # clave → {descripcion, unidad, cantidad}
        orden = []
        for oc in ocs:
            for d in oc.detalles.all():
                codigo = (d.insumo.codigo if d.insumo_id and d.insumo.codigo else '').strip().lower()
                desc = _descripcion_item(d).strip().lower()
                clave = ('c', codigo) if codigo else ('d', desc)
                if clave not in agrupados:
                    agrupados[clave] = {
                        'descripcion': _descripcion_item(d),
                        'unidad': _unidad_item(d),
                        'cantidad': Decimal('0'),
                    }
                    orden.append(clave)
                agrupados[clave]['cantidad'] += d.cantidad
                if d.insumo_id:
                    descuentos[d.insumo_id] = descuentos.get(d.insumo_id, Decimal('0')) + d.cantidad
        for clave in orden:
            info = agrupados[clave]
            DetalleGuia.objects.create(
                guia=guia,
                descripcion=info['descripcion'],
                unidad=info['unidad'],
                cantidad=info['cantidad'].quantize(Decimal('0.001')),
            )
    else:
        for oc in ocs:
            for d in oc.detalles.all():
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
    Nunca supera la cantidad original importada (cantidad_total). Considera tanto las
    OCs (flujo actual) como las cotizaciones legacy."""
    from apps.presupuesto.models import InsumoPresupuesto
    devoluciones = {}
    for oc in guia.ocs.prefetch_related('detalles'):
        for d in oc.detalles.all():
            if d.insumo_id:
                devoluciones[d.insumo_id] = devoluciones.get(d.insumo_id, Decimal('0')) + d.cantidad
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
    disponibles = list(_ocs_disponibles(proyecto))
    seleccion = []

    if request.method == 'POST':
        post = request.POST.copy()
        post['numero'] = _siguiente_numero_guia(proyecto)              # siempre automático
        post['fecha_emision'] = datetime.date.today().strftime('%Y-%m-%d')
        form = GuiaRemisionForm(post)

        ids = []
        for raw in request.POST.getlist('ocs'):
            if raw.isdigit() and int(raw) not in ids:
                ids.append(int(raw))
        elegidas = [oc for oc in disponibles if oc.pk in ids]
        seleccion = [oc.pk for oc in elegidas]

        ocs_ok = bool(elegidas) and len(elegidas) == len(ids)
        if not ids:
            messages.error(request, 'Selecciona al menos una orden de compra.')
        elif not ocs_ok:
            messages.error(request, 'Alguna orden de compra ya no está disponible (ya viaja en otra guía).')

        if form.is_valid() and ocs_ok:
            with transaction.atomic():
                guia = form.save(commit=False)
                guia.proyecto = proyecto
                guia.estado = 'EN_TRANSITO'
                guia.save()
                guia.ocs.set(elegidas)
                _despachar_ocs(guia, elegidas)
            # NOTA: la Entrada no se crea automáticamente. El Almacenero la registra
            # manualmente desde Almacén → Guías → Registrar guía.
            log(request, 'CREAR', 'Logística', f'Guía {guia.numero} despachada en {proyecto.codigo}')
            notificar(
                f'Nueva Guía {guia.numero}',
                mensaje=f'{proyecto.codigo} — Despachada por Logística. Registra su recepción.',
                tipo='info',
                url=f'/almacen/proyecto/{proyecto.pk}/guias/',
            )
            messages.success(request, f'Guía {guia.numero} generada.')
            return redirect('logistica:guia_detalle', pk=guia.pk)
    else:
        form = GuiaRemisionForm(initial={'numero': _siguiente_numero_guia(proyecto)})

    ocs_data = [{
        'pk': oc.pk,
        'numero': oc.numero,
        'proveedor': (oc.proveedor.razon_social if oc.proveedor_id else '') or '',
        'items': [{
            'descripcion': _descripcion_item(d),
            'unidad': _unidad_item(d),
            'cantidad': '{:f}'.format(d.cantidad.quantize(Decimal('0.001')).normalize()),
        } for d in oc.detalles.all()],
    } for oc in disponibles]

    return render(request, 'logistica/guia_form.html', {
        'proyecto': proyecto, 'form': form,
        'ocs_data': ocs_data,
        'ocs_seleccion': seleccion,
        'titulo': 'Nueva Guía de Remisión',
    })


@require_POST
@requiere('puede_gestionar_logistica')
@proyecto_visible
def guia_crear_ajax(request, proyecto_id):
    """Crea una Guía de Remisión desde el modal flotante de guia_lista.
    Espera POST con: ocs (lista de IDs), fecha_traslado, motivo, motivo_otro,
    peso_kg, origen, destino, conductor, placa, licencia, observaciones.
    Devuelve JSON {ok, numero, url} o {ok:False, error}."""
    import datetime, json
    from django.db import transaction
    from django.urls import reverse
    proyecto = _get_proyecto(proyecto_id)

    ids = []
    for raw in request.POST.getlist('ocs'):
        try:
            v = int(raw)
            if v not in ids:
                ids.append(v)
        except (TypeError, ValueError):
            continue
    if not ids:
        return JsonResponse({'ok': False, 'error': 'Selecciona al menos una orden de compra.'}, status=400)

    disponibles = list(_ocs_disponibles(proyecto))
    elegidas = [oc for oc in disponibles if oc.pk in ids]
    if len(elegidas) != len(ids):
        return JsonResponse({'ok': False, 'error': 'Alguna orden de compra ya no está disponible (ya viaja en otra guía).'}, status=400)

    fecha_traslado = (request.POST.get('fecha_traslado') or '').strip()
    if not fecha_traslado:
        return JsonResponse({'ok': False, 'error': 'La fecha de traslado es obligatoria.'}, status=400)

    origen  = (request.POST.get('origen')  or '').strip()
    destino = (request.POST.get('destino') or '').strip()
    if not origen or not destino:
        return JsonResponse({'ok': False, 'error': 'Punto de partida y punto de llegada son obligatorios.'}, status=400)

    motivo = (request.POST.get('motivo') or 'TRASLADO_OBRA').strip()
    if motivo not in dict(MOTIVOS_TRASLADO):
        motivo = 'TRASLADO_OBRA'
    motivo_otro = (request.POST.get('motivo_otro') or '').strip()
    if motivo == 'OTRO' and not motivo_otro:
        return JsonResponse({'ok': False, 'error': 'Indica el motivo cuando eliges "Otro".'}, status=400)

    peso_raw = (request.POST.get('peso_kg') or '').strip()
    peso_kg = None
    if peso_raw:
        try:
            peso_kg = Decimal(peso_raw)
        except Exception:
            return JsonResponse({'ok': False, 'error': 'Peso bruto inválido.'}, status=400)

    with transaction.atomic():
        guia = GuiaRemision.objects.create(
            proyecto=proyecto,
            numero=_siguiente_numero_guia(proyecto),
            fecha_emision=datetime.date.today(),
            fecha_traslado=fecha_traslado,
            motivo=motivo,
            motivo_otro=motivo_otro,
            origen=origen,
            destino=destino,
            conductor=(request.POST.get('conductor') or '').strip(),
            placa=(request.POST.get('placa') or '').strip(),
            licencia=(request.POST.get('licencia') or '').strip(),
            peso_kg=peso_kg,
            observaciones=(request.POST.get('observaciones') or '').strip(),
            estado='EN_TRANSITO',
        )
        guia.ocs.set(elegidas)
        unir = request.POST.get('unir_duplicados') == '1'
        _despachar_ocs(guia, elegidas, unir_duplicados=unir)

    log(request, 'CREAR', 'Logística', f'Guía {guia.numero} despachada en {proyecto.codigo}')
    notificar(
        f'Nueva Guía {guia.numero}',
        mensaje=f'{proyecto.codigo} — Despachada por Logística. Registra su recepción.',
        tipo='info',
        url=f'/almacen/proyecto/{proyecto.pk}/guias/',
    )
    return JsonResponse({
        'ok': True,
        'numero': guia.numero,
        'url': reverse('logistica:guia_detalle', args=[guia.pk]),
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
        tiene_origen = guia.ocs.exists() or guia.cotizaciones.exists()
        if tiene_origen and anterior == 'ANULADO':
            messages.error(request, 'Una guía anulada no se puede reactivar; genera una nueva.')
            return redirect('logistica:guia_detalle', pk=guia.pk)
        with transaction.atomic():
            guia.estado = nuevo
            guia.save(update_fields=['estado'])
            if tiene_origen:
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
    """Ingreso de Requerimientos: solo REQs aún no revisados (ENVIADO/
    EN_REVISION). Una vez que Logística clickea 'Aprobar Requerimiento',
    el REQ sale de esta lista y se ve en 'Aprobados' y/o 'Por Atender'
    según si hay diferencia pendiente o no.
    """
    from apps.requerimientos.models import Requerimiento, ESTADOS_REQ
    proyecto = _get_proyecto(proyecto_id)
    ESTADOS_INGRESO = ('ENVIADO', 'EN_REVISION')
    estado_sel = request.GET.get('estado', '')
    qs = (Requerimiento.objects
          .filter(proyecto=proyecto, estado__in=ESTADOS_INGRESO)
          .prefetch_related('detalles__insumo', 'cotizaciones_origen')
          .order_by('-fecha', '-numero'))
    if estado_sel in ESTADOS_INGRESO:
        qs = qs.filter(estado=estado_sel)
    estados_filtro = [(e, l) for e, l in ESTADOS_REQ if e in ESTADOS_INGRESO]
    return render(request, 'logistica/requerimientos.html', {
        'proyecto':    proyecto,
        'requerimientos': qs,
        'estados':     estados_filtro,
        'estado_sel':  estado_sel,
        'enviados':    Requerimiento.objects.filter(proyecto=proyecto, estado='ENVIADO').count(),
    })


@requiere('puede_revisar_reqs_log')
@proyecto_visible
def historial_log(request, proyecto_id):
    """Kardex por requerimiento: una fila colapsable por REQ con sus
    movimientos (ingreso, aprobación, cotizaciones, guías). Solo lectura."""
    from decimal import Decimal
    from apps.requerimientos.models import Requerimiento

    proyecto = _get_proyecto(proyecto_id)
    reqs = (Requerimiento.objects
            .filter(proyecto=proyecto,
                    estado__in=['EN_REVISION', 'APROBADO', 'PARCIAL',
                                'ANULADO', 'COTIZADO', 'ATENDIDO'])
            .select_related('created_by')
            .prefetch_related('detalles',
                              'historial_revision__usuario',
                              'cotizaciones_origen__detalles',
                              'guias_remision')
            .order_by('-fecha', '-numero'))

    rows = []
    for r in reqs:
        total_req = Decimal('0')
        total_apr = Decimal('0')
        for d in r.detalles.all():
            total_req += d.cantidad_requerida or Decimal('0')
            if d.cantidad_aprobada is not None:
                total_apr += d.cantidad_aprobada

        eventos = []
        items_n = r.detalles.count()

        # 1) Creación / envío
        if r.solicitante:
            u_creacion = r.solicitante
        elif r.created_by:
            u_creacion = r.created_by.get_full_name() or r.created_by.username
        else:
            u_creacion = '—'
        eventos.append({
            'fecha': r.created_at,
            'tipo': 'INGRESO',
            'tipo_label': 'Ingreso',
            'detalle': f'Requerimiento enviado con {items_n} ítem{"s" if items_n != 1 else ""}',
            'cantidad': total_req,
            'usuario': u_creacion,
        })

        # 2) Eventos del HistorialRevisionReq (AGREGAR, SUSTITUIR, ANULAR, RECUPERAR)
        for h in r.historial_revision.all():
            u = (h.usuario.get_full_name() or h.usuario.username) if h.usuario else '—'
            det = h.descripcion
            if h.justificacion:
                det = f'{det} — {h.justificacion}'
            eventos.append({
                'fecha': h.fecha,
                'tipo': h.accion,
                'tipo_label': h.get_accion_display(),
                'detalle': det,
                'cantidad': h.cantidad if h.cantidad and h.cantidad > 0 else None,
                'usuario': u,
            })

        # 3) Aprobación (sintético, sin timestamp exacto). Usa como proxy la
        #    fecha de la primera cotización del REQ; si no hay, queda sin fecha.
        if total_apr > 0 and r.estado != 'ANULADO':
            primera_cot = r.cotizaciones_origen.order_by('created_at').first()
            fecha_apr = primera_cot.created_at if primera_cot else None
            parcial = total_apr < total_req
            label = 'Aprobación parcial' if parcial else 'Aprobación total'
            det_apr = f'Aprobado {total_apr:.2f} de {total_req:.2f} und'
            if parcial:
                det_apr += f' · pendiente {total_req - total_apr:.2f} und'
            eventos.append({
                'fecha': fecha_apr,
                'tipo': 'APROBAR',
                'tipo_label': label,
                'detalle': det_apr,
                'cantidad': total_apr,
                'usuario': '—',
            })

        # 4) Cotizaciones
        for cot in r.cotizaciones_origen.all():
            cant_cot = sum((d.cantidad for d in cot.detalles.all()), Decimal('0'))
            eventos.append({
                'fecha': cot.created_at,
                'tipo': 'COT_CREAR',
                'tipo_label': 'Cotización creada',
                'detalle': f'COT{cot.numero} — {cot.proveedor or "sin proveedor"}',
                'cantidad': cant_cot,
                'usuario': '—',
            })
            if cot.estado == 'APROBADA':
                eventos.append({
                    'fecha': None,
                    'tipo': 'COT_APROBAR',
                    'tipo_label': 'Cotización aprobada',
                    'detalle': f'COT{cot.numero} aprobada',
                    'cantidad': cant_cot,
                    'usuario': '—',
                })
            elif cot.estado == 'RECHAZADA':
                eventos.append({
                    'fecha': None,
                    'tipo': 'COT_RECHAZAR',
                    'tipo_label': 'Cotización rechazada',
                    'detalle': f'COT{cot.numero} rechazada',
                    'cantidad': cant_cot,
                    'usuario': '—',
                })

        # 5) Guías emitidas (FK directa + vía cotizaciones M2M, sin anuladas)
        guias_pks = set()
        for g in r.guias_remision.exclude(estado='ANULADO'):
            guias_pks.add(g.pk)
        for cot in r.cotizaciones_origen.all():
            for g in cot.guias_remision.exclude(estado='ANULADO'):
                guias_pks.add(g.pk)
        if guias_pks:
            for g in (GuiaRemision.objects
                      .filter(pk__in=guias_pks)
                      .prefetch_related('detalles')):
                cant_g = sum((d.cantidad for d in g.detalles.all()), Decimal('0'))
                eventos.append({
                    'fecha': g.creado_en,
                    'tipo': 'GUIA',
                    'tipo_label': 'Guía emitida',
                    'detalle': f'{g.numero} · {g.get_estado_display()}',
                    'cantidad': cant_g,
                    'usuario': '—',
                })

        # Orden cronológico ascendente; los sin fecha quedan al final.
        eventos.sort(key=lambda e: (e['fecha'] is None, e['fecha'] or 0))

        rows.append({
            'req':           r,
            'items':         items_n,
            'total_req':     total_req,
            'total_apr':     total_apr,
            'pendiente':     max(Decimal('0'), total_req - total_apr),
            'eventos':       eventos,
            'eventos_count': len(eventos),
        })

    return render(request, 'logistica/req_historial.html', {
        'proyecto':       proyecto,
        'requerimientos': rows,
    })


ESTADOS_REQ_REVISADOS = ('APROBADO', 'COTIZADO', 'PARCIAL', 'ATENDIDO')


def _reqs_con_items(proyecto, filtro):
    """Devuelve lista de dicts {req, detalles_filtrados} para templates
    de Por Atender / Aprobados.

    filtro:
      - 'pendientes': detalles con cantidad_aprobada < cantidad_requerida
        (o cantidad_aprobada IS NULL) y el REQ está en estado revisado.
      - 'aprobados':  detalles con cantidad_aprobada > 0 (no null) y el
        REQ está en estado revisado.
    """
    from apps.requerimientos.models import Requerimiento
    from django.db.models import F, Q

    qs = (Requerimiento.objects
          .filter(proyecto=proyecto, estado__in=ESTADOS_REQ_REVISADOS)
          .prefetch_related('detalles__insumo')
          .order_by('-fecha', '-numero'))

    from decimal import Decimal
    resultado = []
    for r in qs:
        detalles_filtrados = []
        for d in r.detalles.all():
            cant_req = d.cantidad_requerida or Decimal('0')
            cant_apr = d.cantidad_aprobada  # puede ser None
            aprobada_real = cant_apr if cant_apr is not None else Decimal('0')
            if filtro == 'aprobados':
                if aprobada_real > 0:
                    d.cantidad_pendiente = cant_req - aprobada_real
                    detalles_filtrados.append(d)
            elif filtro == 'pendientes':
                if aprobada_real < cant_req:
                    d.cantidad_pendiente = cant_req - aprobada_real
                    detalles_filtrados.append(d)
        if detalles_filtrados:
            resultado.append({'req': r, 'detalles': detalles_filtrados})
    return resultado


@requiere('puede_revisar_reqs_log')
@proyecto_visible
def por_atender_log(request, proyecto_id):
    """Lista ítems con diferencia pendiente de aprobación (cantidad_requerida
    > cantidad_aprobada) en REQs ya revisados por Logística."""
    proyecto = _get_proyecto(proyecto_id)
    items = _reqs_con_items(proyecto, 'pendientes')
    return render(request, 'logistica/req_por_atender.html', {
        'proyecto': proyecto,
        'items':    items,
    })


@requiere('puede_revisar_reqs_log')
@proyecto_visible
def aprobados_log(request, proyecto_id):
    """Lista ítems aprobados por Logística (cantidad_aprobada > 0) en REQs
    ya revisados. Desde acá se generan cotizaciones."""
    proyecto = _get_proyecto(proyecto_id)
    items = _reqs_con_items(proyecto, 'aprobados')
    return render(request, 'logistica/req_aprobados.html', {
        'proyecto': proyecto,
        'items':    items,
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

    ESTADOS_VISIBLES  = ('ENVIADO', 'EN_REVISION', 'APROBADO', 'COTIZADO', 'PARCIAL', 'ANULADO', 'ATENDIDO')
    # APROBADO entra también a editables: desde 'Por Atender' Logística puede
    # completar la aprobación de los ítems que quedaron con diferencia pendiente.
    ESTADOS_EDITABLES = ('ENVIADO', 'EN_REVISION', 'APROBADO')
    if req.estado not in ESTADOS_VISIBLES:
        messages.error(request, 'Este requerimiento no puede visualizarse en su estado actual.')
        return redirect('logistica:requerimientos_log', proyecto_id=proyecto_id)

    editable = req.estado in ESTADOS_EDITABLES

    # Pestaña de origen para el botón "Volver": leer ?from=... y mapearlo a
    # URL + label. Default: 'Ingreso de Requerimientos'.
    from_slug = (request.GET.get('from') or '').strip()
    _VOLVER = {
        'por_atender': ('logistica:por_atender_log', 'Por atender'),
        'aprobados':   ('logistica:aprobados_log',   'Requerimientos Aprobados'),
        'historial':   ('logistica:historial_log',   'Historial'),
        'anulados':    ('logistica:anulados_log',    'Anulados'),
    }
    _vol = _VOLVER.get(from_slug, ('logistica:requerimientos_log', 'Ingreso de Requerimientos'))
    volver_urlname, volver_label = _vol

    # Historial siempre es solo lectura, sin importar el estado del REQ.
    if from_slug == 'historial':
        editable = False
    # Desde 'Aprobados' el REQ también es solo lectura: ya pasó por la fase
    # de aprobación; acá la siguiente acción es generar cotización.
    elif from_slug == 'aprobados':
        editable = False
    # Desde 'Por Atender': forzamos editable para que Logística pueda cerrar
    # los pendientes aunque el REQ ya esté en PARCIAL (o incluso ATENDIDO
    # por despachos previos). El REQ solo aparece acá si tiene items con
    # cantidad_aprobada < cantidad_requerida.
    elif from_slug == 'por_atender' and req.estado in ('PARCIAL', 'ATENDIDO'):
        editable = True

    if req.estado == 'ENVIADO' and from_slug != 'historial':
        req.estado = 'EN_REVISION'
        req.save(update_fields=['estado'])

    detalles = list(req.detalles.select_related('insumo').all())
    _backfill_codigos(detalles, proyecto)

    # En modo Por Atender, cada detalle expone:
    #   - aprobado_previo: lo ya aprobado antes de abrir esta pantalla
    #   - pendiente: cantidad_requerida - aprobado_previo (nunca negativa)
    # El template usa esos valores para que el input muestre la DIFERENCIA
    # y el max sea esa misma diferencia. Al guardar, la cantidad enviada
    # se interpreta como incremental y se suma al aprobado_previo.
    modo_por_atender = (from_slug == 'por_atender')
    if modo_por_atender:
        _detalles_pendientes = []
        for d in detalles:
            previo = d.cantidad_aprobada or Decimal('0')
            pend = (d.cantidad_requerida or Decimal('0')) - previo
            if pend < 0:
                pend = Decimal('0')
            d.aprobado_previo = previo
            d.pendiente = pend
            if pend > 0:
                _detalles_pendientes.append(d)
        # En Por atender solo mostramos los items con diferencia pendiente.
        detalles = _detalles_pendientes

    if request.method == 'POST':
        if not editable:
            messages.error(request, 'Este requerimiento ya fue aprobado; usa Anular o Recuperar.')
            return redirect('logistica:req_revisar_log', proyecto_id=proyecto_id, pk=pk)

        errores = []

        # ── Procesar ítems existentes ────────────────────────────────
        # (La opción de "eliminar ítem" con justificación se retiró de la UI;
        # ahora para quitar un ítem se usa el flujo de sustitución.)
        aprobaciones = {}

        for det in detalles:
            raw = request.POST.get(f'aprobada_{det.pk}', '').strip()
            try:
                entrada = Decimal(raw) if raw else Decimal('0')
            except InvalidOperation:
                entrada = Decimal('0')
            # En Por atender el input es INCREMENTAL (la diferencia). El
            # total aprobado = ya aprobado + lo escrito ahora.
            if modo_por_atender:
                previo_det = det.cantidad_aprobada or Decimal('0')
                aprobada = previo_det + entrada
            else:
                aprobada = entrada
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
            sust_pk  = request.POST.get(f'nuevo_{n}_sustituye_a', '').strip()
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
                                   'justif': justif,
                                   'sustituye_a_pk': int(sust_pk) if sust_pk.isdigit() else None})
            except (ValueError, _Ins.DoesNotExist, InvalidOperation):
                errores.append(f'Ítem nuevo "{desc}": insumo o cantidad inválidos.')

        # ── Validar saldo GLOBAL por insumo ──────────────────────────
        # Consolidación: lo que este REQ comprometerá por insumo =
        #   Σ aprobaciones de ítems existentes (los marcados "eliminar"
        #     ya quedaron en 0) + Σ cantidades de los nuevos.
        # Un nuevo que "sustituye_a_pk" un detalle existente libera la
        # aprobación de ese detalle (se marca como eliminado implícito).
        from apps.presupuesto.services import saldo_disponible_insumo, consolidar_por_insumo

        sust_pks = {n['sustituye_a_pk'] for n in nuevos if n.get('sustituye_a_pk')}
        pares = []
        for det in detalles:
            if det.pk in sust_pks:
                # Será eliminado por sustitución: no cuenta.
                continue
            if det.insumo_id and aprobaciones.get(det.pk):
                pares.append((det.insumo_id, aprobaciones[det.pk]))
        for n in nuevos:
            pares.append((n['insumo'].pk, n['cantidad']))
        pedido_por_insumo = consolidar_por_insumo(pares)

        for insumo_id, cant in pedido_por_insumo.items():
            try:
                ins_obj = _Ins.objects.get(pk=insumo_id)
            except _Ins.DoesNotExist:
                continue
            disp = saldo_disponible_insumo(ins_obj, excluir_req_pk=req.pk)
            if cant > disp:
                errores.append(
                    f'"{ins_obj.descripcion}": la cantidad total a aprobar '
                    f'({cant}) supera el saldo disponible del presupuesto '
                    f'({disp} {ins_obj.unidad or "und"}). '
                    f'Si existen otros REQ aprobados que consumen este insumo, '
                    f'revisá el stock en el presupuesto antes de aprobar.'
                )

        if errores:
            for e in errores:
                messages.error(request, e)
            historial = req.historial_revision.select_related('insumo', 'usuario').all()
            return render(request, 'logistica/req_revisar.html', {
                'proyecto': proyecto, 'req': req,
                'detalles': detalles, 'historial': historial,
                'editable': editable,
                'volver_urlname': volver_urlname,
                'volver_label':   volver_label,
                'from_slug':      from_slug,
                'modo_por_atender': modo_por_atender,
            })

        # ── Guardar aprobaciones ─────────────────────────────────────
        es_parcial = False
        detalle_por_pk = {d.pk: d for d in detalles}
        for det in detalles:
            # Si este detalle fue marcado para ser sustituido por un nuevo
            # ítem, forzamos su aprobación a 0 (equivale a neutralizarlo).
            es_sustituido = det.pk in sust_pks
            aprobada = Decimal('0') if es_sustituido else aprobaciones[det.pk]
            det.cantidad_aprobada = aprobada
            det.save(update_fields=['cantidad_aprobada'])
            if aprobada < det.cantidad_requerida:
                es_parcial = True

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
            # Si el nuevo ítem sustituye a uno existente, el historial lo
            # registra como SUSTITUIR y nombra al insumo original para
            # dejar rastro completo. Si no, es un AGREGAR común.
            sust_pk = n.get('sustituye_a_pk')
            sust_det = detalle_por_pk.get(sust_pk) if sust_pk else None
            if sust_det:
                orig_desc = (sust_det.descripcion
                             or (sust_det.insumo.descripcion if sust_det.insumo else '—'))
                justif_final = (
                    f'Sustituye a "{orig_desc}". ' + (n['justif'] or '')
                ).strip()
                HistorialRevisionReq.objects.create(
                    requerimiento=req,
                    accion='SUSTITUIR',
                    insumo=n['insumo'],
                    descripcion=n['desc'],
                    unidad=n['unidad'],
                    cantidad=n['cantidad'],
                    justificacion=justif_final,
                    usuario=request.user,
                )
            else:
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
        'volver_urlname': volver_urlname,
        'volver_label':   volver_label,
        'from_slug':      from_slug,
        'modo_por_atender': modo_por_atender,
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


@requiere('puede_revisar_reqs_log')
def req_item_aprobar(request, req_pk, det_pk):
    """Guarda cantidad_aprobada de UN solo ítem via AJAX. No cambia el estado
    del REQ — eso sigue pasando al clicar 'Aprobar Requerimiento' en el form
    grande. Validación: cantidad ≥ 0, ≤ cantidad_requerida, respeta el saldo
    global del insumo en el presupuesto. Responde JSON."""
    from decimal import Decimal, InvalidOperation
    from django.http import JsonResponse
    from django.db.models import Sum
    from apps.requerimientos.models import Requerimiento, DetalleRequerimiento
    from apps.presupuesto.services import saldo_disponible_insumo

    if request.method != 'POST':
        return JsonResponse({'ok': False, 'error': 'Método no permitido.'}, status=405)

    req = get_object_or_404(Requerimiento, pk=req_pk)
    # APROBADO y PARCIAL también entran acá para que Logística pueda cerrar
    # desde 'Por Atender' los ítems que quedaron con diferencia pendiente.
    if req.estado not in ('ENVIADO', 'EN_REVISION', 'APROBADO', 'PARCIAL'):
        return JsonResponse({
            'ok': False,
            'error': 'El requerimiento ya no está en revisión.',
        }, status=400)

    det = get_object_or_404(DetalleRequerimiento, pk=det_pk, requerimiento=req)

    raw = (request.POST.get('cantidad') or '').strip()
    try:
        entrada = Decimal(raw)
    except (InvalidOperation, ValueError):
        return JsonResponse({'ok': False, 'error': 'Cantidad inválida.'}, status=400)

    # Si viene con incremental=1 (desde Por atender), el valor entrante se
    # suma al ya aprobado del ítem en vez de reemplazarlo.
    incremental = request.POST.get('incremental') == '1'
    previo_det = det.cantidad_aprobada or Decimal('0')
    cantidad = (previo_det + entrada) if incremental else entrada

    if cantidad < 0:
        return JsonResponse({'ok': False, 'error': 'La cantidad no puede ser negativa.'}, status=400)
    if cantidad > det.cantidad_requerida:
        return JsonResponse({
            'ok': False,
            'error': f'No puede superar la cantidad requerida ({det.cantidad_requerida}).',
        }, status=400)

    # Saldo global del insumo (excluye este REQ para no contarse a sí mismo).
    if det.insumo_id:
        disp = saldo_disponible_insumo(det.insumo, excluir_req_pk=req.pk)
        # Sumar lo que ya aprobamos en otros detalles del MISMO REQ para
        # este insumo — porque el excluir_req_pk los excluye a todos.
        otros_aprobados_mismo_req = DetalleRequerimiento.objects.filter(
            requerimiento=req, insumo_id=det.insumo_id,
        ).exclude(pk=det.pk).aggregate(
            s=Sum('cantidad_aprobada'),
        )['s'] or Decimal('0')
        if cantidad + otros_aprobados_mismo_req > disp:
            return JsonResponse({
                'ok': False,
                'error': (f'"{det.insumo.descripcion}": pediste {cantidad} pero '
                          f'solo quedan {disp - otros_aprobados_mismo_req} '
                          f'{det.insumo.unidad or "und"} disponibles en el presupuesto.'),
            }, status=400)

    det.cantidad_aprobada = cantidad
    det.save(update_fields=['cantidad_aprobada'])

    if req.estado == 'ENVIADO':
        req.estado = 'EN_REVISION'
        req.save(update_fields=['estado'])

    log(request, 'EDITAR', 'Logística',
        f'REQ{req.numero} ítem "{det.descripcion or det.insumo}" aprobado por '
        f'{cantidad} por {request.user.get_full_name() or request.user.username}')

    return JsonResponse({
        'ok': True,
        'cantidad_aprobada': str(cantidad),
    })


@requiere('puede_revisar_reqs_log')
def req_item_sustituir(request, req_pk, det_pk):
    """Sustituye el insumo de UN detalle por otro (AJAX). Crea un nuevo
    DetalleRequerimiento con el insumo nuevo + neutraliza el original
    (cantidad_aprobada=0) + registra en historial como SUSTITUIR con
    insumo_original para trazabilidad."""
    from decimal import Decimal, InvalidOperation
    from django.http import JsonResponse
    from apps.requerimientos.models import Requerimiento, DetalleRequerimiento, HistorialRevisionReq
    from apps.presupuesto.models import InsumoPresupuesto
    from apps.presupuesto.services import saldo_disponible_insumo

    if request.method != 'POST':
        return JsonResponse({'ok': False, 'error': 'Método no permitido.'}, status=405)

    req = get_object_or_404(Requerimiento, pk=req_pk)
    if req.estado not in ('ENVIADO', 'EN_REVISION'):
        return JsonResponse({
            'ok': False,
            'error': 'El requerimiento ya no está en revisión.',
        }, status=400)

    det_original = get_object_or_404(DetalleRequerimiento, pk=det_pk, requerimiento=req)

    nuevo_insumo_id = (request.POST.get('nuevo_insumo_id') or '').strip()
    cant_raw = (request.POST.get('cantidad') or '').strip()
    justif = (request.POST.get('justificacion') or '').strip()

    if not nuevo_insumo_id:
        return JsonResponse({'ok': False, 'error': 'Elige un insumo de reemplazo.'}, status=400)
    try:
        nuevo_insumo = InsumoPresupuesto.objects.get(pk=int(nuevo_insumo_id))
    except (ValueError, InsumoPresupuesto.DoesNotExist):
        return JsonResponse({'ok': False, 'error': 'Insumo de reemplazo inválido.'}, status=400)

    try:
        cantidad = Decimal(cant_raw)
    except (InvalidOperation, ValueError):
        return JsonResponse({'ok': False, 'error': 'Cantidad inválida.'}, status=400)
    if cantidad <= 0:
        return JsonResponse({'ok': False, 'error': 'La cantidad debe ser mayor a 0.'}, status=400)

    disp = saldo_disponible_insumo(nuevo_insumo, excluir_req_pk=req.pk)
    if cantidad > disp:
        return JsonResponse({
            'ok': False,
            'error': (f'"{nuevo_insumo.descripcion}": pediste {cantidad} pero '
                      f'solo quedan {disp} {nuevo_insumo.unidad or "und"} '
                      f'disponibles en el presupuesto.'),
        }, status=400)

    original_desc = (det_original.descripcion
                     or (det_original.insumo.descripcion if det_original.insumo else '—'))
    original_insumo = det_original.insumo

    det_original.cantidad_aprobada = Decimal('0')
    det_original.save(update_fields=['cantidad_aprobada'])

    nuevo_det = DetalleRequerimiento.objects.create(
        requerimiento=req,
        insumo=nuevo_insumo,
        codigo=nuevo_insumo.codigo or '',
        descripcion=nuevo_insumo.descripcion,
        unidad=nuevo_insumo.unidad or '',
        cantidad=cantidad,
        cantidad_requerida=cantidad,
        cantidad_aprobada=cantidad,
    )

    HistorialRevisionReq.objects.create(
        requerimiento=req,
        accion='SUSTITUIR',
        insumo=nuevo_insumo,
        insumo_original=original_insumo,
        descripcion=f'{original_desc} → {nuevo_insumo.descripcion}',
        unidad=nuevo_insumo.unidad or '',
        cantidad=cantidad,
        justificacion=justif,
        usuario=request.user,
    )

    if req.estado == 'ENVIADO':
        req.estado = 'EN_REVISION'
        req.save(update_fields=['estado'])

    log(request, 'EDITAR', 'Logística',
        f'REQ{req.numero} insumo "{original_desc}" sustituido por '
        f'"{nuevo_insumo.descripcion}" ({cantidad} {nuevo_insumo.unidad or "und"}) '
        f'por {request.user.get_full_name() or request.user.username}')

    return JsonResponse({
        'ok': True,
        'nuevo_det_pk': nuevo_det.pk,
        'original_det_pk': det_original.pk,
    })


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


@requiere('puede_revisar_reqs_log', 'puede_ver_logistica')
@proyecto_visible
def req_insumos_log(request, proyecto_id):
    """Lista de insumos del presupuesto con la cantidad total APROBADA por
    Logística (sumando cantidad_aprobada de todos los REQ en APROBADO,
    COTIZADO, PARCIAL o ATENDIDO).

    Contador = 0.00 mientras no haya REQs aprobados para ese insumo.
    Cuando Logística aprueba un REQ, el contador refleja la suma.
    """
    from decimal import Decimal
    from django.db.models import DecimalField, Sum, Value, Q
    from django.db.models.functions import Coalesce
    from django.core.paginator import Paginator
    from django.db.models.functions import Cast, LPad
    from django.db.models import CharField
    from apps.requerimientos.models import DetalleRequerimiento
    from apps.presupuesto.models import TIPOS_RECURSO

    proyecto = _get_proyecto(proyecto_id)
    if not hasattr(proyecto, 'presupuesto') or proyecto.presupuesto is None:
        return render(request, 'logistica/req_insumos_log.html', {
            'proyecto':  proyecto,
            'items':     [],
            'tipos':     TIPOS_RECURSO,
            'tipo_sel':  '',
            'q':         '',
            'page':      None,
            'total':     0,
            'sin_presupuesto': True,
        })

    tipo_sel = request.GET.get('tipo', '').strip()
    q        = request.GET.get('q', '').strip()

    ESTADOS_APROBADOS = ('APROBADO', 'COTIZADO', 'PARCIAL', 'ATENDIDO')
    dec = DecimalField(max_digits=18, decimal_places=4)

    qs = proyecto.presupuesto.insumos.all()
    if tipo_sel:
        qs = qs.filter(tipo=tipo_sel)
    if q:
        qs = qs.filter(Q(codigo__icontains=q) | Q(descripcion__icontains=q))

    # Pre-sumar cantidad_aprobada por insumo con una subquery agrupada.
    aprobados_por_insumo = dict(
        DetalleRequerimiento.objects
        .filter(
            requerimiento__estado__in=ESTADOS_APROBADOS,
            requerimiento__proyecto=proyecto,
            insumo__isnull=False,
        )
        .values('insumo_id')
        .annotate(total=Coalesce(Sum('cantidad_aprobada', output_field=dec),
                                  Value(Decimal('0'), output_field=dec),
                                  output_field=dec))
        .values_list('insumo_id', 'total')
    )

    qs = qs.annotate(
        codigo_sort=LPad(Cast('codigo', output_field=CharField()), 10, Value('0')),
    ).order_by('tipo', 'codigo_sort')

    paginator = Paginator(qs, 30)
    page = paginator.get_page(request.GET.get('page') or 1)

    items = []
    for ins in page.object_list:
        aprobado = aprobados_por_insumo.get(ins.pk, Decimal('0'))
        items.append({
            'pk':          ins.pk,
            'codigo':      ins.codigo,
            'descripcion': ins.descripcion,
            'tipo':        ins.tipo,
            'tipo_display': ins.get_tipo_display(),
            'unidad':      ins.unidad or 'und',
            'aprobado':    aprobado,
        })

    return render(request, 'logistica/req_insumos_log.html', {
        'proyecto':  proyecto,
        'items':     items,
        'tipos':     TIPOS_RECURSO,
        'tipo_sel':  tipo_sel,
        'q':         q,
        'page':      page,
        'total':     paginator.count,
        'sin_presupuesto': False,
    })


@requiere('puede_ver_logistica')
@proyecto_visible
def compras_log(request, proyecto_id):
    """Lista de Órdenes de Compra del proyecto (excluye las eliminadas)."""
    from django.db.models import Q
    proyecto = _get_proyecto(proyecto_id)
    q = (request.GET.get('q') or '').strip()
    qs = (OrdenCompraLog.objects
          .filter(proyecto=proyecto, deleted_at__isnull=True)
          .select_related('proveedor')
          .prefetch_related('detalles'))
    if q:
        qs = qs.filter(Q(numero__icontains=q) |
                       Q(proveedor__razon_social__icontains=q) |
                       Q(proveedor__ruc__icontains=q) |
                       Q(numero_factura__icontains=q))
    items = []
    for oc in qs:
        items.append({
            'obj':   oc,
            'items_n': oc.detalles.count(),
            'total': oc.total(),
        })
    return render(request, 'logistica/compras_log.html', {
        'proyecto': proyecto,
        'items':    items,
        'q':        q,
        'total':    qs.count(),
        'TIPOS_PAGO_OC': TIPOS_PAGO_OC,
        'siguiente_numero_oc': _siguiente_numero_oc(proyecto),
    })


def _siguiente_numero_oc(proyecto):
    """Correlativo anual por proyecto: OC{nnnnn}-{YYYY}."""
    import datetime
    anio = datetime.date.today().year
    sufijo = f'-{anio}'
    mayor = 0
    for numero in (OrdenCompraLog.objects
                   .filter(proyecto=proyecto, numero__endswith=sufijo)
                   .values_list('numero', flat=True)):
        try:
            correlativo = numero.replace(sufijo, '').replace('OC', '')
            mayor = max(mayor, int(correlativo))
        except ValueError:
            continue
    return f'OC{str(mayor + 1).zfill(5)}{sufijo}'


def _saldos_comprables(proyecto):
    """{insumo_id: Decimal} con lo que queda por comprar =
    (Σ cantidad_aprobada en REQs revisados) − (Σ cantidades ya en OC del proyecto)."""
    from decimal import Decimal
    from django.db.models import Sum
    from apps.requerimientos.models import DetalleRequerimiento

    estados_ok = ('APROBADO', 'COTIZADO', 'PARCIAL', 'ATENDIDO')
    aprobados = dict(
        DetalleRequerimiento.objects
        .filter(requerimiento__proyecto=proyecto,
                requerimiento__estado__in=estados_ok,
                cantidad_aprobada__gt=0,
                insumo_id__isnull=False)
        .values('insumo_id')
        .annotate(s=Sum('cantidad_aprobada'))
        .values_list('insumo_id', 's')
    )
    comprados = dict(
        DetalleOrdenCompraLog.objects
        .filter(orden__proyecto=proyecto,
                orden__deleted_at__isnull=True,
                insumo_id__isnull=False)
        .values('insumo_id')
        .annotate(s=Sum('cantidad'))
        .values_list('insumo_id', 's')
    )
    saldos = {}
    for ins_id, aprob in aprobados.items():
        saldo = (aprob or Decimal('0')) - (comprados.get(ins_id) or Decimal('0'))
        if saldo < 0:
            saldo = Decimal('0')
        saldos[ins_id] = saldo
    return saldos


@requiere('puede_ver_logistica')
@proyecto_visible
def oc_insumos_buscar_ajax(request, proyecto_id):
    """GET AJAX: insumos del proyecto con saldo_comprable > 0. El saldo es
    cantidad_aprobada total − lo ya comprado en OrdenCompraLog previas."""
    from django.db.models import Q
    from apps.presupuesto.models import InsumoPresupuesto

    proyecto = _get_proyecto(proyecto_id)
    q = (request.GET.get('q') or '').strip()

    saldos = _saldos_comprables(proyecto)
    ids = [ins_id for ins_id, saldo in saldos.items() if saldo > 0]
    if not ids:
        return JsonResponse({'items': []})

    qs = InsumoPresupuesto.objects.filter(pk__in=ids)
    if q:
        qs = qs.filter(Q(codigo__icontains=q) | Q(descripcion__icontains=q))
    qs = qs.order_by('codigo', 'descripcion')[:30]
    return JsonResponse({
        'items': [{
            'id':          ins.pk,
            'codigo':      ins.codigo or '',
            'descripcion': ins.descripcion or '',
            'unidad':      ins.unidad or '',
            'saldo':       str(saldos.get(ins.pk, 0)),
        } for ins in qs],
    })


@requiere('puede_gestionar_logistica')
@proyecto_visible
@require_POST
def oc_crear_ajax(request, proyecto_id):
    """Crea una Orden de Compra con sus ítems (POST JSON)."""
    from decimal import Decimal, InvalidOperation
    import datetime, json
    from apps.presupuesto.models import InsumoPresupuesto

    proyecto = _get_proyecto(proyecto_id)
    try:
        data = json.loads(request.body or b'{}')
    except (ValueError, json.JSONDecodeError):
        return JsonResponse({'ok': False, 'error': 'Payload inválido.'}, status=400)

    prov_id = data.get('proveedor_id') or None
    proveedor = Proveedor.objects.filter(pk=prov_id).first() if prov_id else None
    if not proveedor:
        return JsonResponse({'ok': False, 'error': 'Elige un proveedor.'}, status=400)

    try:
        fecha = datetime.date.fromisoformat((data.get('fecha_entrega') or '').strip())
    except ValueError:
        return JsonResponse({'ok': False, 'error': 'Fecha inválida.'}, status=400)

    tipo_pago = (data.get('tipo_pago') or 'EFECTIVO').upper()
    if tipo_pago not in dict(TIPOS_PAGO_OC):
        tipo_pago = 'EFECTIVO'
    numero_factura = (data.get('numero_factura') or '').strip()[:50]
    observaciones  = (data.get('observaciones') or '').strip()

    try:
        costo_envio = Decimal(str(data.get('costo_envio') or '0'))
    except InvalidOperation:
        costo_envio = Decimal('0')
    if costo_envio < 0:
        costo_envio = Decimal('0')

    items_raw = data.get('items') or []
    if not items_raw:
        return JsonResponse({'ok': False, 'error': 'Agrega al menos un ítem.'}, status=400)

    items = []
    for it in items_raw:
        try:
            cant = Decimal(str(it.get('cantidad') or '0'))
            pu   = Decimal(str(it.get('precio_unitario') or '0'))
        except InvalidOperation:
            continue
        desc = (it.get('descripcion') or '').strip()
        if cant <= 0 or not desc:
            continue
        ins_id = it.get('insumo_id') or None
        insumo = InsumoPresupuesto.objects.filter(pk=ins_id).first() if ins_id else None
        items.append({
            'insumo':      insumo,
            'descripcion': desc[:400],
            'unidad':      (it.get('unidad') or '').strip()[:20],
            'cantidad':    cant,
            'precio_unitario': pu,
        })
    if not items:
        return JsonResponse({'ok': False, 'error': 'Los ítems enviados no son válidos.'}, status=400)

    # No permitir el mismo insumo repetido en la misma OC.
    vistos = set()
    for it in items:
        if it['insumo']:
            if it['insumo'].pk in vistos:
                return JsonResponse({
                    'ok': False,
                    'error': f'El insumo "{it["insumo"].descripcion}" aparece más de una vez. '
                             f'Juntá la cantidad en una sola fila.',
                }, status=400)
            vistos.add(it['insumo'].pk)

    # Validar que la cantidad de cada item con insumo asociado no supere el
    # saldo comprable (aprobada total − ya comprada en otras OC).
    saldos = _saldos_comprables(proyecto)
    errores_saldo = []
    for it in items:
        if not it['insumo']:
            continue
        iid = it['insumo'].pk
        disponible = saldos.get(iid, Decimal('0'))
        if it['cantidad'] > disponible:
            errores_saldo.append(
                f'"{it["insumo"].descripcion}": querés comprar {it["cantidad"]} pero solo quedan '
                f'{disponible} aprobadas por comprar.'
            )
    if errores_saldo:
        return JsonResponse({'ok': False, 'error': ' '.join(errores_saldo)}, status=400)

    from django.db import transaction
    with transaction.atomic():
        numero = _siguiente_numero_oc(proyecto)
        oc = OrdenCompraLog.objects.create(
            proyecto=proyecto,
            numero=numero,
            proveedor=proveedor,
            fecha_entrega=fecha,
            tipo_pago=tipo_pago,
            numero_factura=numero_factura,
            costo_envio=costo_envio,
            observaciones=observaciones,
            created_by=request.user,
        )
        for it in items:
            DetalleOrdenCompraLog.objects.create(
                orden=oc,
                insumo=it['insumo'],
                descripcion=it['descripcion'],
                unidad=it['unidad'],
                cantidad=it['cantidad'],
                precio_unitario=it['precio_unitario'],
            )

    log(request, 'CREAR', 'Logística',
        f'Orden de compra {oc.numero} creada en {proyecto.codigo} ({proveedor.razon_social})')
    return JsonResponse({'ok': True, 'id': oc.pk, 'numero': oc.numero})


@requiere('puede_ver_logistica')
@proyecto_visible
def oc_detalle_ajax(request, proyecto_id, pk):
    """GET AJAX: datos completos de la OC para mostrar en modal de detalle."""
    proyecto = _get_proyecto(proyecto_id)
    try:
        oc = (OrdenCompraLog.objects
              .select_related('proveedor', 'created_by')
              .prefetch_related('detalles')
              .get(pk=pk, proyecto=proyecto))
    except OrdenCompraLog.DoesNotExist:
        return JsonResponse({'ok': False, 'error': 'No encontrada.'}, status=404)

    return JsonResponse({
        'ok': True,
        'numero':         oc.numero,
        'proveedor':      oc.proveedor.razon_social if oc.proveedor else '—',
        'ruc':            oc.proveedor.ruc if oc.proveedor else '',
        'fecha_entrega':  oc.fecha_entrega.isoformat() if oc.fecha_entrega else '',
        'tipo_pago':      oc.get_tipo_pago_display(),
        'numero_factura': oc.numero_factura,
        'costo_envio':    str(oc.costo_envio),
        'observaciones':  oc.observaciones,
        'created_at':     oc.created_at.strftime('%d/%m/%Y %H:%M'),
        'created_by':     (oc.created_by.get_full_name() or oc.created_by.username) if oc.created_by else '—',
        'subtotal':       str(oc.subtotal_items()),
        'total':          str(oc.total()),
        'items': [{
            'codigo':      (d.insumo.codigo if d.insumo else ''),
            'descripcion': d.descripcion,
            'unidad':      d.unidad,
            'cantidad':    str(d.cantidad),
            'precio_unitario': str(d.precio_unitario),
            'subtotal':    str(d.subtotal()),
        } for d in oc.detalles.all()],
    })


@requiere('puede_gestionar_logistica')
@proyecto_visible
@require_POST
def oc_eliminar_ajax(request, proyecto_id, pk):
    """Soft delete: marca deleted_at. La OC sigue en BD pero sale de la lista
    activa; su cantidad deja de contar en _saldos_comprables y se puede restaurar
    desde la pestaña "Compras eliminadas"."""
    import datetime
    proyecto = _get_proyecto(proyecto_id)
    try:
        oc = OrdenCompraLog.objects.get(pk=pk, proyecto=proyecto, deleted_at__isnull=True)
    except OrdenCompraLog.DoesNotExist:
        return JsonResponse({'ok': False, 'error': 'No encontrada.'}, status=404)
    if oc.guias_remision.exclude(estado='ANULADO').exists():
        return JsonResponse({
            'ok': False,
            'error': 'No se puede eliminar: la orden ya está en una guía de remisión activa.',
        }, status=400)
    oc.deleted_at = datetime.datetime.now()
    oc.deleted_by = request.user if request.user.is_authenticated else None
    oc.save(update_fields=['deleted_at', 'deleted_by'])
    log(request, 'ELIMINAR', 'Logística', f'Orden de compra {oc.numero} eliminada de {proyecto.codigo}')
    return JsonResponse({'ok': True})


@require_POST
@requiere('puede_gestionar_logistica')
@proyecto_visible
def oc_restaurar_ajax(request, proyecto_id, pk):
    """Restaura una OC eliminada (quita deleted_at)."""
    proyecto = _get_proyecto(proyecto_id)
    try:
        oc = OrdenCompraLog.objects.get(pk=pk, proyecto=proyecto, deleted_at__isnull=False)
    except OrdenCompraLog.DoesNotExist:
        return JsonResponse({'ok': False, 'error': 'No encontrada.'}, status=404)
    oc.deleted_at = None
    oc.deleted_by = None
    oc.save(update_fields=['deleted_at', 'deleted_by'])
    log(request, 'EDITAR', 'Logística', f'Orden de compra {oc.numero} restaurada en {proyecto.codigo}')
    return JsonResponse({'ok': True})


@requiere('puede_ver_logistica')
@proyecto_visible
def compras_eliminadas_log(request, proyecto_id):
    """Lista de Órdenes de Compra eliminadas (soft delete) del proyecto."""
    from django.db.models import Q
    proyecto = _get_proyecto(proyecto_id)
    q = (request.GET.get('q') or '').strip()
    qs = (OrdenCompraLog.objects
          .filter(proyecto=proyecto, deleted_at__isnull=False)
          .select_related('proveedor', 'deleted_by')
          .prefetch_related('detalles')
          .order_by('-deleted_at'))
    if q:
        qs = qs.filter(Q(numero__icontains=q) |
                       Q(proveedor__razon_social__icontains=q) |
                       Q(proveedor__ruc__icontains=q) |
                       Q(numero_factura__icontains=q))
    items = []
    for oc in qs:
        items.append({
            'obj':   oc,
            'items_n': oc.detalles.count(),
            'total': oc.total(),
        })
    return render(request, 'logistica/compras_eliminadas_log.html', {
        'proyecto': proyecto,
        'items':    items,
        'q':        q,
        'total':    qs.count(),
    })


@requiere('puede_ver_logistica')
@proyecto_visible
def proveedores_log(request, proyecto_id):
    """Catálogo global de proveedores — lista con filtros."""
    from django.db.models import Q

    proyecto = _get_proyecto(proyecto_id)
    q      = (request.GET.get('q') or '').strip()
    estado = (request.GET.get('estado') or '').strip()

    qs = Proveedor.objects.all()
    if q:
        qs = qs.filter(Q(razon_social__icontains=q) | Q(ruc__icontains=q))
    if estado == 'activos':
        qs = qs.filter(activo=True)
    elif estado == 'inactivos':
        qs = qs.filter(activo=False)

    items = [{'obj': p} for p in qs]

    return render(request, 'logistica/proveedores_log.html', {
        'proyecto': proyecto,
        'items':    items,
        'q':        q,
        'estado':   estado,
        'total':    qs.count(),
    })


def _parse_json(request):
    import json
    try:
        return json.loads(request.body or b'{}')
    except (ValueError, json.JSONDecodeError):
        return None


@requiere('puede_ver_logistica')
@proyecto_visible
def proveedor_buscar_ajax(request, proyecto_id):
    """GET AJAX: devuelve proveedores activos del catálogo que matchean el
    texto en razón social o RUC. Usado por el autocompletar del modal de
    cotización."""
    q = (request.GET.get('q') or '').strip()
    qs = Proveedor.objects.filter(activo=True)
    if q:
        from django.db.models import Q
        qs = qs.filter(Q(razon_social__icontains=q) | Q(ruc__icontains=q))
    qs = qs.order_by('razon_social')[:20]
    return JsonResponse({
        'items': [{
            'id':           p.pk,
            'razon_social': p.razon_social,
            'ruc':          p.ruc,
            'direccion':    p.direccion,
            'telefono':     p.telefono,
        } for p in qs],
    })


@requiere('puede_ver_logistica')
@proyecto_visible
@require_POST
def proveedor_guardar_ajax(request, proyecto_id, pk=None):
    """POST AJAX: crea o edita un proveedor.

    - pk=None → crea nuevo.
    - pk=<id> → edita existente.
    """
    data = _parse_json(request)
    if data is None:
        return JsonResponse({'ok': False, 'error': 'Payload inválido.'}, status=400)

    ruc                      = (data.get('ruc') or '').strip()
    razon_social             = (data.get('razon_social') or '').strip()
    nombre_comercial         = (data.get('nombre_comercial') or '').strip()
    telefono                 = (data.get('telefono') or '').strip()
    email                    = (data.get('email') or '').strip()
    persona_contacto         = (data.get('persona_contacto') or '').strip()
    direccion                = (data.get('direccion') or '').strip()
    referencia               = (data.get('referencia') or '').strip()
    estado_sunat             = (data.get('estado_sunat') or '').strip()
    condicion_sunat          = (data.get('condicion_sunat') or '').strip()
    tipo_contribuyente       = (data.get('tipo_contribuyente') or '').strip()
    fecha_inicio_actividades = (data.get('fecha_inicio_actividades') or '').strip()

    if not razon_social:
        return JsonResponse({'ok': False, 'error': 'La razón social es obligatoria.'}, status=400)
    if ruc and not (len(ruc) in (8, 11) and ruc.isdigit()):
        return JsonResponse({'ok': False, 'error': 'RUC debe ser 11 dígitos, DNI 8.'}, status=400)

    if pk:
        try:
            prov = Proveedor.objects.get(pk=pk)
        except Proveedor.DoesNotExist:
            return JsonResponse({'ok': False, 'error': 'Proveedor no encontrado.'}, status=404)
    else:
        prov = Proveedor()

    prov.ruc                      = ruc
    prov.razon_social             = razon_social
    prov.nombre_comercial         = nombre_comercial
    prov.telefono                 = telefono
    prov.email                    = email
    prov.persona_contacto         = persona_contacto
    prov.direccion                = direccion
    prov.referencia               = referencia
    prov.estado_sunat             = estado_sunat
    prov.condicion_sunat          = condicion_sunat
    prov.tipo_contribuyente       = tipo_contribuyente
    prov.fecha_inicio_actividades = fecha_inicio_actividades
    prov.save()
    return JsonResponse({'ok': True, 'id': prov.pk})


@requiere('puede_ver_logistica')
@proyecto_visible
def proveedor_detalle_ajax(request, proyecto_id, pk):
    """GET AJAX: datos del proveedor para precargar el modal de edición."""
    try:
        p = Proveedor.objects.get(pk=pk)
    except Proveedor.DoesNotExist:
        return JsonResponse({'ok': False, 'error': 'Proveedor no encontrado.'}, status=404)
    return JsonResponse({
        'ok': True,
        'proveedor': {
            'id': p.pk, 'ruc': p.ruc, 'razon_social': p.razon_social,
            'nombre_comercial': p.nombre_comercial, 'telefono': p.telefono,
            'email': p.email, 'persona_contacto': p.persona_contacto,
            'direccion': p.direccion, 'referencia': p.referencia, 'activo': p.activo,
            'estado_sunat':             p.estado_sunat,
            'condicion_sunat':          p.condicion_sunat,
            'tipo_contribuyente':       p.tipo_contribuyente,
            'fecha_inicio_actividades': p.fecha_inicio_actividades,
        },
    })


@requiere('puede_ver_logistica')
@proyecto_visible
@require_POST
def proveedor_toggle_ajax(request, proyecto_id, pk):
    """POST AJAX: activa/desactiva un proveedor (no se elimina)."""
    try:
        p = Proveedor.objects.get(pk=pk)
    except Proveedor.DoesNotExist:
        return JsonResponse({'ok': False, 'error': 'Proveedor no encontrado.'}, status=404)
    p.activo = not p.activo
    p.save(update_fields=['activo'])
    return JsonResponse({'ok': True, 'activo': p.activo})


@requiere('puede_ver_logistica')
@proyecto_visible
@require_POST
def proveedor_eliminar_ajax(request, proyecto_id, pk):
    """POST AJAX: borra un proveedor."""
    try:
        p = Proveedor.objects.get(pk=pk)
    except Proveedor.DoesNotExist:
        return JsonResponse({'ok': False, 'error': 'Proveedor no encontrado.'}, status=404)
    p.delete()
    return JsonResponse({'ok': True})


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
    """Entrada del módulo Reportes — redirige al primer tab (Req. vs Atenciones)."""
    return redirect('logistica:vs_atenciones', proyecto_id=proyecto_id)


@requiere('puede_revisar_reqs_log')
@proyecto_visible
def vs_atenciones_log(request, proyecto_id):
    """Réplica de Req vs Atenciones para el área de Logística.

    Usa el helper `consolidar_vs_atenciones` de requerimientos para no duplicar lógica.
    """
    from apps.requerimientos.views import consolidar_vs_atenciones
    proyecto = _get_proyecto(proyecto_id)
    return render(request, 'logistica/vs_atenciones.html', {
        'proyecto': proyecto,
        'filas': consolidar_vs_atenciones(proyecto),
    })


@requiere('puede_ver_logistica')
@proyecto_visible
def cuadrilla_log(request, proyecto_id):
    """Vista read-only de Personal y Cuadrillas del proyecto (replica para Logística)."""
    from django.db.models import Count
    from apps.maquinaria.models import Trabajador, Cuadrilla
    proyecto = _get_proyecto(proyecto_id)
    trabajadores = (
        Trabajador.objects
        .filter(proyecto=proyecto)
        .select_related('tipo_personal')
        .order_by('apellidos', 'nombres')
    )
    cuadrillas = (
        Cuadrilla.objects
        .filter(proyecto=proyecto)
        .select_related('capataz')
        .annotate(n_integrantes=Count('integrantes'))
        .order_by('nombre')
    )
    return render(request, 'logistica/cuadrilla.html', {
        'proyecto':     proyecto,
        'trabajadores': trabajadores,
        'cuadrillas':   cuadrillas,
    })


@requiere('puede_ver_logistica')
@proyecto_visible
def maquinaria_log(request, proyecto_id):
    """Vista read-only del catálogo de Maquinaria con uso en el proyecto (replica para Logística)."""
    from django.db.models import Sum, Count, Q
    from apps.maquinaria.models import Maquinaria, RegistroMaquinaria
    proyecto = _get_proyecto(proyecto_id)
    maquinas = (
        Maquinaria.objects.filter(activo=True)
        .annotate(
            total_hm=Sum('registromaquinaria__horas', filter=Q(registromaquinaria__proyecto=proyecto)),
            n_turnos=Count('registromaquinaria', filter=Q(registromaquinaria__proyecto=proyecto)),
        )
        .order_by('codigo')
    )
    total_hm_proyecto = RegistroMaquinaria.objects.filter(proyecto=proyecto).aggregate(t=Sum('horas'))['t'] or 0
    return render(request, 'logistica/maquinaria.html', {
        'proyecto':          proyecto,
        'maquinas':          maquinas,
        'total_hm_proyecto': total_hm_proyecto,
    })
