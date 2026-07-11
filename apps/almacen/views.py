from decimal import Decimal
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.http import JsonResponse
from django.db.models import Q, Sum
from apps.proyectos.models import Proyecto
from apps.presupuesto.models import InsumoPresupuesto, TIPOS_RECURSO
from apps.registro.utils import log, notificar
from .models import (
    Entrada, DetalleEntrada,
    Salida, DetalleSalida,
    Cotizacion, DetalleCotizacion,
    OrdenCompra, DetalleOrdenCompra,
    ESTADOS_OC,
)
from .forms import (
    EntradaForm, DetalleEntradaFormSet,
    SalidaForm, DetalleSalidaFormSet,
    CotizacionForm, DetalleCotizacionFormSet,
    OrdenCompraForm, DetalleOrdenCompraFormSet,
)
from apps.requerimientos.models import Requerimiento


def _sync_insumo_snapshot(detalle):
    """Populate descripcion/unidad snapshot from insumo FK if blank."""
    if detalle.insumo:
        if not detalle.descripcion:
            detalle.descripcion = detalle.insumo.descripcion
        if not detalle.unidad:
            detalle.unidad = detalle.insumo.unidad
    detalle.save()


def dashboard(request, proyecto_id):
    proyecto = get_object_or_404(Proyecto, pk=proyecto_id)
    ctx = {
        'proyecto': proyecto,
        'total_requerimientos': proyecto.requerimientos.count(),
        'total_entradas': proyecto.entradas.count(),
        'total_salidas': proyecto.salidas.count(),
        'total_cotizaciones': proyecto.cotizaciones.count(),
        'total_ordenes': proyecto.ordenes_compra.count(),
        'ultimos_req': proyecto.requerimientos.all()[:5],
        'ultimas_entradas': proyecto.entradas.all()[:5],
        'ultimas_salidas': proyecto.salidas.all()[:5],
    }
    return render(request, 'almacen/dashboard.html', ctx)


# ── Stock / Kardex ───────────────────────────────────────────────────────────

def stock(request, proyecto_id):
    proyecto = get_object_or_404(Proyecto, pk=proyecto_id)
    tipo_sel = request.GET.get('tipo', '')

    entradas_agg = {
        r['insumo_id']: r['total']
        for r in DetalleEntrada.objects
        .filter(entrada__proyecto=proyecto)
        .values('insumo_id')
        .annotate(total=Sum('cantidad'))
    }
    salidas_agg = {
        r['insumo_id']: r['total']
        for r in DetalleSalida.objects
        .filter(salida__proyecto=proyecto)
        .values('insumo_id')
        .annotate(total=Sum('cantidad'))
    }

    insumo_ids = set(entradas_agg) | set(salidas_agg)
    insumo_ids.discard(None)
    qs = InsumoPresupuesto.objects.filter(pk__in=insumo_ids)
    if tipo_sel:
        qs = qs.filter(tipo=tipo_sel)

    items = []
    for ins in qs:
        entrada = entradas_agg.get(ins.pk, Decimal('0'))
        salida  = salidas_agg.get(ins.pk, Decimal('0'))
        items.append({
            'insumo': ins,
            'total_entrada': entrada,
            'total_salida':  salida,
            'saldo': entrada - salida,
        })
    items.sort(key=lambda x: x['insumo'].codigo or '')

    return render(request, 'almacen/stock.html', {
        'proyecto': proyecto,
        'items': items,
        'tipos': TIPOS_RECURSO,
        'tipo_sel': tipo_sel,
    })


