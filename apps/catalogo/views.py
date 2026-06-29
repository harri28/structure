from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.http import JsonResponse
from django.db.models import Q
from .models import Producto, CATEGORIAS
from .forms import ProductoForm
from .importador import importar_catalogo_excel


def lista(request):
    categoria = request.GET.get('categoria', '')
    buscar = request.GET.get('q', '')
    productos = Producto.objects.filter(activo=True)
    if categoria:
        productos = productos.filter(categoria=categoria)
    if buscar:
        productos = productos.filter(Q(codigo__icontains=buscar) | Q(descripcion__icontains=buscar))
    return render(request, 'catalogo/lista.html', {
        'productos': productos,
        'categorias': CATEGORIAS,
        'categoria_sel': categoria,
        'buscar': buscar,
    })


def importar(request):
    if request.method == 'POST' and request.FILES.get('archivo'):
        archivo = request.FILES['archivo']
        try:
            creados, actualizados = importar_catalogo_excel(archivo)
            messages.success(request, f'Importación completada: {creados} nuevos, {actualizados} actualizados.')
        except Exception as e:
            messages.error(request, f'Error al importar: {str(e)}')
        return redirect('catalogo:lista')
    return render(request, 'catalogo/importar.html')


def editar(request, pk):
    producto = get_object_or_404(Producto, pk=pk)
    if request.method == 'POST':
        form = ProductoForm(request.POST, instance=producto)
        if form.is_valid():
            form.save()
            messages.success(request, 'Producto actualizado.')
            return redirect('catalogo:lista')
    else:
        form = ProductoForm(instance=producto)
    return render(request, 'catalogo/form.html', {'form': form, 'producto': producto})


def eliminar(request, pk):
    producto = get_object_or_404(Producto, pk=pk)
    if request.method == 'POST':
        producto.activo = False
        producto.save()
        messages.success(request, 'Producto desactivado.')
        return redirect('catalogo:lista')
    return render(request, 'catalogo/confirmar_eliminar.html', {'producto': producto})


def api_buscar(request):
    q = request.GET.get('q', '')
    categoria = request.GET.get('categoria', '')
    productos = Producto.objects.filter(activo=True)
    if q:
        productos = productos.filter(Q(codigo__icontains=q) | Q(descripcion__icontains=q))
    if categoria:
        productos = productos.filter(categoria=categoria)
    data = [{'id': p.pk, 'codigo': p.codigo, 'descripcion': p.descripcion, 'unidad': p.unidad} for p in productos[:50]]
    return JsonResponse(data, safe=False)
