"""
Data migration — "Administrador de Obra" y "Jefe de obra" son el mismo rol.

Ambos roles sembrados tenían permisos distintos (p. ej. solo "Jefe de obra"
podía editar proyectos y solo "Administrador de Obra" tenía
`puede_configurar_proyecto`). Se decidió que son equivalentes, así que cada
permiso queda activo en ambos si lo tenía cualquiera de los dos (unión).

Excepción: `puede_administrar_usuarios` y `puede_administrar_roles` NO se
tocan. La migración 0022 dejó "Usuarios & Roles" como exclusivo de
Superadmin para el Administrador de Obra; no se amplía aquí.

Idempotente: si falta alguno de los dos roles no hace nada. No reversible
(no se guarda el estado previo).
"""
from django.db import migrations

NO_UNIFICAR = {'puede_administrar_usuarios', 'puede_administrar_roles'}


def unificar(apps, schema_editor):
    Rol = apps.get_model('configuracion', 'Rol')
    admin = Rol.objects.filter(nombre='Administrador de Obra').first()
    jefe = Rol.objects.filter(nombre='Jefe de obra').first()
    if not admin or not jefe:
        return
    campos = [
        f.name for f in Rol._meta.get_fields()
        if f.name.startswith('puede_') and f.name not in NO_UNIFICAR
    ]
    for c in campos:
        valor = bool(getattr(admin, c) or getattr(jefe, c))
        setattr(admin, c, valor)
        setattr(jefe, c, valor)
    admin.save(update_fields=campos)
    jefe.save(update_fields=campos)


class Migration(migrations.Migration):

    dependencies = [
        ('configuracion', '0022_admin_obra_puede_configurar_empresa'),
    ]

    operations = [
        migrations.RunPython(unificar, migrations.RunPython.noop),
    ]