def consumo(request, proyecto_id):
    proyecto = get_object_or_404(Proyecto, pk=proyecto_id)
    tipo_sel = request.GET.get('tipo', '')
    desde    = request.GET.get('desde', '')
    hasta    = request.GET.get('hasta', '')

    qs = DetalleSalida.objects.filter(salida__proyecto=proyecto).select_related('insumo', 'salida')
    if desde:
        qs = qs.filter(salida__fecha__gte=desde)
    if hasta:
        qs = qs.filter(salida__fecha__lte=hasta)
    if tipo_sel:
        qs = qs.filter(insumo__tipo=tipo_sel)

    agg = {}
    for det in qs:
        key = det.insumo_id if det.insumo_id else f'__{det.descripcion}'
        if key not in agg:
            agg[key] = {
                'insumo': det.insumo,
                'descripcion': det.insumo.descripcion if det.insumo else (det.descripcion or '—'),
                'unidad': det.insumo.unidad if det.insumo else det.unidad,
                'tipo_display': det.insumo.get_tipo_display() if det.insumo else '—',
                'total_cantidad': Decimal('0'),
                'total_costo': Decimal('0'),
                'num_registros': 0,
            }
        agg[key]['total_cantidad'] += det.cantidad
        agg[key]['total_costo']    += det.subtotal()
        agg[key]['num_registros']  += 1

    items = sorted(agg.values(), key=lambda x: x['descripcion'].lower())
    total_costo = sum(i['total_costo'] for i in items)

    return render(request, 'almacen/consumo.html', {
        'proyecto': proyecto,
        'items': items,
        'total_costo': total_costo,
        'tipos': TIPOS_RECURSO,
        'tipo_sel': tipo_sel,
        'desde': desde,
        'hasta': hasta,
    })


def kardex(request, proyecto_id, insumo_id):
    proyecto = get_object_or_404(Proyecto, pk=proyecto_id)
    insumo = get_object_or_404(InsumoPresupuesto, pk=insumo_id)

    movimientos = []

    for d in (DetalleEntrada.objects
              .filter(entrada__proyecto=proyecto, insumo=insumo)
              .select_related('entrada').order_by('entrada__fecha')):
        movimientos.append({
            'fecha':      d.entrada.fecha,
            'tipo':       'ENTRADA',
            'referencia': f'GUIA {d.entrada.serie}-{d.entrada.numero_guia}',
            'detalle':    d.entrada.proveedor or '—',
            'entrada':    d.cantidad,
            'salida':     None,
            'precio':     d.precio_unitario,
        })

    for d in (DetalleSalida.objects
              .filter(salida__proyecto=proyecto, insumo=insumo)
              .select_related('salida').order_by('salida__fecha')):
        movimientos.append({
            'fecha':      d.salida.fecha,
            'tipo':       'SALIDA',
            'referencia': f'SAL-{d.salida.numero}',
            'detalle':    d.salida.destino or '—',
            'entrada':    None,
            'salida':     d.cantidad,
            'precio':     d.precio_unitario,
        })

    movimientos.sort(key=lambda x: x['fecha'])

    saldo = Decimal('0')
    for m in movimientos:
        if m['entrada']:
            saldo += m['entrada']
        if m['salida']:
            saldo -= m['salida']
        m['saldo'] = saldo

    return render(request, 'almacen/kardex.html', {
        'proyecto': proyecto,
        'insumo': insumo,
        'movimientos': movimientos,
        'saldo_final': saldo,
    })


# ── Entradas ────────────────────────────────────────────────────────────────

def entrada_lista(request, proyecto_id):
    proyecto = get_object_or_404(Proyecto, pk=proyecto_id)
    return render(request, 'almacen/entrada_lista.html', {
        'proyecto': proyecto, 'entradas': proyecto.entradas.all(),
    })


def entrada_detalle(request, pk):
    entrada = get_object_or_404(Entrada, pk=pk)
    return render(request, 'almacen/entrada_detalle.html', {'entrada': entrada, 'proyecto': entrada.proyecto})


def entrada_crear(request, proyecto_id):
    proyecto = get_object_or_404(Proyecto, pk=proyecto_id)
    if request.method == 'POST':
        form = EntradaForm(request.POST, proyecto=proyecto)
        formset = DetalleEntradaFormSet(request.POST, prefix='detalles')
        if form.is_valid() and formset.is_valid():
            entrada = form.save(commit=False)
            entrada.proyecto = proyecto
            entrada.save()
            for f in formset:
                if f.cleaned_data and not f.cleaned_data.get('DELETE'):
                    d = f.save(commit=False)
                    d.entrada = entrada
                    _sync_insumo_snapshot(d)
            log(request, 'CREAR', 'Almacén',
                f'Entrada GUIA {entrada.serie}-{entrada.numero_guia} registrada en {proyecto.codigo}')
            notificar(
                f'Nueva entrada registrada — Guía {entrada.serie}-{entrada.numero_guia}',
                mensaje=f'Por {request.user.get_full_name() or request.user.username} en {proyecto.codigo}',
                tipo='success',
            )
            messages.success(request, 'Entrada registrada.')
            return redirect('almacen:entrada_detalle', pk=entrada.pk)
    else:
        form = EntradaForm(proyecto=proyecto)
        formset = DetalleEntradaFormSet(prefix='detalles')
    return render(request, 'almacen/entrada_form.html', {
        'form': form, 'formset': formset, 'proyecto': proyecto, 'titulo': 'Nueva Entrada',
    })


