import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('presupuesto', '0003_partida_partida_origen_presupuesto_presupuesto_base_and_more'),
        ('proyectos', '0003_proyecto_activo'),
    ]

    operations = [
        migrations.CreateModel(
            name='Modificacion',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('tipo', models.CharField(
                    choices=[
                        ('ADICIONAL', 'Adicional de Obra'),
                        ('DEDUCTIVO', 'Deductivo de Obra'),
                        ('VINCULANTE', 'Adicional con Deductivo Vinculante'),
                    ],
                    max_length=20,
                )),
                ('numero', models.PositiveIntegerField()),
                ('nombre', models.CharField(max_length=300)),
                ('estado', models.CharField(
                    choices=[
                        ('PENDIENTE', 'Pendiente de Aprobación'),
                        ('APROBADO', 'Aprobado'),
                        ('EJECUTADO', 'Ejecutado'),
                        ('RECHAZADO', 'Rechazado'),
                    ],
                    default='PENDIENTE',
                    max_length=20,
                )),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('proyecto', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='modificaciones',
                    to='proyectos.proyecto',
                )),
            ],
            options={
                'verbose_name': 'Modificación',
                'verbose_name_plural': 'Modificaciones',
                'ordering': ['tipo', 'numero'],
            },
        ),
        migrations.AddConstraint(
            model_name='modificacion',
            constraint=models.UniqueConstraint(
                fields=['proyecto', 'tipo', 'numero'],
                name='unique_modificacion_numero',
            ),
        ),
        migrations.CreateModel(
            name='PartidaModificacion',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('subtipo', models.CharField(
                    choices=[('ADICIONAL', 'Adicional'), ('DEDUCTIVO', 'Deductivo')],
                    default='ADICIONAL',
                    max_length=20,
                )),
                ('codigo', models.CharField(blank=True, max_length=50)),
                ('nombre', models.CharField(max_length=500)),
                ('unidad', models.CharField(blank=True, max_length=20)),
                ('cantidad', models.DecimalField(decimal_places=4, default=0, max_digits=15)),
                ('precio_unitario', models.DecimalField(decimal_places=4, default=0, max_digits=15)),
                ('orden', models.PositiveIntegerField(default=0)),
                ('modificacion', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='partidas',
                    to='presupuesto.modificacion',
                )),
                ('partida_origen', models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='en_modificaciones',
                    to='presupuesto.partida',
                )),
            ],
            options={
                'verbose_name': 'Partida de Modificación',
                'verbose_name_plural': 'Partidas de Modificación',
                'ordering': ['subtipo', 'orden'],
            },
        ),
    ]
