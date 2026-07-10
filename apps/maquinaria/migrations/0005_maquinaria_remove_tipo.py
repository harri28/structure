from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('maquinaria', '0004_maquinaria_campos_completos'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='maquinaria',
            name='tipo',
        ),
    ]
