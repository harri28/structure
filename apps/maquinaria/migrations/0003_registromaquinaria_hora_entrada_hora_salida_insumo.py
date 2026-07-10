from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('maquinaria', '0002_registromaquinaria_codigo_registromaquinaria_costo_and_more'),
        ('presupuesto', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='registromaquinaria',
            name='hora_entrada',
            field=models.TimeField(blank=True, null=True, verbose_name='Hora entrada'),
        ),
        migrations.AddField(
            model_name='registromaquinaria',
            name='hora_salida',
            field=models.TimeField(blank=True, null=True, verbose_name='Hora salida'),
        ),
        migrations.AddField(
            model_name='registromaquinaria',
            name='insumo',
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='registros_maquinaria',
                to='presupuesto.insumopresupuesto',
                verbose_name='Insumo presupuesto',
            ),
        ),
    ]
