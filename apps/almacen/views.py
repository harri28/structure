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
from config.permisos import requiere, proyecto_visible


def _sync_insumo_snapshot(detalle):
    """Populate descripcion/unidad snapshot from insumo FK if blank."""
    if detalle.insumo:
        if not detalle.descripcion:
            detalle.descripcion = detalle.insumo.descripcion
        if not detalle.unidad:
            detalle.unidad = detalle.insumo.unidad
    detalle.save()


@requiere('puede_ver_almacen')
@proyecto_visible
def dashboard(request, proyecto_id):
    # Si el usuario es Almacenero (crea reqs pero no aprueba), redirigir a su dashboard propio
    from config.permisos import tiene
    if tiene(request.user, 'puede_crear_requerimientos') and not tiene(request.user, 'puede_aprobar_requerimientos'):
        return redirect('almacen:dashboard_almacenero', proyecto_id=proyecto_id)
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


@requiere('puede_ver_almacen')
@proyecto_visible
def dashboard_almacenero(request, proyecto_id):
    """Dashboard específico del Almacenero — foco en su día a día:
    guías por recibir, stock general, sus solicitudes de material."""
    from apps.logistica.models import GuiaRemision
    proyecto = get_object_or_404(Proyecto, pk=proyecto_id)

    # Guías despachadas (pendientes de recibir + ya registradas)
    guias_qs = GuiaRemision.objects.filter(
        proyecto=proyecto, estado__in=['EN_TRANSITO', 'ENTREGADO']
    )
    guias_por_recibir = guias_qs.filter(entrada__isnull=True).count()
    guias_sin_ver    = guias_qs.filter(vista_por_almacen=False).count()
    ultimas_guias    = (guias_qs.select_related('transportista', 'requerimiento')
                                 .order_by('-fecha_emision', '-pk')[:5])

    # Stock: total de insumos del presupuesto
    try:
        total_insumos = proyecto.presupuesto.insumos.count()
    except Exception:
        total_insumos = 0

    # Mis solicitudes: solo las creadas por el Almacenero logueado
    mis_solicitudes_qs = proyecto.requerimientos.filter(created_by=request.user)
    ultimas_solicitudes = mis_solicitudes_qs.order_by('-fecha', '-numero')[:5]
    total_solicitudes   = mis_solicitudes_qs.count()

    return render(request, 'almacen/dashboard_almacenero.html', {
        'proyecto':          proyecto,
        'guias_por_recibir': guias_por_recibir,
        'guias_sin_ver':     guias_sin_ver,
        'ultimas_guias':     ultimas_guias,
        'total_insumos':     total_insumos,
        'ultimas_solicitudes': ultimas_solicitudes,
        'total_solicitudes':   total_solicitudes,
    })


# ── Stock / Kardex ───────────────────────────────────────────────────────────

PAGE_SIZE_STOCK = 20


STOCK_ORDER_MAP = {
    # 'codigo' usa el int casteado (_codigo_int) porque el campo es CharField pero
    # los valores son enteros amigables (1, 2, ... 100+). Ver REGLAS_NEGOCIO.md §15.
    'codigo':        ('_codigo_int', 'codigo'),
    'alpha':         ('descripcion', '_codigo_int'),
    'cantidad_desc': ('-cantidad_total', '_codigo_int'),
    'cantidad_asc':  ('cantidad_total', '_codigo_int'),
}


