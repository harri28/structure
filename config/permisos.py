"""
Utilidades de permisos para S&S Gestión.
Uso en vistas: from config.permisos import tiene, requiere, proyectos_visibles
"""
from functools import wraps

from django.contrib import messages
from django.shortcuts import redirect


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


def proyecto_visible(view):
    """
    Decorador de aislamiento entre proyectos.

    Verifica que el `proyecto_id` de la URL sea visible para el usuario según
    `proyectos_visibles()`. Cierra el hueco donde un usuario con permiso general
    (por ej. `puede_gestionar_entradas`) podría acceder por URL directa a un
    proyecto del que no es miembro.

    Se usa APILADO con `@requiere(...)` — primero `@requiere` (verifica permiso),
    luego `@proyecto_visible` (verifica pertenencia al proyecto):

        @requiere('puede_gestionar_entradas')
        @proyecto_visible
        def entrada_lista(request, proyecto_id): ...

    Si la vista no recibe `proyecto_id` como kwarg, el decorador es no-op.
    """
    @wraps(view)
    def _wrapped(request, *args, **kwargs):
        proyecto_id = kwargs.get('proyecto_id')
        if proyecto_id is not None:
            if not proyectos_visibles(request.user).filter(pk=proyecto_id).exists():
                messages.warning(request, 'No tienes acceso a ese proyecto.')
                return redirect('proyectos:dashboard')
        return view(request, *args, **kwargs)
    return _wrapped


def requiere(*permisos):
    """
    Decorador RBAC para vistas. Bloquea el acceso si el usuario no tiene
    NINGUNO de los permisos indicados; redirige al dashboard con un mensaje.

    Superuser y roles con `es_superadmin` pasan siempre (los cubre `tiene()`).
    Con varios permisos basta con tener uno (semántica OR — coincide con el
    patrón `perm_a or perm_b` que hoy usa el sidebar).

        @requiere('puede_administrar_usuarios')
        def usuarios(request): ...

        @requiere('puede_administrar_usuarios', 'puede_administrar_roles')
        def equipo(request): ...

    La autenticación ya la garantiza `LoginRequiredMiddleware`, así que aquí
    solo se comprueba autorización.
    """
    def decorator(view):
        @wraps(view)
        def _wrapped(request, *args, **kwargs):
            if any(tiene(request.user, p) for p in permisos):
                return view(request, *args, **kwargs)
            messages.warning(request, 'No tienes permiso para acceder a esa sección.')
            return redirect('proyectos:dashboard')
        return _wrapped
    return decorator
