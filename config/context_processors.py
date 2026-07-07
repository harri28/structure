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


def notif_no_leidas(request):
    """Inyecta el contador de notificaciones no leídas en todos los templates."""
    try:
        if not request.user.is_authenticated:
            return {'notif_count': 0}
        from apps.registro.models import Notificacion
        count = Notificacion.objects.filter(usuario=request.user, leida=False).count()
        return {'notif_count': count}
    except Exception:
        return {'notif_count': 0}


def req_enviados_count(request):
    """Inyecta el conteo de requerimientos enviados a Logística pendientes de atención."""
    try:
        if not request.user.is_authenticated:
            return {'req_enviados': 0}
        from apps.proyectos.models import Proyecto
        from apps.requerimientos.models import Requerimiento
        proyecto = Proyecto.objects.filter(activo=True).first()
        if not proyecto:
            return {'req_enviados': 0}
        count = Requerimiento.objects.filter(proyecto=proyecto, estado='ENVIADO').count()
        return {'req_enviados': count}
    except Exception:
        return {'req_enviados': 0}


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
