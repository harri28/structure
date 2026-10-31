from django.db import migrations


DEFECTOS = [
    ('PEON',    'Peón',       10),
    ('MAESTRO', 'Maestro',    20),
    ('ASIST',   'Asistente',  30),
]


def crear_defectos(apps, schema_editor):
    TipoPersonal = apps.get_model('maquinaria', 'TipoPersonal')
    for codigo, nombre, _orden in DEFECTOS:
        TipoPersonal.objects.get_or_create(
            codigo=codigo,
            defaults={'nombre': nombre, 'costo_hora': 0, 'activo': True},
        )


def borrar_defectos(apps, schema_editor):
    TipoPersonal = apps.get_model('maquinaria', 'TipoPersonal')
    # Solo borra si no se usan en ningún trabajador (seguridad)
    for codigo, _nombre, _orden in DEFECTOS:
        tp = TipoPersonal.objects.filter(codigo=codigo).first()
        if tp and not tp.trabajadores.exists():
            tp.delete()


class Migration(migrations.Migration):

    dependencies = [
        ('maquinaria', '0013_asistencia'),
    ]

    operations = [
        migrations.RunPython(crear_defectos, reverse_code=borrar_defectos),
    ]
