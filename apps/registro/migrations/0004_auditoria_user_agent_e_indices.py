from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('registro', '0003_alter_registroaccion_modulo'),
    ]

    operations = [
        migrations.AddField(
            model_name='registroaccion',
            name='user_agent',
            field=models.TextField(blank=True, verbose_name='User-Agent'),
        ),
        migrations.AlterField(
            model_name='registroaccion',
            name='accion',
            field=models.CharField(
                choices=[
                    ('CREAR', 'Crear'),
                    ('EDITAR', 'Editar'),
                    ('ELIMINAR', 'Eliminar'),
                    ('IMPORTAR', 'Importar'),
                    ('APROBAR', 'Aprobar'),
                    ('ANULAR', 'Anular'),
                    ('LOGIN', 'Iniciar sesión'),
                    ('LOGOUT', 'Cerrar sesión'),
                    ('LOGIN_FAIL', 'Intento fallido de login'),
                    ('OTRO', 'Otro'),
                ],
                default='OTRO',
                max_length=20,
            ),
        ),
        migrations.AddIndex(
            model_name='registroaccion',
            index=models.Index(fields=['-fecha'], name='registro_fecha_idx'),
        ),
        migrations.AddIndex(
            model_name='registroaccion',
            index=models.Index(fields=['accion', '-fecha'], name='registro_accion_idx'),
        ),
        migrations.AddIndex(
            model_name='registroaccion',
            index=models.Index(fields=['usuario', '-fecha'], name='registro_usuario_idx'),
        ),
        migrations.AddIndex(
            model_name='registroaccion',
            index=models.Index(fields=['ip'], name='registro_ip_idx'),
        ),
    ]
