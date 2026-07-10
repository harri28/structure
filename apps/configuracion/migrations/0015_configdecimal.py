from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('configuracion', '0014_unidadmedida_decimales'),
    ]

    operations = [
        migrations.CreateModel(
            name='ConfigDecimal',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('codigo', models.CharField(max_length=20, unique=True, verbose_name='Código')),
                ('nombre', models.CharField(max_length=100, verbose_name='Nombre')),
                ('descripcion', models.CharField(blank=True, max_length=200, verbose_name='Descripción')),
                ('aliases', models.TextField(blank=True, help_text='Variantes separadas por coma.', verbose_name='Aliases')),
                ('decimales', models.PositiveSmallIntegerField(default=0, verbose_name='Decimales')),
                ('activo', models.BooleanField(default=True, verbose_name='Activo')),
            ],
            options={
                'verbose_name': 'Configuración Decimal',
                'verbose_name_plural': 'Configuraciones Decimales',
                'ordering': ['codigo'],
            },
        ),
    ]