def entrada_editar(request, pk):
    entrada = get_object_or_404(Entrada, pk=pk)
    proyecto = entrada.proyecto
    if request.method == 'POST':
        form = EntradaForm(request.POST, instance=entrada, proyecto=proyecto)
        formset = DetalleEntradaFormSet(request.POST, instance=entrada, prefix='detalles')
        if form.is_valid() and formset.is_valid():
            form.save()
            for d in formset.save():
                _sync_insumo_snapshot(d)
            log(request, 'EDITAR', 'Almacén',
                f'Entrada GUIA {entrada.serie}-{entrada.numero_guia} editada en {proyecto.codigo}')
            messages.success(request, 'Entrada actualizada.')
            return redirect('almacen:entrada_detalle', pk=entrada.pk)
    else:
        form = EntradaForm(instance=entrada, proyecto=proyecto)
        formset = DetalleEntradaFormSet(instance=entrada, prefix='detalles')
    return render(request, 'almacen/entrada_form.html', {
        'form': form, 'formset': formset, 'proyecto': proyecto, 'titulo': 'Editar Entrada',
    })


def entrada_eliminar(request, pk):
    entrada = get_object_or_404(Entrada, pk=pk)
    proyecto = entrada.proyecto
    if request.method == 'POST':
        ref = f'GUIA {entrada.serie}-{entrada.numero_guia}'
        entrada.delete()
        log(request, 'ELIMINAR', 'Almacén', f'Entrada {ref} eliminada en {proyecto.codigo}')
        messages.success(request, 'Entrada eliminada.')
        return redirect('almacen:entrada_lista', proyecto_id=proyecto.pk)
    return render(request, 'almacen/confirmar_eliminar.html', {'obj': entrada, 'proyecto': proyecto})


def entrada_aceptar(request, pk):
    entrada = get_object_or_404(Entrada, pk=pk)
    if request.method == 'POST' and entrada.estado == 'PENDIENTE':
        entrada.estado = 'ACEPTADO'
        entrada.save()
        log(request, 'EDITAR', 'Almacén',
            f'Guía {entrada.numero_guia} aceptada en {entrada.proyecto.codigo}')
        notificar(
            f'Guía {entrada.numero_guia} aceptada',
            mensaje=f'Almacén confirmó la recepción de la guía {entrada.numero_guia}.',
            tipo='success',
        )
        messages.success(request, f'Guía {entrada.numero_guia} aceptada.')
    return redirect('almacen:entrada_lista', proyecto_id=entrada.proyecto.pk)


def entrada_rechazar(request, pk):
    entrada = get_object_or_404(Entrada, pk=pk)
    if request.method == 'POST' and entrada.estado == 'PENDIENTE':
        motivo = request.POST.get('motivo', '').strip()
        entrada.estado = 'RECHAZADO'
        entrada.motivo_rechazo = motivo
        entrada.save()
        log(request, 'EDITAR', 'Almacén',
            f'Guía {entrada.numero_guia} rechazada en {entrada.proyecto.codigo}. Motivo: {motivo or "—"}')
        notificar(
            f'Guía {entrada.numero_guia} rechazada',
            mensaje=f'Almacén rechazó la guía {entrada.numero_guia}. Motivo: {motivo or "—"}',
            tipo='danger',
        )
        messages.warning(request, f'Guía {entrada.numero_guia} rechazada.')
    return redirect('almacen:entrada_lista', proyecto_id=entrada.proyecto.pk)


# ── Salidas ─────────────────────────────────────────────────────────────────

def salida_lista(request, proyecto_id):
    proyecto = get_object_or_404(Proyecto, pk=proyecto_id)
    return render(request, 'almacen/salida_lista.html', {
        'proyecto': proyecto, 'salidas': proyecto.salidas.all(),
    })


