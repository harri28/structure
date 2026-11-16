from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('configuracion', '0030_configempresa_login_texto_tamanos'),
    ]

    operations = [
        migrations.AddField(
            model_name='perfilusuario',
            name='cliente',
            field=models.CharField(blank=True, max_length=200, verbose_name='Cliente'),
        ),
        migrations.AddField(
            model_name='perfilusuario',
            name='ubicacion',
            field=models.CharField(blank=True, max_length=300, verbose_name='Ubicación'),
        ),
        migrations.AddField(
            model_name='perfilusuario',
            name='descripcion',
            field=models.TextField(blank=True, verbose_name='Descripción'),
        ),
    ]