def _stock_query(proyecto, tipo_sel='', q='', order='codigo'):
    """Devuelve (queryset ordenado, entradas_agg, salidas_agg) para el stock del proyecto."""
    from django.db.models import Q, IntegerField
    from django.db.models.functions import Cast
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
    try:
        qs = proyecto.presupuesto.insumos.all()
    except Exception:
        qs = InsumoPresupuesto.objects.none()
    if tipo_sel:
        qs = qs.filter(tipo=tipo_sel)
    if q:
        qs = qs.filter(Q(codigo__icontains=q) | Q(descripcion__icontains=q))
    # Cast del código a entero para poder ordenar 1, 2, 3, ..., 10, ... 100 en vez de
    # 1, 10, 100, 2, ... (que es lo que da el orden lexicográfico sobre CharField).
    qs = qs.annotate(_codigo_int=Cast('codigo', IntegerField()))
    order_fields = STOCK_ORDER_MAP.get(order, STOCK_ORDER_MAP['codigo'])
    qs = qs.order_by(*order_fields)
    return qs, entradas_agg, salidas_agg


def _build_items(qs, entradas_agg, salidas_agg):
    items = []
    for ins in qs:
        entrada = entradas_agg.get(ins.pk, Decimal('0'))
        salida  = salidas_agg.get(ins.pk, Decimal('0'))
        items.append({
            'insumo': ins,
            'presupuestado': ins.cantidad_total or Decimal('0'),
            'total_entrada': entrada,
            'total_salida':  salida,
            'saldo': entrada - salida,
        })
    return items


@requiere('puede_ver_almacen')
@proyecto_visible
def stock(request, proyecto_id):
    from django.core.paginator import Paginator
    proyecto = get_object_or_404(Proyecto, pk=proyecto_id)
    tipo_sel = request.GET.get('tipo', '')
    q        = request.GET.get('q', '').strip()
    order    = request.GET.get('order', 'codigo')

    qs, entradas_agg, salidas_agg = _stock_query(proyecto, tipo_sel, q, order)
    paginator = Paginator(qs, PAGE_SIZE_STOCK)
    page_num  = request.GET.get('page') or 1
    page      = paginator.get_page(page_num)
    items     = _build_items(page.object_list, entradas_agg, salidas_agg)

    return render(request, 'almacen/stock.html', {
        'proyecto':   proyecto,
        'items':      items,
        'tipos':      TIPOS_RECURSO,
        'tipo_sel':   tipo_sel,
        'q':          q,
        'page':       page,
        'total':      paginator.count,
        'tiene_presupuesto': hasattr(proyecto, 'presupuesto') and proyecto.presupuesto is not None,
    })


@requiere('puede_ver_almacen', 'puede_gestionar_almacen_log')
@proyecto_visible
def stock_api(request, proyecto_id):
    """Endpoint JSON para búsqueda + paginación live del Stock.
    Accesible por Almacenero (puede_ver_almacen) y por Logística
    (puede_gestionar_almacen_log) para su vista informativa."""
    from django.core.paginator import Paginator
    from django.http import JsonResponse
    proyecto = get_object_or_404(Proyecto, pk=proyecto_id)
    tipo_sel = request.GET.get('tipo', '')
    q        = request.GET.get('q', '').strip()
    order    = request.GET.get('order', 'codigo')

    qs, entradas_agg, salidas_agg = _stock_query(proyecto, tipo_sel, q, order)
    paginator = Paginator(qs, PAGE_SIZE_STOCK)
    page_num  = request.GET.get('page') or 1
    page      = paginator.get_page(page_num)
    items     = _build_items(page.object_list, entradas_agg, salidas_agg)

    data = {
        'items': [
            {
                'pk':            item['insumo'].pk,
                'codigo':        item['insumo'].codigo or '',
                'descripcion':   item['insumo'].descripcion or '',
                'tipo':          item['insumo'].get_tipo_display() or '',
                'unidad':        item['insumo'].unidad or '',
                'presupuestado': f"{item['presupuestado']:.2f}",
                'total_entrada': f"{item['total_entrada']:.2f}",
                'total_salida':  f"{item['total_salida']:.2f}",
                'saldo':         f"{item['saldo']:.2f}",
                'saldo_pos':     item['saldo'] > 0,
            }
            for item in items
        ],
        'page':        page.number,
        'total_pages': paginator.num_pages,
        'count':       paginator.count,
        'has_prev':    page.has_previous(),
        'has_next':    page.has_next(),
    }
    return JsonResponse(data)


