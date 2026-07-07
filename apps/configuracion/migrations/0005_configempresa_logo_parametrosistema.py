from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('configuracion', '0004_rol_puede_gestionar_logistica_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='configempresa',
            name='logo',
            field=models.ImageField(blank=True, upload_to='empresa/', verbose_name='Logo'),
        ),
        migrations.CreateModel(
            name='ParametroSistema',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('gg_pct_default',       models.DecimalField(decimal_places=2, default=10.0, max_digits=5, verbose_name='GG % por defecto')),
                ('utilidad_pct_default', models.DecimalField(decimal_places=2, default=5.0,  max_digits=5, verbose_name='Utilidad % por defecto')),
                ('igv_pct_default',      models.DecimalField(decimal_places=2, default=18.0, max_digits=5, verbose_name='IGV % por defecto')),
                ('dias_vigencia_cot',    models.IntegerField(default=30, verbose_name='Días vigencia cotización')),
                ('updated_at',           models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name': 'Parámetros del Sistema',
            },
        ),
    ]
