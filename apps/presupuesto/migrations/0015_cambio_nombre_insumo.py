from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('presupuesto', '0014_ampliacion_insumo'),
    ]

    operations = [
        migrations.CreateModel(
            name='CambioNombreInsumo',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('nombre_anterior', models.CharField(max_length=300)),
                ('nombre_nuevo', models.CharField(max_length=300)),
                ('justificacion', models.TextField(blank=True)),
                ('fecha', models.DateTimeField(auto_now_add=True)),
                ('insumo', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='cambios_nombre',
                    to='presupuesto.insumopresupuesto',
                )),
                ('usuario', models.ForeignKey(
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={
                'verbose_name': 'Cambio de nombre de insumo',
                'verbose_name_plural': 'Cambios de nombre de insumo',
                'ordering': ['-fecha'],
            },
        ),
    ]