@requiere('puede_ver_almacen')
@proyecto_visible
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


@requiere('puede_ver_almacen')
@proyecto_visible
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


# ── Guías (perspectiva Almacén) ─────────────────────────────────────────────

@requiere('puede_gestionar_entradas')
@proyecto_visible
def guias_almacen_lista(request, proyecto_id):
    """Sub-módulo 'Guías' del Almacén: recibe las guías despachadas por Logística.
    Muestra todas las guías con estado EN_TRANSITO o ENTREGADO (excluye ANULADAS).
    Las no vistas por Almacén (vista_por_almacen=False) se resaltan en verde suave.
    """
    from apps.logistica.models import GuiaRemision
    proyecto = get_object_or_404(Proyecto, pk=proyecto_id)

    guias = (GuiaRemision.objects
             .filter(proyecto=proyecto, estado__in=['EN_TRANSITO', 'ENTREGADO'])
             .select_related('transportista', 'requerimiento')
             .prefetch_related('detalles')
             .order_by('-fecha_emision', '-pk'))

    return render(request, 'almacen/guias_lista.html', {
        'proyecto': proyecto,
        'guias':    guias,
    })


@requiere('puede_gestionar_entradas')
def guia_almacen_detalle(request, pk):
    """Vista readonly de una guía desde la perspectiva del Almacén.
    Al abrirse, marca la guía como vista_por_almacen=True (para que ya no aparezca
    en verde en la lista). Muestra datos + ítems no editables, con botón 'Registrar'
    abajo que lleva al form de Nueva Entrada con autofill (?guia=<pk>).
    """
    from apps.logistica.models import GuiaRemision
    guia = get_object_or_404(
        GuiaRemision.objects.select_related('proyecto', 'transportista', 'requerimiento')
                            .prefetch_related('detalles'),
        pk=pk,
    )
    if not guia.vista_por_almacen:
        guia.vista_por_almacen = True
        guia.save(update_fields=['vista_por_almacen'])
    return render(request, 'almacen/guia_almacen_detalle.html', {
        'guia':     guia,
        'proyecto': guia.proyecto,
        'guia_registrada': Entrada.objects.filter(guia=guia).exists(),
    })


# ── Entradas ────────────────────────────────────────────────────────────────

@requiere('puede_gestionar_entradas')
@proyecto_visible
def entrada_lista(request, proyecto_id):
    proyecto = get_object_or_404(Proyecto, pk=proyecto_id)
    return render(request, 'almacen/entrada_lista.html', {
        'proyecto': proyecto, 'entradas': proyecto.entradas.all(),
    })


@requiere('puede_gestionar_entradas')
def entrada_detalle(request, pk):
    entrada = get_object_or_404(Entrada, pk=pk)
    return render(request, 'almacen/entrada_detalle.html', {'entrada': entrada, 'proyecto': entrada.proyecto})


