from decimal import Decimal
from django.db.models import Sum


def actualizar_stock_almacen(insumo):
    """Recalcula InsumoPresupuesto.stock_almacen = Σ entradas − Σ salidas.
    Sin filtro por estado — alinea con la vista Stock existente (_stock_query)."""
    if not insumo:
        return
    from .models import DetalleEntrada, DetalleSalida

    entradas = (
        DetalleEntrada.objects
        .filter(insumo=insumo)
        .aggregate(t=Sum('cantidad'))['t'] or Decimal('0')
    )
    salidas = (
        DetalleSalida.objects
        .filter(insumo=insumo)
        .aggregate(t=Sum('cantidad'))['t'] or Decimal('0')
    )
    nuevo = entradas - salidas
    if insumo.stock_almacen != nuevo:
        insumo.stock_almacen = nuevo
        insumo.save(update_fields=['stock_almacen'])


def actualizar_stock_todos_insumos(proyecto=None):
    """Backfill: recalcula stock_almacen para todos los insumos.
    Si `proyecto` viene, filtra por ese proyecto."""
    from apps.presupuesto.models import InsumoPresupuesto
    qs = InsumoPresupuesto.objects.all()
    if proyecto:
        qs = qs.filter(presupuesto__proyecto=proyecto)
    n = 0
    for insumo in qs:
        actualizar_stock_almacen(insumo)
        n += 1
    return n
