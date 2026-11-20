from django.db import migrations, models


class Migration(migrations.Migration):
    """Horómetro numérico y correlativo propio de turno.

    Los campos hora_inicio / hora_fin dejan de ser TimeField (hora reloj) y
    pasan a ser DecimalField (lectura del horómetro de la máquina). Para que
    PostgreSQL no se queje del cambio de tipo, los borramos y los creamos
    de nuevo (los valores previos eran de prueba y no son recuperables como
    horómetro). Si en producción hay turnos reales ya cargados, hay que
    recapturar su horómetro desde el parte físico."""

    dependencies = [
        ('maquinaria', '0016_registro_hora_reloj'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='registromaquinaria',
            name='hora_inicio',
        ),
        migrations.RemoveField(
            model_name='registromaquinaria',
            name='hora_fin',
        ),
        migrations.AddField(
            model_name='registromaquinaria',
            name='hora_inicio',
            field=models.DecimalField(
                blank=True, decimal_places=2, max_digits=10, null=True,
                verbose_name='Horómetro inicial',
            ),
        ),
        migrations.AddField(
            model_name='registromaquinaria',
            name='hora_fin',
            field=models.DecimalField(
                blank=True, decimal_places=2, max_digits=10, null=True,
                verbose_name='Horómetro final',
            ),
        ),
        migrations.AddField(
            model_name='registromaquinaria',
            name='numero_turno',
            field=models.PositiveIntegerField(blank=True, null=True, verbose_name='N° Turno'),
        ),
    ]
