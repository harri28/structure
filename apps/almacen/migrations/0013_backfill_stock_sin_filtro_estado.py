# Re-backfill de stock_almacen sin filtro de estado en Entrada.
# La migración 0012 filtraba entrada__estado='ACEPTADO'; para alinear con la
# vista Stock existente (_stock_query) contamos TODAS las entradas.

from decimal import Decimal
from django.db import migrations
from django.db.models import Sum


def backfill_stock(apps, schema_editor):
    InsumoPresupuesto = apps.get_model('presupuesto', 'InsumoPresupuesto')
    DetalleEntrada = apps.get_model('almacen', 'DetalleEntrada')
    DetalleSalida = apps.get_model('almacen', 'DetalleSalida')

    for insumo in InsumoPresupuesto.objects.all():
        entradas = (
            DetalleEntrada.objects
            .filter(insumo_id=insumo.pk)
            .aggregate(t=Sum('cantidad'))['t'] or Decimal('0')
        )
        salidas = (
            DetalleSalida.objects
            .filter(insumo_id=insumo.pk)
            .aggregate(t=Sum('cantidad'))['t'] or Decimal('0')
        )
        nuevo = entradas - salidas
        if insumo.stock_almacen != nuevo:
            insumo.stock_almacen = nuevo
            insumo.save(update_fields=['stock_almacen'])


def reverso(apps, schema_editor):
    # El reverso deja stock_almacen en 0; 0012 lo hará luego si se retrocede.
    InsumoPresupuesto = apps.get_model('presupuesto', 'InsumoPresupuesto')
    InsumoPresupuesto.objects.all().update(stock_almacen=0)


class Migration(migrations.Migration):

    dependencies = [
        ('almacen', '0012_backfill_stock_almacen'),
    ]

    operations = [
        migrations.RunPython(backfill_stock, reverso),
    ]
