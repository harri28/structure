from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('configuracion', '0027_configempresa_favicon'),
    ]

    operations = [
        migrations.AddField(
            model_name='configempresa',
            name='imagen_fondo_login',
            field=models.ImageField(
                blank=True,
                null=True,
                upload_to='empresa/fondo_login/',
                verbose_name='Fondo de Login',
                help_text='Imagen de fondo a pantalla completa detrás del formulario de ingreso.',
            ),
        ),
    ]
