from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('maquinaria', '0015_cargos_corrige_defectos'),
    ]

    operations = [
        migrations.AddField(
            model_name='registromaquinaria',
            name='hora_inicio',
            field=models.TimeField(blank=True, null=True, verbose_name='Hora inicial'),
        ),
        migrations.AddField(
            model_name='registromaquinaria',
            name='hora_fin',
            field=models.TimeField(blank=True, null=True, verbose_name='Hora final'),
        ),
    ]
