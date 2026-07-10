def proyecto_activo(request):
    """Inyecta el proyecto seleccionado en sesión en todos los templates."""
    try:
        if not request.user.is_authenticated:
            return {}
        pid = request.session.get('proyecto_id')
        if not pid:
            return {}
        from apps.proyectos.models import Proyecto
        p = Proyecto.objects.only('pk', 'codigo', 'nombre', 'estado').get(pk=pid)
        return {'proyecto_activo': p}
    except Exception:
        return {}


def notif_no_leidas(request):
    try:
        if not request.user.is_authenticated:
            return {'notif_count': 0}
        from apps.registro.models import Notificacion
        count = Notificacion.objects.filter(usuario=request.user, leida=False).count()
        return {'notif_count': count}
    except Exception:
        return {'notif_count': 0}


def req_enviados_count(request):
    try:
        if not request.user.is_authenticated:
            return {'req_enviados': 0}
        pid = request.session.get('proyecto_id')
        if not pid:
            return {'req_enviados': 0}
        from apps.requerimientos.models import Requerimiento
        count = Requerimiento.objects.filter(proyecto_id=pid, estado='ENVIADO').count()
        return {'req_enviados': count}
    except Exception:
        return {'req_enviados': 0}


def permisos_usuario(request):
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
