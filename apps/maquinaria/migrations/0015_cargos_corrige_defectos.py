from django.db import migrations


A_AGREGAR = [
    ('OPER', 'Operario'),
    ('OFIC', 'Oficial'),
]
A_BORRAR = ['ASIST']


def corregir(apps, schema_editor):
    TipoPersonal = apps.get_model('maquinaria', 'TipoPersonal')
    # Agregar Operario y Oficial (idempotente)
    for codigo, nombre in A_AGREGAR:
        TipoPersonal.objects.get_or_create(
            codigo=codigo,
            defaults={'nombre': nombre, 'costo_hora': 0, 'activo': True},
        )
    # Borrar Asistente si no lo usa ningún trabajador
    for codigo in A_BORRAR:
        tp = TipoPersonal.objects.filter(codigo=codigo).first()
        if tp and not tp.trabajadores.exists():
            tp.delete()


def revertir(apps, schema_editor):
    TipoPersonal = apps.get_model('maquinaria', 'TipoPersonal')
    # Al revertir, quita los agregados (si no están en uso) y restaura Asistente
    for codigo, _nombre in A_AGREGAR:
        tp = TipoPersonal.objects.filter(codigo=codigo).first()
        if tp and not tp.trabajadores.exists():
            tp.delete()
    TipoPersonal.objects.get_or_create(
        codigo='ASIST',
        defaults={'nombre': 'Asistente', 'costo_hora': 0, 'activo': True},
    )


class Migration(migrations.Migration):

    dependencies = [
        ('maquinaria', '0014_tipos_personal_defecto'),
    ]

    operations = [
        migrations.RunPython(corregir, reverse_code=revertir),
    ]
