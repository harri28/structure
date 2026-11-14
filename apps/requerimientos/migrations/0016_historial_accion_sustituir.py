from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('requerimientos', '0015_estado_cotizado'),
    ]

    operations = [
        migrations.AlterField(
            model_name='historialrevisionreq',
            name='accion',
            field=models.CharField(
                choices=[
                    ('ELIMINAR', 'Ítem eliminado'),
                    ('AGREGAR', 'Ítem agregado'),
                    ('SUSTITUIR', 'Insumo sustituido'),
                    ('ANULAR', 'Requerimiento anulado'),
                    ('RECUPERAR', 'Requerimiento recuperado'),
                ],
                max_length=10,
            ),
        ),
    ]