@requiere('puede_gestionar_entradas')
@proyecto_visible
def entrada_aplicar_item(request, proyecto_id, guia_pk):
    """AJAX: aplica un ítem de la guía a la BD (crea o actualiza DetalleEntrada).
    Idempotente: llamadas repetidas con el mismo insumo actualizan el registro
    en lugar de crear duplicados.
    """
    from decimal import InvalidOperation
    from datetime import date
    from django.http import JsonResponse
    from apps.logistica.models import GuiaRemision

    if request.method != 'POST':
        return JsonResponse({'ok': False, 'msg': 'Método no permitido'}, status=405)

    proyecto = get_object_or_404(Proyecto, pk=proyecto_id)
    guia = get_object_or_404(GuiaRemision, pk=guia_pk, proyecto=proyecto)

    desc      = request.POST.get('item_desc', '').strip()
    unidad    = request.POST.get('item_unidad', '').strip()
    cant_raw  = request.POST.get('item_cantidad', '0').strip()
    insumo_pk = request.POST.get('item_insumo_pk', '').strip()
    obs       = request.POST.get('item_observaciones', '').strip()

    if not desc:
        return JsonResponse({'ok': False, 'msg': 'Falta la descripción del ítem'}, status=400)
    try:
        cant = Decimal(cant_raw) if cant_raw else Decimal('0')
    except (InvalidOperation, ValueError):
        return JsonResponse({'ok': False, 'msg': 'Cantidad inválida'}, status=400)
    if cant <= 0:
        return JsonResponse({'ok': False, 'msg': 'La cantidad debe ser mayor a 0'}, status=400)

    # Resolver el insumo (si viene FK)
    insumo = None
    if insumo_pk:
        try:
            insumo = InsumoPresupuesto.objects.get(pk=int(insumo_pk))
        except (ValueError, InsumoPresupuesto.DoesNotExist):
            pass

    # Get or create Entrada (OneToOne con la guía)
    entrada = Entrada.objects.filter(guia=guia).first()
    if not entrada:
        entrada = Entrada.objects.create(
            proyecto=proyecto,
            guia=guia,
            requerimiento=guia.requerimiento,
            numero_guia=guia.numero,
            # No pasamos `serie` (max_length=10) porque guia.numero suele venir tipo
            # "GR-2026-002" y no cabe. Dejamos el default '001'.
            fecha=date.today(),
            proveedor=guia.conductor or (guia.transportista.razon_social if guia.transportista else ''),
            descripcion=guia.get_motivo_display(),
        )
        log(request, 'CREAR', 'Almacén',
            f'Entrada iniciada desde Guía {guia.numero} en {proyecto.codigo}')

    # Buscar DetalleEntrada existente (por insumo si hay FK, sino por descripción)
    det_qs = entrada.detalles.all()
    if insumo:
        det = det_qs.filter(insumo=insumo).first()
    else:
        det = det_qs.filter(insumo__isnull=True, descripcion__iexact=desc).first()

    if det:
        det.cantidad = cant
        det.observaciones = obs
        det.unidad = unidad or det.unidad
        det.descripcion = desc or det.descripcion
        det.save(update_fields=['cantidad', 'observaciones', 'unidad', 'descripcion'])
        accion = 'actualizado'
    else:
        det = DetalleEntrada.objects.create(
            entrada=entrada,
            insumo=insumo,
            descripcion=desc,
            unidad=unidad,
            cantidad=cant,
            observaciones=obs,
        )
        _sync_insumo_snapshot(det)
        accion = 'creado'

    return JsonResponse({
        'ok': True,
        'entrada_pk': entrada.pk,
        'detalle_pk': det.pk,
        'accion': accion,
    })


