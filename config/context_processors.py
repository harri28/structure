def proyecto_activo(request):
    """Inyecta el proyecto con activo=True en todos los templates."""
    try:
        if not request.user.is_authenticated:
            return {}
        from apps.proyectos.models import Proyecto
        p = Proyecto.objects.filter(activo=True).only('pk', 'codigo', 'nombre', 'estado').first()
        if p:
            return {'proyecto_activo': p}
    except Exception:
        pass
    return {}


def permisos_usuario(request):
    """Inyecta el dict 'permisos' y el 'rol_actual' en todos los templates."""
    try:
        if not request.user.is_authenticated:
            return {'permisos': {}}
        from config.permisos import permisos_dict
        rol = None
        try:
            rol = request.user.perfil.rol
        except AttributeError:
            pass
        return {'permisos': permisos_dict(request.user), 'rol_actual': rol}
    except Exception:
        return {'permisos': {}}
