from decimal import Decimal
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.http import JsonResponse
from django.db.models import Q, Sum
from apps.proyectos.models import Proyecto
from apps.catalogo.models import Producto
from .models import (
    Requerimiento, DetalleRequerimiento,
    Entrada, DetalleEntrada,
    Salida, DetalleSalida,
    Cotizacion, DetalleCotizacion,
    OrdenCompra, DetalleOrdenCompra,
    ESTADOS_OC,
)
from .forms import (
    RequerimientoForm, DetalleRequerimientoFormSet,
    EntradaForm, DetalleEntradaFormSet,
    SalidaForm, DetalleSalidaFormSet,
    CotizacionForm, DetalleCotizacionFormSet,
    OrdenCompraForm, DetalleOrdenCompraFormSet,
)


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
    categoria = request.GET.get('categoria', '')

    entradas_agg = {
        r['producto_id']: r['total']
        for r in DetalleEntrada.objects
        .filter(entrada__proyecto=proyecto)
        .values('producto_id')
        .annotate(total=Sum('cantidad'))
    }
    salidas_agg = {
        r['producto_id']: r['total']
        for r in DetalleSalida.objects
        .filter(salida__proyecto=proyecto)
        .values('producto_id')
        .annotate(total=Sum('cantidad'))
    }

    producto_ids = set(entradas_agg) | set(salidas_agg)
    qs = Producto.objects.filter(pk__in=producto_ids)
    if categoria:
        qs = qs.filter(categoria=categoria)

    items = []
    for p in qs:
        entrada = entradas_agg.get(p.pk, Decimal('0'))
        salida  = salidas_agg.get(p.pk, Decimal('0'))
        items.append({
            'producto': p,
            'total_entrada': entrada,
            'total_salida':  salida,
            'saldo': entrada - salida,
        })
    items.sort(key=lambda x: x['producto'].codigo)

    from apps.catalogo.models import CATEGORIAS
    return render(request, 'almacen/stock.html', {
        'proyecto': proyecto,
        'items': items,
        'categorias': CATEGORIAS,
        'categoria_sel': categoria,
    })


def kardex(request, proyecto_id, producto_id):
    proyecto = get_object_or_404(Proyecto, pk=proyecto_id)
    producto = get_object_or_404(Producto, pk=producto_id)

    movimientos = []

    for d in (DetalleEntrada.objects
              .filter(entrada__proyecto=proyecto, producto=producto)
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
              .filter(salida__proyecto=proyecto, producto=producto)
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
        'producto': producto,
        'movimientos': movimientos,
        'saldo_final': saldo,
    })


# ── Requerimientos ──────────────────────────────────────────────────────────

def req_lista(request, proyecto_id):
    proyecto = get_object_or_404(Proyecto, pk=proyecto_id)
    qs = proyecto.requerimientos.all()
    estado = request.GET.get('estado', '')
    if estado:
        qs = qs.filter(estado=estado)
    return render(request, 'almacen/req_lista.html', {
        'proyecto': proyecto, 'requerimientos': qs, 'estado_sel': estado,
    })


def req_detalle(request, pk):
    req = get_object_or_404(Requerimiento, pk=pk)
    return render(request, 'almacen/req_detalle.html', {'req': req, 'proyecto': req.proyecto})


def req_crear(request, proyecto_id):
    proyecto = get_object_or_404(Proyecto, pk=proyecto_id)
    if request.method == 'POST':
        form = RequerimientoForm(request.POST)
        formset = DetalleRequerimientoFormSet(request.POST, prefix='detalles')
        if form.is_valid() and formset.is_valid():
            req = form.save(commit=False)
            req.proyecto = proyecto
            req.save()
            for f in formset:
                if f.cleaned_data and not f.cleaned_data.get('DELETE'):
                    d = f.save(commit=False)
                    d.requerimiento = req
                    d.save()
            messages.success(request, 'Requerimiento registrado.')
            return redirect('almacen:req_detalle', pk=req.pk)
    else:
        form = RequerimientoForm()
        formset = DetalleRequerimientoFormSet(prefix='detalles')
    return render(request, 'almacen/req_form.html', {
        'form': form, 'formset': formset, 'proyecto': proyecto, 'titulo': 'Nuevo Requerimiento',
    })


