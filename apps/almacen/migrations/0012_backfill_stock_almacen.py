# Backfill de InsumoPresupuesto.stock_almacen para todos los proyectos.
# Después de esta migración, el sync automático (signals en apps/almacen/signals.py)
# mantiene el valor actualizado en cada Entrada / Salida.

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
            .filter(insumo_id=insumo.pk, entrada__estado='ACEPTADO')
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
    InsumoPresupuesto = apps.get_model('presupuesto', 'InsumoPresupuesto')
    InsumoPresupuesto.objects.all().update(stock_almacen=0)


class Migration(migrations.Migration):

    dependencies = [
        ('almacen', '0011_detallesalida_guia_detallesalida_observaciones_and_more'),
        ('presupuesto', '0012_insumopresupuesto_stock_almacen'),
    ]

    operations = [
        migrations.RunPython(backfill_stock, reverso),
    ]
