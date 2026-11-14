"""
Data migration — subir precisión de `InsumoPresupuesto.total` a 4 decimales.

Contexto: hasta ahora `total` se almacenaba como `DecimalField(15, 2)`. Al
sumar miles de filas pre-redondeadas a 2 decimales, el total consolidado
podía desviarse en centavos — tolerable con presupuestos chicos, molesto
con presupuestos de 500M donde pueden aparecer diferencias de soles contra
Excel/fuente.

Esta migración:
  1. Alter: `total` pasa de (15,2) a (18,4). 14 dígitos enteros — holgura
     hasta 99 trillones de soles, imposible rebalsar.
  2. Recalcula `total = cantidad_total × costo_unitario` con 4 decimales
     para todas las filas existentes. Usa cantidad_total (cupo original S10)
     como fuente de verdad; es inmutable, igual que el presupuesto base.
  3. Reverse: baja el campo a (15,2). El recálculo no se revierte (los
     valores más precisos no se pierden si solo se guardan truncados).

Idempotente: si se corre dos veces, el recálculo produce el mismo resultado.
"""
from decimal import Decimal, ROUND_HALF_UP
from django.db import migrations, models


Q4 = Decimal('0.0001')


def recalcular_totales(apps, schema_editor):
    Insumo = apps.get_model('presupuesto', 'InsumoPresupuesto')
    actualizados = 0
    for ins in Insumo.objects.all().iterator(chunk_size=500):
        cant = ins.cantidad_total or Decimal('0')
        prec = ins.costo_unitario or Decimal('0')
        nuevo_total = (Decimal(cant) * Decimal(prec)).quantize(Q4, rounding=ROUND_HALF_UP)
        if nuevo_total != (ins.total or Decimal('0')):
            ins.total = nuevo_total
            ins.save(update_fields=['total'])
            actualizados += 1
    # Nota: `actualizados` no se registra; si querés verlo, correr
    # apps.presupuesto desde el shell antes del migrate.


class Migration(migrations.Migration):

    dependencies = [
        ('presupuesto', '0012_insumopresupuesto_stock_almacen'),
    ]

    operations = [
        migrations.AlterField(
            model_name='insumopresupuesto',
            name='total',
            field=models.DecimalField(max_digits=18, decimal_places=4, default=0),
        ),
        migrations.RunPython(recalcular_totales, migrations.RunPython.noop),
    ]
