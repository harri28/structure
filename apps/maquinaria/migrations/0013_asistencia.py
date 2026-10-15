import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('maquinaria', '0012_cuadrilla_frente_de_trabajo'),
    ]

    operations = [
        migrations.CreateModel(
            name='Asistencia',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('fecha', models.DateField()),
                ('estado', models.CharField(choices=[('P', 'Presente'), ('F', 'Falta'), ('T', 'Tardanza'),
                                                     ('PM', 'Permiso'), ('D', 'Descanso'), ('FE', 'Feriado')],
                                            default='P', max_length=2)),
                ('observacion', models.CharField(blank=True, max_length=200)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('trabajador', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,
                                                 related_name='asistencias',
                                                 to='maquinaria.trabajador')),
            ],
            options={
                'verbose_name': 'Asistencia',
                'verbose_name_plural': 'Asistencias',
                'ordering': ['-fecha', 'trabajador__apellidos'],
                'unique_together': {('trabajador', 'fecha')},
            },
        ),
    ]