@requiere('puede_gestionar_entradas')
@proyecto_visible
def entrada_crear(request, proyecto_id):
    from apps.logistica.models import GuiaRemision
    proyecto = get_object_or_404(Proyecto, pk=proyecto_id)

    # Detectar modo guía (viene desde Almacén → Guías → Registrar guía)
    guia_pk = (request.GET.get('guia') or request.POST.get('guia_pk') or '').strip()
    guia = None
    if guia_pk:
        try:
            guia = (GuiaRemision.objects
                    .select_related('transportista', 'requerimiento')
                    .prefetch_related('detalles')
                    .get(pk=int(guia_pk), proyecto=proyecto))
        except (ValueError, GuiaRemision.DoesNotExist):
            guia = None

    if request.method == 'POST':
        form = EntradaForm(request.POST, proyecto=proyecto)
        if guia:
            # Modo guía: los ítems se guardaron vía AJAX en entrada_aplicar_item.
            # Guardar acá es idempotente — solo redirige a la Entrada creada.
            entrada = Entrada.objects.filter(guia=guia).first()
            if entrada:
                messages.success(request, f'Entrada de Guía {guia.numero} guardada.')
                return redirect('almacen:entrada_detalle', pk=entrada.pk)
            else:
                messages.warning(request, 'No aplicaste ningún ítem. Marcá al menos uno como "Aplicar" antes de guardar.')
                return redirect('almacen:entrada_crear', proyecto_id=proyecto.pk)
        else:
            # Modo manual clásico: usa el formset
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
        # GET
        initial = {}
        items_recibir = []
        if guia:
            from datetime import date
            initial = {
                'numero_guia': guia.numero,
                'serie':       guia.numero,
                'fecha':       date.today(),   # fecha de recepción = hoy (no la de traslado)
                'proveedor':   guia.conductor or (guia.transportista.razon_social if guia.transportista else ''),
                'descripcion': guia.get_motivo_display(),
                'requerimiento': guia.requerimiento_id,
            }
            # Preparar items con stock actual (entradas - salidas) buscando insumo por descripción
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
            for d in guia.detalles.all():
                # Buscar el InsumoPresupuesto por descripción (iexact)
                ins = None
                try:
                    ins = proyecto.presupuesto.insumos.filter(descripcion__iexact=d.descripcion).first()
                except Exception:
                    pass
                if ins:
                    stock_actual = (entradas_agg.get(ins.pk, Decimal('0'))
                                    - salidas_agg.get(ins.pk, Decimal('0')))
                else:
                    stock_actual = None  # None → mostrar '—' en el template
                items_recibir.append({
                    'descripcion':   d.descripcion,
                    'unidad':        d.unidad,
                    'cantidad_guia': d.cantidad,
                    'insumo_pk':     ins.pk if ins else '',
                    'stock_actual':  stock_actual,
                })

        form = EntradaForm(proyecto=proyecto, initial=initial)
        formset = DetalleEntradaFormSet(prefix='detalles')

    ctx = {
        'form': form, 'formset': formset, 'proyecto': proyecto,
        'titulo': 'Nueva Entrada',
    }
    if guia:
        ctx.update({
            'guia': guia,
            'modo_guia': True,
            'items_recibir': items_recibir if request.method == 'GET' else [],
        })
    return render(request, 'almacen/entrada_form.html', ctx)


@requiere('puede_gestionar_entradas')
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


@requiere('puede_gestionar_entradas')
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


@requiere('puede_gestionar_entradas')
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


@requiere('puede_gestionar_entradas')
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

@requiere('puede_gestionar_salidas')
@proyecto_visible
def salida_lista(request, proyecto_id):
    proyecto = get_object_or_404(Proyecto, pk=proyecto_id)
    # 1 fila = 1 material atendido. Cada Atención es una Salida con 1 detalle.
    detalles = (
        DetalleSalida.objects
        .filter(salida__proyecto=proyecto)
        .select_related('salida', 'insumo', 'guia')
        .order_by('-salida__fecha', '-salida__created_at', '-pk')
    )
    return render(request, 'almacen/salida_lista.html', {
        'proyecto': proyecto,
        'detalles': detalles,
    })


@requiere('puede_gestionar_salidas')
@proyecto_visible
def api_insumos_buscar(request, proyecto_id):
    """Autocomplete de insumos del proyecto para el modal de Atención.
    Marca cada insumo con `seleccionable` (True si stock_almacen > 0)."""
    proyecto = get_object_or_404(Proyecto, pk=proyecto_id)
    q = (request.GET.get('q') or '').strip()
    qs = InsumoPresupuesto.objects.filter(presupuesto__proyecto=proyecto)
    if q:
        qs = qs.filter(Q(codigo__icontains=q) | Q(descripcion__icontains=q))
    qs = qs.order_by('codigo', 'descripcion')[:50]
    data = [{
        'id':            i.pk,
        'codigo':        i.codigo,
        'descripcion':   i.descripcion,
        'unidad':        i.unidad,
        'stock_almacen': float(i.stock_almacen or 0),
        'seleccionable': (i.stock_almacen or 0) > 0,
    } for i in qs]
    return JsonResponse({'ok': True, 'items': data})