def salida_detalle(request, pk):
    salida = get_object_or_404(Salida, pk=pk)
    return render(request, 'almacen/salida_detalle.html', {'salida': salida, 'proyecto': salida.proyecto})


def salida_crear(request, proyecto_id):
    from apps.requerimientos.models import Requerimiento as Req
    proyecto = get_object_or_404(Proyecto, pk=proyecto_id)
    reqs_aprobados = proyecto.requerimientos.filter(estado='APROBADO')
    if request.method == 'POST':
        form = SalidaForm(request.POST)
        formset = DetalleSalidaFormSet(request.POST, prefix='detalles')
        if form.is_valid() and formset.is_valid():
            salida = form.save(commit=False)
            salida.proyecto = proyecto
            req_id = request.POST.get('requerimiento_id')
            if req_id:
                try:
                    req = Req.objects.get(pk=req_id, proyecto=proyecto)
                    salida.requerimiento = req
                except Req.DoesNotExist:
                    pass
            salida.save()
            for f in formset:
                if f.cleaned_data and not f.cleaned_data.get('DELETE'):
                    d = f.save(commit=False)
                    d.salida = salida
                    _sync_insumo_snapshot(d)
            if salida.requerimiento:
                salida.requerimiento.estado = 'ATENDIDO'
                salida.requerimiento.save()
            log(request, 'CREAR', 'Almacén',
                f'Salida SAL-{salida.numero} registrada en {proyecto.codigo}')
            messages.success(request, 'Salida registrada.')
            return redirect('almacen:salida_detalle', pk=salida.pk)
    else:
        form = SalidaForm()
        formset = DetalleSalidaFormSet(prefix='detalles')
    return render(request, 'almacen/salida_form.html', {
        'form': form, 'formset': formset, 'proyecto': proyecto,
        'titulo': 'Nueva Salida', 'reqs_aprobados': reqs_aprobados,
    })


def salida_editar(request, pk):
    salida = get_object_or_404(Salida, pk=pk)
    proyecto = salida.proyecto
    if request.method == 'POST':
        form = SalidaForm(request.POST, instance=salida)
        formset = DetalleSalidaFormSet(request.POST, instance=salida, prefix='detalles')
        if form.is_valid() and formset.is_valid():
            form.save()
            for d in formset.save():
                _sync_insumo_snapshot(d)
            log(request, 'EDITAR', 'Almacén',
                f'Salida SAL-{salida.numero} editada en {proyecto.codigo}')
            messages.success(request, 'Salida actualizada.')
            return redirect('almacen:salida_detalle', pk=salida.pk)
    else:
        form = SalidaForm(instance=salida)
        formset = DetalleSalidaFormSet(instance=salida, prefix='detalles')
    return render(request, 'almacen/salida_form.html', {
        'form': form, 'formset': formset, 'proyecto': proyecto, 'titulo': 'Editar Salida',
    })


def salida_eliminar(request, pk):
    salida = get_object_or_404(Salida, pk=pk)
    proyecto = salida.proyecto
    if request.method == 'POST':
        ref = f'SAL-{salida.numero}'
        salida.delete()
        log(request, 'ELIMINAR', 'Almacén', f'Salida {ref} eliminada en {proyecto.codigo}')
        messages.success(request, 'Salida eliminada.')
        return redirect('almacen:salida_lista', proyecto_id=proyecto.pk)
    return render(request, 'almacen/confirmar_eliminar.html', {'obj': salida, 'proyecto': proyecto})


# ── Cotizaciones ─────────────────────────────────────────────────────────────

def cot_lista(request, proyecto_id):
    proyecto = get_object_or_404(Proyecto, pk=proyecto_id)
    return render(request, 'almacen/cot_lista.html', {
        'proyecto': proyecto, 'cotizaciones': proyecto.cotizaciones.all(),
    })


def cot_detalle(request, pk):
    cot = get_object_or_404(Cotizacion, pk=pk)
    return render(request, 'almacen/cot_detalle.html', {'cot': cot, 'proyecto': cot.proyecto})


