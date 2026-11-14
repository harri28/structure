"""
Data migration — fusionar "Administrador de Obra" y "Jefe de obra" bajo el
nombre "Jefe de obra".

Contexto: la migración 0023 ya había unificado los permisos operativos de
ambos roles, pero dejó los dos vivos. Hoy "Jefe de obra" no tiene usuarios
asignados y "Administrador de Obra" conserva al residente.

Esta migración:
  1. Elimina "Jefe de obra" si existe (es huérfano por diseño: 0 usuarios).
  2. Renombra "Administrador de Obra" → "Jefe de obra". Mantiene permisos,
     usuarios, FKs. Solo cambia el campo `nombre` (y actualiza la descripción
     para que refleje el nuevo título).

El orden importa por el UNIQUE constraint sobre `Rol.nombre`: primero
borrar el que lleva el nombre destino, luego renombrar.

Idempotente: si ya se corrió una vez, no hace nada en la segunda ejecución.
No es reversible (no se restaura el nombre viejo ni se recrea "Jefe de obra"
huérfano — nadie los necesita por separado).
"""
from django.db import migrations


NOMBRE_VIEJO = 'Administrador de Obra'
NOMBRE_NUEVO = 'Jefe de obra'
DESCRIPCION_NUEVA = (
    'Residente del proyecto. Gestiona presupuesto, requerimientos, '
    'cuadrilla, maquinaria, personal del proyecto. No es admin del sistema.'
)


def renombrar(apps, schema_editor):
    Rol = apps.get_model('configuracion', 'Rol')
    PerfilUsuario = apps.get_model('configuracion', 'PerfilUsuario')
    ProyectoMiembro = apps.get_model('proyectos', 'ProyectoMiembro')

    jefe_existente = Rol.objects.filter(nombre=NOMBRE_NUEVO).first()
    admin = Rol.objects.filter(nombre=NOMBRE_VIEJO).first()

    if admin:
        # Si hubiera un "Jefe de obra" previo, lo usamos como destino de
        # cualquier FK que todavía apunte a él (no debería haber ninguna,
        # pero curamos antes de borrar).
        if jefe_existente:
            PerfilUsuario.objects.filter(rol=jefe_existente).update(rol=admin)
            ProyectoMiembro.objects.filter(rol=jefe_existente).update(rol=admin)
            jefe_existente.delete()
        admin.nombre = NOMBRE_NUEVO
        admin.descripcion = DESCRIPCION_NUEVA
        admin.save(update_fields=['nombre', 'descripcion'])
    else:
        # No existe "Administrador de Obra" (ya fue renombrado antes).
        # Nos aseguramos de que, si queda un segundo "Jefe de obra" huérfano
        # por alguna razón, se consolide en el que tiene más usuarios.
        if jefe_existente and Rol.objects.filter(nombre=NOMBRE_NUEVO).count() > 1:
            principal = (
                Rol.objects.filter(nombre=NOMBRE_NUEVO)
                .order_by('-pk')
                .first()
            )
            duplicados = Rol.objects.filter(nombre=NOMBRE_NUEVO).exclude(pk=principal.pk)
            for d in duplicados:
                PerfilUsuario.objects.filter(rol=d).update(rol=principal)
                ProyectoMiembro.objects.filter(rol=d).update(rol=principal)
                d.delete()


class Migration(migrations.Migration):

    dependencies = [
        ('configuracion', '0023_unificar_admin_obra_jefe_obra'),
        ('proyectos', '0007_proyectomiembro_rol'),
    ]

    operations = [
        migrations.RunPython(renombrar, migrations.RunPython.noop),
    ]
