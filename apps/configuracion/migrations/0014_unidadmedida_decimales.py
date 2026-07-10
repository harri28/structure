from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('configuracion', '0013_rol_puede_ver_dashboard'),
    ]

    operations = [
        migrations.AddField(
            model_name='unidadmedida',
            name='decimales',
            field=models.PositiveSmallIntegerField(
                default=4,
                help_text='Cifras decimales al mostrar cantidades de esta unidad (0 = entero, 4 = predeterminado).',
                verbose_name='Decimales',
            ),
        ),
    ]