def cot_crear(request, proyecto_id):
    proyecto = get_object_or_404(Proyecto, pk=proyecto_id)
    if request.method == 'POST':
        form = CotizacionForm(request.POST)
        formset = DetalleCotizacionFormSet(request.POST, prefix='detalles')
        if form.is_valid() and formset.is_valid():
            cot = form.save(commit=False)
            cot.proyecto = proyecto
            cot.save()
            for f in formset:
                if f.cleaned_data and not f.cleaned_data.get('DELETE'):
                    d = f.save(commit=False)
                    d.cotizacion = cot
                    _sync_insumo_snapshot(d)
            log(request, 'CREAR', 'Almacén',
                f'Cotización COT-{cot.numero} creada en {proyecto.codigo}')
            messages.success(request, 'Cotización registrada.')
            return redirect('almacen:cot_detalle', pk=cot.pk)
    else:
        form = CotizacionForm()
        formset = DetalleCotizacionFormSet(prefix='detalles')
    return render(request, 'almacen/cot_form.html', {
        'form': form, 'formset': formset, 'proyecto': proyecto, 'titulo': 'Nueva Cotización',
    })


def cot_desde_req(request, proyecto_id, req_pk):
    """Genera una cotización pre-cargada con los ítems de un requerimiento."""
    from django.utils.timezone import now
    from apps.requerimientos.models import Requerimiento

    if request.method != 'POST':
        return redirect('almacen:cot_lista', proyecto_id=proyecto_id)

    proyecto = get_object_or_404(Proyecto, pk=proyecto_id)
    req = get_object_or_404(Requerimiento, pk=req_pk, proyecto=proyecto)

    ultimo = proyecto.cotizaciones.order_by('-pk').first()
    try:
        siguiente = int(''.join(filter(str.isdigit, str(ultimo.numero)))) + 1 if ultimo else 1
    except (ValueError, AttributeError):
        siguiente = proyecto.cotizaciones.count() + 1

    cot = Cotizacion.objects.create(
        proyecto=proyecto,
        numero=str(siguiente).zfill(3),
        fecha=now().date(),
        proveedor='',
        estado='PENDIENTE',
        observaciones=f'Generada desde REQ-{req.numero}',
    )

    detalles = req.detalles.select_related('insumo').all()
    for d in detalles:
        if not d.descripcion and not d.insumo:
            continue
        cantidad = d.cantidad_aprobada if d.cantidad_aprobada is not None else d.cantidad_requerida
        DetalleCotizacion.objects.create(
            cotizacion=cot,
            insumo=d.insumo,
            descripcion=d.descripcion or (d.insumo.descripcion if d.insumo else ''),
            cantidad=cantidad,
            precio_unitario=Decimal('0'),
            unidad=d.unidad,
        )

    if not req.cotizacion_sistema_id:
        req.cotizacion_sistema = cot
        req.save(update_fields=['cotizacion_sistema'])

    log(request, 'CREAR', 'Almacén',
        f'Cotización COT-{cot.numero} generada desde REQ-{req.numero} en {proyecto.codigo}')
    messages.success(request, f'Cotización COT-{cot.numero} generada. Completa el proveedor y precios.')
    return redirect('almacen:cot_editar', pk=cot.pk)


def cot_rapida(request, proyecto_id):
    """Crea una cotización desde el modal rápido de la lista."""
    from django.utils.dateparse import parse_date
    proyecto = get_object_or_404(Proyecto, pk=proyecto_id)
    if request.method != 'POST':
        return redirect('almacen:cot_lista', proyecto_id=proyecto_id)

    fecha     = parse_date(request.POST.get('fecha', ''))
    proveedor = request.POST.get('proveedor', '').strip()

    if not fecha or not proveedor:
        messages.error(request, 'Fecha y proveedor son obligatorios.')
        return redirect('almacen:cot_lista', proyecto_id=proyecto_id)

    # Auto-numerar
    ultimo = proyecto.cotizaciones.order_by('-pk').first()
    try:
        siguiente = int(''.join(filter(str.isdigit, str(ultimo.numero)))) + 1 if ultimo else 1
    except (ValueError, AttributeError):
        siguiente = proyecto.cotizaciones.count() + 1
    numero = str(siguiente).zfill(3)

    pdf = request.FILES.get('archivo_pdf') or None
    cot = Cotizacion.objects.create(
        proyecto=proyecto,
        numero=numero,
        fecha=fecha,
        proveedor=proveedor,
        estado='PENDIENTE',
        observaciones=request.POST.get('observaciones', '').strip(),
        archivo_pdf=pdf,
    )

    descripciones = request.POST.getlist('item_desc')
    cantidades    = request.POST.getlist('item_cant')
    precios       = request.POST.getlist('item_precio')
    unidades      = request.POST.getlist('item_und')

    for desc, cant, precio, und in zip(descripciones, cantidades, precios, unidades):
        desc = desc.strip()
        if not desc:
            continue
        try:
            cant_d   = Decimal(cant)   if cant   else Decimal('0')
            precio_d = Decimal(precio) if precio else Decimal('0')
        except Exception:
            cant_d = precio_d = Decimal('0')
        DetalleCotizacion.objects.create(
            cotizacion=cot,
            descripcion=desc,
            cantidad=cant_d,
            precio_unitario=precio_d,
            unidad=und.strip(),
        )

    log(request, 'CREAR', 'Almacén', f'Cotización COT-{cot.numero} creada rápidamente en {proyecto.codigo}')
    messages.success(request, f'Cotización COT-{cot.numero} registrada.')
    return redirect('almacen:cot_detalle', pk=cot.pk)


