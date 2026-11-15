from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('configuracion', '0029_configempresa_login_texto'),
    ]

    operations = [
        migrations.AddField(
            model_name='configempresa',
            name='login_titulo_tamano',
            field=models.PositiveSmallIntegerField(default=44, verbose_name='Tamaño del título (px)'),
        ),
        migrations.AddField(
            model_name='configempresa',
            name='login_subtitulo_tamano',
            field=models.PositiveSmallIntegerField(default=14, verbose_name='Tamaño del subtítulo (px)'),
        ),
    ]