@requiere('puede_gestionar_salidas')
@proyecto_visible
def api_insumo_guias(request, proyecto_id):
    """Devuelve las guías del proyecto asociadas a requerimientos que incluyen ese insumo.
    (DetalleGuia no tiene FK a insumo — la relación viaja por el Requerimiento)."""
    from apps.logistica.models import GuiaRemision
    from apps.requerimientos.models import DetalleRequerimiento
    proyecto = get_object_or_404(Proyecto, pk=proyecto_id)
    insumo_id = request.GET.get('insumo')
    if not insumo_id:
        return JsonResponse({'ok': False, 'error': 'Falta insumo'}, status=400)
    req_ids = (
        DetalleRequerimiento.objects
        .filter(requerimiento__proyecto=proyecto, insumo_id=insumo_id)
        .values_list('requerimiento_id', flat=True)
        .distinct()
    )
    guias = (
        GuiaRemision.objects
        .filter(proyecto=proyecto, requerimiento_id__in=req_ids)
        .order_by('-fecha_emision', '-pk')
    )
    data = [{
        'id':     g.pk,
        'numero': g.numero,
        'fecha':  g.fecha_emision.strftime('%d/%m/%Y') if g.fecha_emision else '',
    } for g in guias]
    return JsonResponse({'ok': True, 'items': data})


@requiere('puede_gestionar_salidas')
@proyecto_visible
def atencion_crear(request, proyecto_id):
    """Endpoint AJAX: crea una Salida con UN detalle (una Atención = un material)."""
    import json
    if request.method != 'POST':
        return JsonResponse({'ok': False, 'error': 'Solo POST'}, status=405)
    proyecto = get_object_or_404(Proyecto, pk=proyecto_id)
    try:
        body = json.loads(request.body or b'{}')
    except (ValueError, json.JSONDecodeError):
        return JsonResponse({'ok': False, 'error': 'JSON inválido'}, status=400)

    # Validación
    insumo_id = body.get('insumo_id')
    if not insumo_id:
        return JsonResponse({'ok': False, 'error': 'Debe elegir un insumo'}, status=400)
    try:
        insumo = InsumoPresupuesto.objects.get(pk=insumo_id, presupuesto__proyecto=proyecto)
    except InsumoPresupuesto.DoesNotExist:
        return JsonResponse({'ok': False, 'error': 'Insumo no pertenece al proyecto'}, status=400)

    try:
        cantidad = Decimal(str(body.get('cantidad') or '0'))
        parcial  = Decimal(str(body.get('parcial')  or '0'))
    except Exception:
        return JsonResponse({'ok': False, 'error': 'Cantidad/parcial inválidos'}, status=400)

    if cantidad <= 0:
        return JsonResponse({'ok': False, 'error': 'Cantidad debe ser > 0'}, status=400)
    if cantidad > (insumo.stock_almacen or 0):
        return JsonResponse({
            'ok': False,
            'error': f'Cantidad ({cantidad}) supera el stock disponible ({insumo.stock_almacen}).',
        }, status=400)

    precio_unitario = (parcial / cantidad) if cantidad else Decimal('0')

    guia = None
    guia_id = body.get('guia_id')
    if guia_id:
        from apps.logistica.models import GuiaRemision
        try:
            guia = GuiaRemision.objects.get(pk=guia_id, proyecto=proyecto)
        except GuiaRemision.DoesNotExist:
            pass

    # Correlativo SAL-XXX interno (trazabilidad)
    from django.db.models import Max
    ult = proyecto.salidas.aggregate(m=Max('numero'))['m']
    try:
        siguiente = int((ult or '0')) + 1
    except (ValueError, TypeError):
        siguiente = (proyecto.salidas.count() or 0) + 1

    import datetime as _dt
    fecha_str = body.get('fecha') or _dt.date.today().isoformat()
    try:
        fecha = _dt.date.fromisoformat(fecha_str)
    except ValueError:
        fecha = _dt.date.today()

    salida = Salida.objects.create(
        proyecto=proyecto,
        numero=str(siguiente).zfill(4),
        fecha=fecha,
        proveedor=(body.get('proveedor') or '').strip(),
        factura=(body.get('factura') or '').strip(),
        observaciones=(body.get('observaciones') or '').strip(),
    )

    detalle = DetalleSalida.objects.create(
        salida=salida,
        insumo=insumo,
        guia=guia,
        descripcion=insumo.descripcion,
        unidad=insumo.unidad,
        cantidad=cantidad,
        precio_unitario=precio_unitario.quantize(Decimal('0.0001')),
        observaciones=(body.get('observaciones_linea') or '').strip(),
    )
    # El signal post_save de DetalleSalida ya descuenta stock_almacen del insumo.

    log(request, 'CREAR', 'Almacén',
        f'Atención SAL-{salida.numero}: {cantidad} {insumo.unidad} de {insumo.codigo} - {insumo.descripcion[:40]}')

    return JsonResponse({
        'ok': True,
        'detalle_id': detalle.pk,
        'salida_numero': salida.numero,
    })


