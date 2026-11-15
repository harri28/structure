from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('configuracion', '0028_configempresa_imagen_fondo_login'),
    ]

    operations = [
        migrations.AddField(
            model_name='configempresa',
            name='login_titulo',
            field=models.CharField(
                blank=True,
                max_length=80,
                verbose_name='Título sobre el fondo de login',
                help_text='Texto grande que se muestra al costado izquierdo del formulario de ingreso. Dejar vacío para ocultar.',
            ),
        ),
        migrations.AddField(
            model_name='configempresa',
            name='login_subtitulo',
            field=models.CharField(
                blank=True,
                max_length=120,
                verbose_name='Subtítulo sobre el fondo de login',
                help_text='Línea pequeña bajo el título (por ejemplo, la versión del sistema). Dejar vacío para ocultar.',
            ),
        ),
    ]
