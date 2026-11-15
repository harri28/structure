from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('presupuesto', '0013_insumo_total_4_decimales'),
    ]

    operations = [
        migrations.CreateModel(
            name='AmpliacionInsumo',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('cantidad', models.DecimalField(decimal_places=4, max_digits=15)),
                ('justificacion', models.TextField(blank=True)),
                ('fecha', models.DateTimeField(auto_now_add=True)),
                ('insumo', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='ampliaciones',
                    to='presupuesto.insumopresupuesto',
                )),
                ('usuario', models.ForeignKey(
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={
                'verbose_name': 'Ampliación de insumo',
                'verbose_name_plural': 'Ampliaciones de insumo',
                'ordering': ['-fecha'],
            },
        ),
    ]