@requiere('puede_gestionar_salidas')
def salida_detalle(request, pk):
    salida = get_object_or_404(Salida, pk=pk)
    return render(request, 'almacen/salida_detalle.html', {'salida': salida, 'proyecto': salida.proyecto})


@requiere('puede_gestionar_salidas')
@proyecto_visible
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


@requiere('puede_gestionar_salidas')
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


@requiere('puede_gestionar_salidas')
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

@requiere('puede_gestionar_cotizaciones', 'puede_gestionar_cotizaciones_log')
@proyecto_visible
def cot_lista(request, proyecto_id):
    from apps.almacen.models import ESTADOS_COT
    proyecto = get_object_or_404(Proyecto, pk=proyecto_id)
    estado_sel = request.GET.get('estado', '')
    qs = (proyecto.cotizaciones
          .select_related('requerimiento_origen')
          .prefetch_related('detalles__insumo')
          .order_by('-fecha', '-pk'))
    if estado_sel:
        qs = qs.filter(estado=estado_sel)
    return render(request, 'almacen/cot_lista.html', {
        'proyecto':     proyecto,
        'cotizaciones': qs,
        'estados':      ESTADOS_COT,
        'estado_sel':   estado_sel,
    })


@requiere('puede_gestionar_cotizaciones', 'puede_gestionar_cotizaciones_log')
def cot_detalle(request, pk):
    cot = get_object_or_404(Cotizacion, pk=pk)
    return render(request, 'almacen/cot_detalle.html', {'cot': cot, 'proyecto': cot.proyecto})


@requiere('puede_gestionar_cotizaciones', 'puede_gestionar_cotizaciones_log')
def cot_imprimir(request, pk):
    from decimal import InvalidOperation
    from apps.configuracion.models import ConfigEmpresa
    cot = get_object_or_404(
        Cotizacion.objects.select_related('proyecto', 'requerimiento_origen')
                          .prefetch_related('detalles__insumo'),
        pk=pk,
    )

    if request.method == 'POST':
        for det in cot.detalles.all():
            raw = request.POST.get(f'cantidad_{det.pk}', '').strip()
            if not raw:
                continue
            try:
                nueva = Decimal(raw)
                if nueva >= 0 and nueva != det.cantidad:
                    det.cantidad = nueva
                    det.save(update_fields=['cantidad'])
            except (InvalidOperation, ValueError):
                continue
        log(request, 'EDITAR', 'Almacén',
            f'Cantidades de COT-{cot.numero} actualizadas por {request.user.get_full_name() or request.user.username}')
        messages.success(request, f'Cantidades de COT-{cot.numero} guardadas.')
        return redirect('almacen:cot_imprimir', pk=cot.pk)

    return render(request, 'almacen/cot_imprimir.html', {
        'cot':      cot,
        'proyecto': cot.proyecto,
        'empresa':  ConfigEmpresa.get(),
    })


