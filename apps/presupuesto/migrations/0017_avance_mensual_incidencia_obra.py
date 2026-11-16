from decimal import Decimal
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('presupuesto', '0016_igv_default_cero'),
        ('proyectos', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='AvanceMensual',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('anio', models.PositiveSmallIntegerField(verbose_name='Año')),
                ('mes', models.PositiveSmallIntegerField(
                    choices=[(1, 'Ene'), (2, 'Feb'), (3, 'Mar'), (4, 'Abr'),
                             (5, 'May'), (6, 'Jun'), (7, 'Jul'), (8, 'Ago'),
                             (9, 'Sep'), (10, 'Oct'), (11, 'Nov'), (12, 'Dic')],
                    verbose_name='Mes',
                )),
                ('programado_pct', models.DecimalField(decimal_places=2, default=Decimal('0'), max_digits=5, verbose_name='Programado (%)')),
                ('ejecutado_pct', models.DecimalField(decimal_places=2, default=Decimal('0'), max_digits=5, verbose_name='Ejecutado (%)')),
                ('monto_programado', models.DecimalField(decimal_places=2, default=Decimal('0'), max_digits=15, verbose_name='Monto programado (S/)')),
                ('monto_ejecutado', models.DecimalField(decimal_places=2, default=Decimal('0'), max_digits=15, verbose_name='Monto ejecutado (S/)')),
                ('observaciones', models.TextField(blank=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('created_by', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='avances_registrados',
                    to=settings.AUTH_USER_MODEL,
                )),
                ('proyecto', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='avances_mensuales',
                    to='proyectos.proyecto',
                )),
            ],
            options={
                'verbose_name': 'Avance mensual',
                'verbose_name_plural': 'Avances mensuales',
                'ordering': ['anio', 'mes'],
                'unique_together': {('proyecto', 'anio', 'mes')},
            },
        ),
        migrations.CreateModel(
            name='IncidenciaObra',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('fecha', models.DateField()),
                ('tipo', models.CharField(
                    choices=[('INCIDENCIA', 'Incidencia'), ('EVENTO', 'Evento')],
                    default='INCIDENCIA', max_length=20,
                )),
                ('severidad', models.CharField(
                    choices=[('ALTA', 'Alta'), ('MEDIA', 'Media'), ('BAJA', 'Baja')],
                    default='MEDIA', max_length=10,
                )),
                ('descripcion', models.TextField()),
                ('responsable', models.CharField(blank=True, max_length=200)),
                ('estado', models.CharField(
                    choices=[('ABIERTA', 'Abierta'), ('CERRADA', 'Cerrada')],
                    default='ABIERTA', max_length=10,
                )),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('created_by', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='incidencias_registradas',
                    to=settings.AUTH_USER_MODEL,
                )),
                ('partida', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='incidencias',
                    to='presupuesto.partida',
                )),
                ('proyecto', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='incidencias_obra',
                    to='proyectos.proyecto',
                )),
            ],
            options={
                'verbose_name': 'Incidencia de obra',
                'verbose_name_plural': 'Incidencias de obra',
                'ordering': ['-fecha', '-id'],
            },
        ),
    ]
