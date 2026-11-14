"""
Data migration — alinear el nombre del rol con el contrato del sistema.

El rol operativo del almacén se llama canónicamente "Almacenero" (así figura
en la seed 0019, en ROLES_BLOQUEADOS, en REGLAS_NEGOCIO.md y en el resto de
la documentación). En algún momento alguien lo renombró a "Almacen" desde
la UI, lo que dejó el rol fuera de ROLES_BLOQUEADOS y, en consecuencia,
reconfigurable desde la UI — algo que el diseño no permite.

Esta migración:
  1. Si existe un "Almacenero" previo (improbable), consolida sus FKs en
     el principal y borra el duplicado antes de renombrar.
  2. Renombra "Almacen" → "Almacenero". Mantiene permisos, usuarios y FKs.

Idempotente: si ya se corrió una vez (o si el rol ya se llama "Almacenero"),
no hace nada en la segunda ejecución. No reversible.
"""
from django.db import migrations


NOMBRE_VIEJO = 'Almacen'
NOMBRE_NUEVO = 'Almacenero'


def renombrar(apps, schema_editor):
    Rol = apps.get_model('configuracion', 'Rol')
    PerfilUsuario = apps.get_model('configuracion', 'PerfilUsuario')
    ProyectoMiembro = apps.get_model('proyectos', 'ProyectoMiembro')

    actual = Rol.objects.filter(nombre=NOMBRE_VIEJO).first()
    destino = Rol.objects.filter(nombre=NOMBRE_NUEVO).first()

    if actual:
        if destino:
            # Hay un "Almacenero" previo — consolidamos FKs en `actual` y
            # borramos el preexistente para liberar el nombre único.
            PerfilUsuario.objects.filter(rol=destino).update(rol=actual)
            ProyectoMiembro.objects.filter(rol=destino).update(rol=actual)
            destino.delete()
        actual.nombre = NOMBRE_NUEVO
        actual.save(update_fields=['nombre'])


class Migration(migrations.Migration):

    dependencies = [
        ('configuracion', '0024_renombrar_admin_obra_a_jefe_obra'),
        ('proyectos', '0007_proyectomiembro_rol'),
    ]

    operations = [
        migrations.RunPython(renombrar, migrations.RunPython.noop),
    ]
