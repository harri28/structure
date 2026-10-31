import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('almacen', '0016_salida_hora'),
        ('maquinaria', '0010_trabajador_documentotrabajador'),
    ]

    operations = [
        migrations.AddField(
            model_name='salida',
            name='trabajador',
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='+',
                to='maquinaria.trabajador',
            ),
        ),
    ]
