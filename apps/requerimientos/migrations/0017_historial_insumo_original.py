from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('presupuesto', '0013_insumo_total_4_decimales'),
        ('requerimientos', '0016_historial_accion_sustituir'),
    ]

    operations = [
        migrations.AddField(
            model_name='historialrevisionreq',
            name='insumo_original',
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='historial_como_original',
                to='presupuesto.insumopresupuesto',
                verbose_name='Insumo original (para sustituciones)',
            ),
        ),
    ]
