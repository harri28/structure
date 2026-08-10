# Rename propietario → propietario_documento + agregado de 3 nuevos campos.
# Preserva el valor viejo copiándolo a propietario_razon_social.

from django.db import migrations, models


def copiar_propietario_a_razon_social(apps, schema_editor):
    Maquinaria = apps.get_model('maquinaria', 'Maquinaria')
    for m in Maquinaria.objects.all():
        if m.propietario:
            m.propietario_razon_social = m.propietario
            m.propietario = ''
            m.save(update_fields=['propietario_razon_social', 'propietario'])


def reverso_copiar(apps, schema_editor):
    Maquinaria = apps.get_model('maquinaria', 'Maquinaria')
    for m in Maquinaria.objects.all():
        if m.propietario_razon_social and not m.propietario:
            m.propietario = m.propietario_razon_social
            m.save(update_fields=['propietario'])


class Migration(migrations.Migration):

    dependencies = [
        ('maquinaria', '0008_alter_registromaquinaria_hora_entrada_and_more'),
    ]

    operations = [
        # 1) Agregar los 3 nuevos campos (vacíos)
        migrations.AddField(
            model_name='maquinaria',
            name='propietario_razon_social',
            field=models.CharField(blank=True, max_length=200, verbose_name='Razón social'),
        ),
        migrations.AddField(
            model_name='maquinaria',
            name='propietario_celular',
            field=models.CharField(blank=True, max_length=20, verbose_name='Celular'),
        ),
        migrations.AddField(
            model_name='maquinaria',
            name='propietario_direccion',
            field=models.CharField(blank=True, max_length=300, verbose_name='Dirección'),
        ),
        # 2) Copiar propietario → razon_social y vaciar propietario
        #    (necesario antes del rename para que el AlterField 200→15 no falle
        #    si el texto viejo supera 15 chars)
        migrations.RunPython(copiar_propietario_a_razon_social, reverso_copiar),
        # 3) Rename propietario → propietario_documento
        migrations.RenameField(
            model_name='maquinaria',
            old_name='propietario',
            new_name='propietario_documento',
        ),
        # 4) Ajustar max_length 200 → 15 (ya está vacío, no hay riesgo de truncado)
        migrations.AlterField(
            model_name='maquinaria',
            name='propietario_documento',
            field=models.CharField(blank=True, max_length=15, verbose_name='RUC / DNI'),
        ),
    ]