"""
Data migration — siembra los 3 roles operativos definidos en el diseño RBAC
(ver arquitectura_structure.md §2 y REGLAS_NEGOCIO.md §6).

Comportamiento idempotente:
- Si el rol ya existe (mismo nombre), NO se modifica.
- Si el rol no existe, se crea con los permisos declarados aquí.

El reverso (migrate zero) es no-op: los roles semilla no se borran automáticamente
para no romper asignaciones de usuarios. Si hace falta eliminarlos, se hace
manualmente desde `/configuracion/roles/`.
"""
from django.db import migrations


ROLES_SEMILLA = [
    {
        'nombre': 'Administrador de Obra',
        'descripcion': (
            'Residente del proyecto. Gestiona presupuesto, requerimientos, '
            'cuadrilla, maquinaria, personal del proyecto. No es admin del sistema.'
        ),
        'permisos': [
            'puede_ver_dashboard',
            'puede_ver_presupuesto',
            'puede_editar_presupuesto',
            'puede_crear_requerimientos',
            'puede_aprobar_requerimientos',
            'puede_ver_maquinaria',
            'puede_gestionar_maquinaria',
            'puede_editar_catalogo',
            'puede_gestionar_personal',
            'puede_ver_actividad',
            'puede_configurar_proyecto',
        ],
    },
    {
        'nombre': 'Logística',
        'descripcion': (
            'Área de logística del consorcio. Revisa requerimientos, cotiza, '
            'genera guías de remisión y gestiona inventarios/almacén de logística.'
        ),
        'permisos': [
            'puede_ver_logistica',
            'puede_revisar_reqs_log',
            'puede_gestionar_cotizaciones_log',
            'puede_gestionar_logistica',
            'puede_gestionar_inventarios_log',
            'puede_gestionar_almacen_log',
            'puede_gestionar_ctrl_maq_log',
        ],
    },
    {
        'nombre': 'Almacenero',
        'descripcion': (
            'Operador del almacén del proyecto. Solicita materiales al '
            'Administrador de Obra, recibe entradas y registra salidas.'
        ),
        'permisos': [
            'puede_ver_almacen',
            'puede_crear_requerimientos',
            'puede_gestionar_entradas',
            'puede_gestionar_salidas',
        ],
    },
]


def crear_roles_semilla(apps, schema_editor):
    Rol = apps.get_model('configuracion', 'Rol')

    # Todos los BooleanField del modelo Rol son permisos. Los enumeramos desde
    # el estado histórico del modelo para no acoplar la migración al código actual.
    from django.db.models import BooleanField
    campos_permiso = [
        f.name for f in Rol._meta.get_fields()
        if isinstance(f, BooleanField)
    ]

    for rol_data in ROLES_SEMILLA:
        rol, creado = Rol.objects.get_or_create(
            nombre=rol_data['nombre'],
            defaults={'descripcion': rol_data['descripcion']},
        )
        if not creado:
            # Ya existía (probablemente creado manualmente antes). No lo tocamos.
            print(f'    · Rol "{rol.nombre}" ya existe — no se modifica.')
            continue

        # Aplicar EXPLÍCITAMENTE todos los permisos:
        # True si están en la lista del rol; False en el resto.
        # Esto es necesario porque `puede_ver_dashboard` tiene default=True
        # y el Almacenero (que no lo tiene) debe recibirlo en False.
        permisos_del_rol = set(rol_data['permisos'])
        for permiso in campos_permiso:
            setattr(rol, permiso, permiso in permisos_del_rol)
        rol.save()
        print(f'    · Rol "{rol.nombre}" creado con {len(permisos_del_rol)} permisos.')


def eliminar_roles_semilla(apps, schema_editor):
    # No-op deliberado: al revertir la migración NO borramos los roles semilla
    # para no romper asignaciones de PerfilUsuario. Si hace falta eliminarlos,
    # se hace manualmente desde /configuracion/roles/.
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('configuracion', '0018_rol_puede_configurar_proyecto_and_more'),
    ]

    operations = [
        migrations.RunPython(crear_roles_semilla, eliminar_roles_semilla),
    ]
