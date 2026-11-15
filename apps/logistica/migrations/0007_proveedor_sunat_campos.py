from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('logistica', '0006_proveedor'),
    ]

    operations = [
        migrations.AddField(
            model_name='proveedor',
            name='estado_sunat',
            field=models.CharField(blank=True, max_length=40, verbose_name='Estado SUNAT'),
        ),
        migrations.AddField(
            model_name='proveedor',
            name='condicion_sunat',
            field=models.CharField(blank=True, max_length=40, verbose_name='Condición SUNAT'),
        ),
        migrations.AddField(
            model_name='proveedor',
            name='tipo_contribuyente',
            field=models.CharField(blank=True, max_length=100, verbose_name='Tipo de Contribuyente'),
        ),
        migrations.AddField(
            model_name='proveedor',
            name='fecha_inicio_actividades',
            field=models.CharField(blank=True, max_length=20, verbose_name='Fecha Inicio Actividades'),
        ),
    ]
