from django.db import migrations, models
from decimal import Decimal, InvalidOperation


def poblar_cantidad_total(apps, schema_editor):
    InsumoPresupuesto = apps.get_model('presupuesto', 'InsumoPresupuesto')
    for ins in InsumoPresupuesto.objects.all():
        try:
            if ins.costo_unitario and ins.costo_unitario != 0 and ins.total:
                ins.cantidad_total = ins.total / ins.costo_unitario
            else:
                ins.cantidad_total = ins.cantidad
        except (InvalidOperation, ZeroDivisionError):
            ins.cantidad_total = ins.cantidad
        ins.save(update_fields=['cantidad_total'])


class Migration(migrations.Migration):

    dependencies = [
        ('presupuesto', '0009_add_insumo_total'),
    ]

    operations = [
        migrations.AddField(
            model_name='insumopresupuesto',
            name='cantidad_total',
            field=models.DecimalField(decimal_places=4, default=0, max_digits=18),
        ),
        migrations.RunPython(poblar_cantidad_total, migrations.RunPython.noop),
    ]