@requiere('puede_gestionar_cotizaciones', 'puede_gestionar_cotizaciones_log')
@proyecto_visible
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


@requiere('puede_gestionar_cotizaciones', 'puede_gestionar_cotizaciones_log')
@proyecto_visible
def cot_desde_req(request, proyecto_id, req_pk):
    """Genera una cotización pre-cargada con los ítems (cantidad_aprobada) de un requerimiento.
    Numeración: espeja el número del REQ. Si ya existen cotizaciones para el mismo REQ,
    agrega sufijo -2, -3, ...  Ej: REQ-025 → COT-025, luego COT-025-2, COT-025-3.
    """
    from django.utils.timezone import now
    from apps.requerimientos.models import Requerimiento

    if request.method != 'POST':
        return redirect('almacen:cot_lista', proyecto_id=proyecto_id)

    proyecto = get_object_or_404(Proyecto, pk=proyecto_id)
    req = get_object_or_404(Requerimiento, pk=req_pk, proyecto=proyecto)

    base = str(req.numero)
    cots_previas = req.cotizaciones_origen.count()
    numero = base if cots_previas == 0 else f'{base}-{cots_previas + 1}'
    # guardarnos de colisiones (por si el usuario borró alguna en el medio)
    while Cotizacion.objects.filter(proyecto=proyecto, numero=numero).exists():
        cots_previas += 1
        numero = f'{base}-{cots_previas + 1}'

    cot = Cotizacion.objects.create(
        proyecto=proyecto,
        requerimiento_origen=req,
        numero=numero,
        fecha=now().date(),
        proveedor='',
        estado='PENDIENTE',
        observaciones=f'Solicitud de cotización generada desde REQ-{req.numero}',
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

    # Mantener req.cotizacion_sistema apuntando a la última creada (compat con flujos previos)
    req.cotizacion_sistema = cot
    req.save(update_fields=['cotizacion_sistema'])

    log(request, 'CREAR', 'Almacén',
        f'Cotización COT-{cot.numero} generada desde REQ-{req.numero} en {proyecto.codigo}')
    messages.success(request, f'Solicitud de cotización COT-{cot.numero} generada.')
    return redirect('almacen:cot_imprimir', pk=cot.pk)


@requiere('puede_gestionar_cotizaciones', 'puede_gestionar_cotizaciones_log')
@proyecto_visible
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


@requiere('puede_gestionar_cotizaciones', 'puede_gestionar_cotizaciones_log')
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


@requiere('puede_gestionar_cotizaciones', 'puede_gestionar_cotizaciones_log')
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

@requiere('puede_gestionar_oc')
@proyecto_visible
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


@requiere('puede_gestionar_oc')
def oc_detalle(request, pk):
    oc = get_object_or_404(OrdenCompra, pk=pk)
    return render(request, 'almacen/oc_detalle.html', {'oc': oc, 'proyecto': oc.proyecto})


@requiere('puede_gestionar_oc')
@proyecto_visible
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


@requiere('puede_gestionar_oc')
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


@requiere('puede_gestionar_oc')
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

@requiere('puede_gestionar_cotizaciones', 'puede_gestionar_cotizaciones_log')
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


@requiere('puede_ver_almacen', 'puede_gestionar_entradas', 'puede_gestionar_salidas', 'puede_crear_requerimientos', 'puede_aprobar_requerimientos')
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


@requiere('puede_ver_almacen', 'puede_gestionar_entradas', 'puede_gestionar_salidas', 'puede_gestionar_cotizaciones', 'puede_gestionar_cotizaciones_log', 'puede_gestionar_oc', 'puede_crear_requerimientos', 'puede_aprobar_requerimientos')
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
