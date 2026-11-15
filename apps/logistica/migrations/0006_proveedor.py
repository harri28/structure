from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('logistica', '0005_guiaremision_motivo_otro'),
    ]

    operations = [
        migrations.CreateModel(
            name='Proveedor',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('ruc', models.CharField(max_length=11, verbose_name='RUC / DNI')),
                ('razon_social', models.CharField(max_length=200, verbose_name='Razón Social')),
                ('nombre_comercial', models.CharField(blank=True, max_length=200, verbose_name='Nombre Comercial')),
                ('telefono', models.CharField(blank=True, max_length=50, verbose_name='Teléfono')),
                ('email', models.EmailField(blank=True, max_length=254, verbose_name='E-mail')),
                ('persona_contacto', models.CharField(blank=True, max_length=150, verbose_name='Persona de Contacto')),
                ('direccion', models.CharField(blank=True, max_length=300, verbose_name='Dirección')),
                ('activo', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
            ],
            options={
                'verbose_name': 'Proveedor',
                'verbose_name_plural': 'Proveedores',
                'ordering': ['razon_social'],
            },
        ),
    ]
