from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('requerimientos', '0007_detalle_codigo_snapshot'),
    ]

    operations = [
        migrations.AddField(
            model_name='requerimiento',
            name='aprobacion_vista',
            field=models.BooleanField(default=True),
        ),
    ]