def cot_editar(request, pk):
    cot = get_object_or_404(Cotizacion, pk=pk)
    proyecto = cot.proyecto
    if request.method == 'POST':
        form = CotizacionForm(request.POST, instance=cot)
        formset = DetalleCotizacionFormSet(request.POST, instance=cot, prefix='detalles')
        if form.is_valid() and formset.is_valid():
            form.save()
            for d in formset.save():
                _sync_insumo_snapshot(d)
            log(request, 'EDITAR', 'Almacén',
                f'Cotización COT-{cot.numero} editada en {proyecto.codigo}')
            messages.success(request, 'Cotización actualizada.')
            return redirect('almacen:cot_detalle', pk=cot.pk)
    else:
        form = CotizacionForm(instance=cot)
        formset = DetalleCotizacionFormSet(instance=cot, prefix='detalles')
    return render(request, 'almacen/cot_form.html', {
        'form': form, 'formset': formset, 'proyecto': proyecto, 'titulo': 'Editar Cotización',
    })


def cot_eliminar(request, pk):
    cot = get_object_or_404(Cotizacion, pk=pk)
    proyecto = cot.proyecto
    if request.method == 'POST':
        ref = f'COT-{cot.numero}'
        cot.delete()
        log(request, 'ELIMINAR', 'Almacén', f'Cotización {ref} eliminada en {proyecto.codigo}')
        messages.success(request, 'Cotización eliminada.')
        return redirect('almacen:cot_lista', proyecto_id=proyecto.pk)
    return render(request, 'almacen/confirmar_eliminar.html', {'obj': cot, 'proyecto': proyecto})


# ── Órdenes de Compra ────────────────────────────────────────────────────────

def oc_lista(request, proyecto_id):
    proyecto = get_object_or_404(Proyecto, pk=proyecto_id)
    qs = proyecto.ordenes_compra.all()
    estado = request.GET.get('estado', '')
    if estado:
        qs = qs.filter(estado=estado)
    return render(request, 'almacen/oc_lista.html', {
        'proyecto': proyecto,
        'ordenes': qs,
        'estados': ESTADOS_OC,
        'estado_sel': estado,
    })


def oc_detalle(request, pk):
    oc = get_object_or_404(OrdenCompra, pk=pk)
    return render(request, 'almacen/oc_detalle.html', {'oc': oc, 'proyecto': oc.proyecto})


def oc_crear(request, proyecto_id):
    proyecto = get_object_or_404(Proyecto, pk=proyecto_id)
    if request.method == 'POST':
        form = OrdenCompraForm(request.POST, proyecto=proyecto)
        formset = DetalleOrdenCompraFormSet(request.POST, prefix='detalles')
        if form.is_valid() and formset.is_valid():
            oc = form.save(commit=False)
            oc.proyecto = proyecto
            oc.save()
            for f in formset:
                if f.cleaned_data and not f.cleaned_data.get('DELETE'):
                    d = f.save(commit=False)
                    d.orden = oc
                    _sync_insumo_snapshot(d)
            log(request, 'CREAR', 'Almacén', f'OC-{oc.numero} creada en {proyecto.codigo}')
            messages.success(request, f'OC-{oc.numero} creada.')
            return redirect('almacen:oc_detalle', pk=oc.pk)
    else:
        form = OrdenCompraForm(proyecto=proyecto)
        formset = DetalleOrdenCompraFormSet(prefix='detalles')
    return render(request, 'almacen/oc_form.html', {
        'form': form, 'formset': formset, 'proyecto': proyecto, 'titulo': 'Nueva Orden de Compra',
    })