def req_editar(request, pk):
    req = get_object_or_404(Requerimiento, pk=pk)
    proyecto = req.proyecto
    if request.method == 'POST':
        form = RequerimientoForm(request.POST, instance=req)
        formset = DetalleRequerimientoFormSet(request.POST, instance=req, prefix='detalles')
        if form.is_valid() and formset.is_valid():
            form.save()
            formset.save()
            messages.success(request, 'Requerimiento actualizado.')
            return redirect('almacen:req_detalle', pk=req.pk)
    else:
        form = RequerimientoForm(instance=req)
        formset = DetalleRequerimientoFormSet(instance=req, prefix='detalles')
    return render(request, 'almacen/req_form.html', {
        'form': form, 'formset': formset, 'proyecto': proyecto, 'titulo': 'Editar Requerimiento',
    })


def req_eliminar(request, pk):
    req = get_object_or_404(Requerimiento, pk=pk)
    proyecto = req.proyecto
    if request.method == 'POST':
        req.delete()
        messages.success(request, 'Requerimiento eliminado.')
        return redirect('almacen:req_lista', proyecto_id=proyecto.pk)
    return render(request, 'almacen/confirmar_eliminar.html', {'obj': req, 'proyecto': proyecto})


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
                    d.save()
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
            formset.save()
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
        entrada.delete()
        messages.success(request, 'Entrada eliminada.')
        return redirect('almacen:entrada_lista', proyecto_id=proyecto.pk)
    return render(request, 'almacen/confirmar_eliminar.html', {'obj': entrada, 'proyecto': proyecto})


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
    proyecto = get_object_or_404(Proyecto, pk=proyecto_id)
    if request.method == 'POST':
        form = SalidaForm(request.POST)
        formset = DetalleSalidaFormSet(request.POST, prefix='detalles')
        if form.is_valid() and formset.is_valid():
            salida = form.save(commit=False)
            salida.proyecto = proyecto
            salida.save()
            for f in formset:
                if f.cleaned_data and not f.cleaned_data.get('DELETE'):
                    d = f.save(commit=False)
                    d.salida = salida
                    d.save()
            messages.success(request, 'Salida registrada.')
            return redirect('almacen:salida_detalle', pk=salida.pk)
    else:
        form = SalidaForm()
        formset = DetalleSalidaFormSet(prefix='detalles')
    return render(request, 'almacen/salida_form.html', {
        'form': form, 'formset': formset, 'proyecto': proyecto, 'titulo': 'Nueva Salida',
    })


def salida_editar(request, pk):
    salida = get_object_or_404(Salida, pk=pk)
    proyecto = salida.proyecto
    if request.method == 'POST':
        form = SalidaForm(request.POST, instance=salida)
        formset = DetalleSalidaFormSet(request.POST, instance=salida, prefix='detalles')
        if form.is_valid() and formset.is_valid():
            form.save()
            formset.save()
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
        salida.delete()
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
                    d.save()
            messages.success(request, 'Cotización registrada.')
            return redirect('almacen:cot_detalle', pk=cot.pk)
    else:
        form = CotizacionForm()
        formset = DetalleCotizacionFormSet(prefix='detalles')
    return render(request, 'almacen/cot_form.html', {
        'form': form, 'formset': formset, 'proyecto': proyecto, 'titulo': 'Nueva Cotización',
    })


def cot_editar(request, pk):
    cot = get_object_or_404(Cotizacion, pk=pk)
    proyecto = cot.proyecto
    if request.method == 'POST':
        form = CotizacionForm(request.POST, instance=cot)
        formset = DetalleCotizacionFormSet(request.POST, instance=cot, prefix='detalles')
        if form.is_valid() and formset.is_valid():
            form.save()
            formset.save()
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
        cot.delete()
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
                    d.save()
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
            formset.save()
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
        oc.delete()
        messages.success(request, 'Orden eliminada.')
        return redirect('almacen:oc_lista', proyecto_id=proyecto.pk)
    return render(request, 'almacen/confirmar_eliminar.html', {'obj': oc, 'proyecto': proyecto})


# ── API ───────────────────────────────────────────────────────────────────────

def api_productos(request):
    q = request.GET.get('q', '')
    productos = Producto.objects.filter(activo=True)
    if q:
        productos = productos.filter(Q(codigo__icontains=q) | Q(descripcion__icontains=q))
    data = [{'id': p.pk, 'codigo': p.codigo, 'descripcion': p.descripcion, 'unidad': p.unidad} for p in productos[:50]]
    return JsonResponse(data, safe=False)
