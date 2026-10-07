import django.db.models.deletion
import django.utils.timezone
from django.db import migrations, models


def wipe_cuadrillas(apps, schema_editor):
    """Empezar limpio: elimina cuadrillas e integrantes antiguos antes de alterar el esquema."""
    IntegranteCuadrilla = apps.get_model('maquinaria', 'IntegranteCuadrilla')
    Cuadrilla           = apps.get_model('maquinaria', 'Cuadrilla')
    IntegranteCuadrilla.objects.all().delete()
    Cuadrilla.objects.all().delete()


class Migration(migrations.Migration):

    dependencies = [
        ('maquinaria', '0011_trabajador_perfil_completo'),
        ('proyectos',  '0001_initial'),
    ]

    operations = [
        migrations.RunPython(wipe_cuadrillas, reverse_code=migrations.RunPython.noop),

        # IntegranteCuadrilla: deshacer unique_together, quitar tipo_personal + cantidad, agregar trabajador
        migrations.AlterUniqueTogether(
            name='integrantecuadrilla',
            unique_together=set(),
        ),
        migrations.RemoveField(
            model_name='integrantecuadrilla',
            name='tipo_personal',
        ),
        migrations.RemoveField(
            model_name='integrantecuadrilla',
            name='cantidad',
        ),
        migrations.AddField(
            model_name='integrantecuadrilla',
            name='trabajador',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name='membresias',
                to='maquinaria.trabajador',
            ),
        ),
        migrations.AddField(
            model_name='integrantecuadrilla',
            name='fecha_alta',
            field=models.DateField(auto_now_add=True, default=django.utils.timezone.now),
            preserve_default=False,
        ),
        migrations.AlterUniqueTogether(
            name='integrantecuadrilla',
            unique_together={('cuadrilla', 'trabajador')},
        ),
        migrations.AlterModelOptions(
            name='integrantecuadrilla',
            options={
                'ordering': ['trabajador__apellidos', 'trabajador__nombres'],
                'verbose_name': 'Integrante de Cuadrilla',
                'verbose_name_plural': 'Integrantes de Cuadrilla',
            },
        ),

        # Cuadrilla: agregar proyecto, capataz, ubicación, fechas, created_at + verbose_names
        migrations.AddField(
            model_name='cuadrilla',
            name='proyecto',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name='cuadrillas',
                to='proyectos.proyecto',
                null=True,
            ),
        ),
        migrations.AddField(
            model_name='cuadrilla',
            name='capataz',
            field=models.ForeignKey(
                null=True, blank=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='cuadrillas_a_cargo',
                to='maquinaria.trabajador',
                verbose_name='Capataz / Responsable',
            ),
        ),
        migrations.AddField(
            model_name='cuadrilla',
            name='ubicacion',
            field=models.CharField(blank=True, max_length=200, verbose_name='Ubicación / Zona de obra'),
        ),
        migrations.AddField(
            model_name='cuadrilla',
            name='fecha_inicio',
            field=models.DateField(blank=True, null=True, verbose_name='Fecha de inicio'),
        ),
        migrations.AddField(
            model_name='cuadrilla',
            name='fecha_fin',
            field=models.DateField(blank=True, null=True, verbose_name='Fecha de fin'),
        ),
        migrations.AddField(
            model_name='cuadrilla',
            name='created_at',
            field=models.DateTimeField(auto_now_add=True, default=django.utils.timezone.now),
            preserve_default=False,
        ),
        migrations.AlterField(
            model_name='cuadrilla',
            name='nombre',
            field=models.CharField(max_length=200, verbose_name='Nombre del frente'),
        ),
        migrations.AlterField(
            model_name='cuadrilla',
            name='descripcion',
            field=models.TextField(blank=True, verbose_name='Descripción'),
        ),
        # Tras el wipe la tabla está vacía: fijamos proyecto como NOT NULL.
        migrations.AlterField(
            model_name='cuadrilla',
            name='proyecto',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name='cuadrillas',
                to='proyectos.proyecto',
            ),
        ),
    ]
