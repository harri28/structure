"""
Utilidades de permisos para S&S Gestión.
Uso en vistas: from config.permisos import tiene, proyectos_visibles
"""


def tiene(user, permiso):
    """True si el usuario tiene el permiso indicado."""
    if not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    try:
        rol = user.perfil.rol
        if rol is None:
            return False
        if rol.es_superadmin:
            return True
        return getattr(rol, permiso, False)
    except AttributeError:
        return False


def proyectos_visibles(user):
    """
    QuerySet de proyectos que el usuario puede ver.
    Regla: el filtro por membresía solo aplica si el usuario tiene un rol
    explícito SIN acceso_todos_proyectos. Sin rol asignado ve todo.
    """
    from apps.proyectos.models import Proyecto
    if not user.is_authenticated:
        return Proyecto.objects.none()
    if user.is_superuser:
        return Proyecto.objects.all()
    try:
        rol = user.perfil.rol
        if rol is None:
            return Proyecto.objects.all()
        if rol.es_superadmin or rol.acceso_todos_proyectos:
            return Proyecto.objects.all()
        # Rol explícito sin acceso total → solo proyectos asignados
        return Proyecto.objects.filter(miembros__usuario=user)
    except AttributeError:
        # Sin perfil creado → ve todo
        return Proyecto.objects.all()


def permisos_dict(user):
    """Devuelve un dict {campo: bool} con todos los permisos del usuario."""
    from apps.configuracion.models import TODOS_LOS_PERMISOS
    if not user.is_authenticated:
        return {}
    if user.is_superuser:
        return {p: True for p in TODOS_LOS_PERMISOS}
    try:
        rol = user.perfil.rol
        if rol is None:
            return {p: False for p in TODOS_LOS_PERMISOS}
        if rol.es_superadmin:
            return {p: True for p in TODOS_LOS_PERMISOS}
        return {p: getattr(rol, p, False) for p in TODOS_LOS_PERMISOS}
    except AttributeError:
        return {p: False for p in TODOS_LOS_PERMISOS}
