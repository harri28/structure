"""
Utilidades de permisos para S&S Gestión.
Uso en vistas: from config.permisos import tiene, requiere, proyectos_visibles
"""
from functools import wraps

from django.contrib import messages
from django.shortcuts import redirect


def _rol_efectivo(user, proyecto_id=None):
    """
    Devuelve el rol efectivo del usuario para un proyecto dado.
    Precedencia:
      1. ProyectoMiembro.rol (si proyecto_id está dado y la membresía tiene rol)
      2. PerfilUsuario.rol (rol global, fallback)
    Devuelve None si no hay ningún rol.
    """
    rol_global = None
    try:
        rol_global = user.perfil.rol
    except AttributeError:
        pass
    if proyecto_id:
        try:
            from apps.proyectos.models import ProyectoMiembro
            miembro = ProyectoMiembro.objects.select_related('rol').filter(
                usuario=user, proyecto_id=proyecto_id,
            ).first()
            if miembro and miembro.rol:
                return miembro.rol
        except Exception:
            pass
    return rol_global


def tiene(user, permiso, proyecto_id=None):
    """
    True si el usuario tiene el permiso indicado.
    Si `proyecto_id` se proporciona, se resuelve contra el rol específico
    del proyecto (si lo hay); sino cae al rol global del perfil.
    """
    if not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    try:
        rol = _rol_efectivo(user, proyecto_id)
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


def permisos_dict(user, proyecto_id=None):
    """
    Devuelve un dict {campo: bool} con todos los permisos efectivos del usuario.
    Si `proyecto_id` se proporciona, usa el rol específico del proyecto cuando
    existe; sino cae al rol global del perfil.
    """
    from apps.configuracion.models import TODOS_LOS_PERMISOS
    if not user.is_authenticated:
        return {}
    if user.is_superuser:
        return {p: True for p in TODOS_LOS_PERMISOS}
    try:
        rol = _rol_efectivo(user, proyecto_id)
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

    Si la URL incluye `proyecto_id`, el decorador resuelve el permiso contra
    el rol efectivo en ese proyecto (override de ProyectoMiembro.rol si existe,
    sino el rol global del PerfilUsuario). Así un usuario con rol restringido
    en la Obra A no puede saltarse la restricción navegando directo por URL,
    aunque su proyecto activo de sesión sea otro.

    La autenticación ya la garantiza `LoginRequiredMiddleware`, así que aquí
    solo se comprueba autorización.
    """
    def decorator(view):
        @wraps(view)
        def _wrapped(request, *args, **kwargs):
            proyecto_id = kwargs.get('proyecto_id')
            if any(tiene(request.user, p, proyecto_id=proyecto_id) for p in permisos):
                return view(request, *args, **kwargs)
            messages.warning(request, 'No tienes permiso para acceder a esa sección.')
            return redirect('proyectos:dashboard')
        return _wrapped
    return decorator