def oc_editar(request, pk):
    oc = get_object_or_404(OrdenCompra, pk=pk)
    proyecto = oc.proyecto
    if request.method == 'POST':
        form = OrdenCompraForm(request.POST, instance=oc, proyecto=proyecto)
        formset = DetalleOrdenCompraFormSet(request.POST, instance=oc, prefix='detalles')
        if form.is_valid() and formset.is_valid():
            form.save()
            for d in formset.save():
                _sync_insumo_snapshot(d)
            log(request, 'EDITAR', 'Almacén', f'OC-{oc.numero} editada en {proyecto.codigo}')
            messages.success(request, 'Orden actualizada.')
            return redirect('almacen:oc_detalle', pk=oc.pk)
    else:
        form = OrdenCompraForm(instance=oc, proyecto=proyecto)
        formset = DetalleOrdenCompraFormSet(instance=oc, prefix='detalles')
    return render(request, 'almacen/oc_form.html', {
        'form': form, 'formset': formset, 'proyecto': proyecto, 'titulo': f'Editar OC-{oc.numero}',
    })


def oc_eliminar(request, pk):
    oc = get_object_or_404(OrdenCompra, pk=pk)
    proyecto = oc.proyecto
    if request.method == 'POST':
        ref = f'OC-{oc.numero}'
        oc.delete()
        log(request, 'ELIMINAR', 'Almacén', f'{ref} eliminada en {proyecto.codigo}')
        messages.success(request, 'Orden eliminada.')
        return redirect('almacen:oc_lista', proyecto_id=proyecto.pk)
    return render(request, 'almacen/confirmar_eliminar.html', {'obj': oc, 'proyecto': proyecto})


# ── API ───────────────────────────────────────────────────────────────────────

def api_req_detalles(request, pk):
    from apps.requerimientos.models import Requerimiento as Req
    try:
        req = Req.objects.get(pk=pk)
        data = [
            {
                'descripcion': d.descripcion or (d.insumo.descripcion if d.insumo else ''),
                'cantidad': str(d.cantidad),
                'unidad': d.unidad,
                'insumo_id': d.insumo_id or '',
            }
            for d in req.detalles.all()
        ]
    except Req.DoesNotExist:
        data = []
    return JsonResponse(data, safe=False)


def api_insumo_stock(request, insumo_id):
    pid = request.session.get('proyecto_id')
    proyecto = Proyecto.objects.filter(pk=pid).first() if pid else None
    if not proyecto:
        return JsonResponse({'stock': 0})
    entrada = DetalleEntrada.objects.filter(
        entrada__proyecto=proyecto, insumo_id=insumo_id
    ).aggregate(total=Sum('cantidad'))['total'] or 0
    salida = DetalleSalida.objects.filter(
        salida__proyecto=proyecto, insumo_id=insumo_id
    ).aggregate(total=Sum('cantidad'))['total'] or 0
    return JsonResponse({'stock': float(entrada - salida)})


def api_productos(request):
    q = request.GET.get('q', '')
    pid = request.session.get('proyecto_id')
    proyecto_activo = Proyecto.objects.filter(pk=pid).first() if pid else None
    if not proyecto_activo or not hasattr(proyecto_activo, 'presupuesto'):
        return JsonResponse([], safe=False)
    qs = proyecto_activo.presupuesto.insumos.all()
    if q:
        qs = qs.filter(Q(codigo__icontains=q) | Q(descripcion__icontains=q))
    data = [
        {
            'id': p.pk, 'codigo': p.codigo, 'descripcion': p.descripcion,
            'unidad': p.unidad,
            'cantidad': str(p.cantidad),
            'cantidad_restante': str(p.cantidad),
            'cantidad_total': str(p.cantidad_total),
        }
        for p in qs[:50]
    ]
    return JsonResponse(data, safe=False)
