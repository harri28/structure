from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('almacen', '0015_detalleentrada_detalle_guia'),
    ]

    operations = [
        migrations.AddField(
            model_name='salida',
            name='hora',
            field=models.TimeField(blank=True, null=True),
        ),
    ]
