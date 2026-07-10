from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('maquinaria', '0003_registromaquinaria_hora_entrada_hora_salida_insumo'),
    ]

    operations = [
        migrations.AddField(
            model_name='maquinaria',
            name='tipo_equipo',
            field=models.CharField(blank=True, choices=[
                ('CAMIONETA', 'Camioneta'), ('TRACTOR', 'Tractor'),
                ('RETROEXCAVADORA', 'Retroexcavadora'), ('EXCAVADORA', 'Excavadora'),
                ('CARGADOR', 'Cargador Frontal'), ('VOLQUETE', 'Volquete'),
                ('GRUA', 'Grúa'), ('COMPACTADORA', 'Compactadora'),
                ('MOTONIVELADORA', 'Motoniveladora'), ('BUS', 'Bus / Minibús'), ('OTRO', 'Otro'),
            ], max_length=20, verbose_name='Tipo de equipo'),
        ),
        migrations.AddField(
            model_name='maquinaria',
            name='marca',
            field=models.CharField(blank=True, max_length=100, verbose_name='Marca'),
        ),
        migrations.AddField(
            model_name='maquinaria',
            name='modelo',
            field=models.CharField(blank=True, max_length=100, verbose_name='Modelo'),
        ),
        migrations.AddField(
            model_name='maquinaria',
            name='costo',
            field=models.DecimalField(decimal_places=2, default=0, max_digits=14, verbose_name='Costo'),
        ),
        migrations.AddField(
            model_name='maquinaria',
            name='modalidad_costo',
            field=models.CharField(blank=True, choices=[
                ('MENSUAL', 'Mensual'), ('SEMANAL', 'Semanal'), ('QUINCENAL', 'Quincenal'),
            ], max_length=15, verbose_name='Modalidad'),
        ),
        migrations.AddField(
            model_name='maquinaria',
            name='propietario',
            field=models.CharField(blank=True, max_length=200, verbose_name='Propietario'),
        ),
        migrations.AddField(
            model_name='maquinaria',
            name='operador',
            field=models.CharField(blank=True, max_length=200, verbose_name='Operador'),
        ),
        migrations.AddField(
            model_name='maquinaria',
            name='fecha_llegada',
            field=models.DateField(blank=True, null=True, verbose_name='Fecha de llegada'),
        ),
        migrations.AddField(
            model_name='maquinaria',
            name='fecha_reinicio',
            field=models.DateField(blank=True, null=True, verbose_name='Fecha de reinicio de trabajo'),
        ),
        migrations.AddField(
            model_name='maquinaria',
            name='fecha_salida_obra',
            field=models.DateField(blank=True, null=True, verbose_name='Fecha de salida de obra'),
        ),
        migrations.AlterModelOptions(
            name='maquinaria',
            options={'ordering': ['codigo'], 'verbose_name': 'Maquinaria', 'verbose_name_plural': 'Maquinaria'},
        ),
    ]
