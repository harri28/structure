def _mezclar(hex_color, objetivo, factor):
    """Mezcla hex_color hacia objetivo (0,0,0 o 255,255,255) en la proporción `factor`."""
    hex_color = (hex_color or '').lstrip('#')
    if len(hex_color) != 6:
        hex_color = '2563eb'
    r, g, b = int(hex_color[0:2], 16), int(hex_color[2:4], 16), int(hex_color[4:6], 16)
    ro, go, bo = objetivo
    r = round(r + (ro - r) * factor)
    g = round(g + (go - g) * factor)
    b = round(b + (bo - b) * factor)
    return f'#{r:02x}{g:02x}{b:02x}'


def tema_empresa(request):
    """Inyecta el color primario configurado por la empresa como variables CSS."""
    try:
        from apps.configuracion.models import ConfigEmpresa
        cfg = ConfigEmpresa.get()
        color = cfg.color_primario or '#2563eb'
        return {
            'tema_color':          color,
            'tema_color_hover':    _mezclar(color, (0, 0, 0), 0.15),
            'tema_color_pale':     _mezclar(color, (255, 255, 255), 0.92),
            'tema_imagen_marca':   cfg.imagen_marca.url if cfg.imagen_marca else '',
        }
    except Exception:
        return {}


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


def req_solicitados_count(request):
    """Conteo de requerimientos en estado SOLICITADO del proyecto activo.

    Alimenta el badge de la 'Bandeja de Entrada' del Administrador de Obra.
    Ver REGLAS_NEGOCIO.md §10.
    """
    try:
        if not request.user.is_authenticated:
            return {'req_solicitados': 0}
        pid = request.session.get('proyecto_id')
        if not pid:
            return {'req_solicitados': 0}
        from apps.requerimientos.models import Requerimiento
        count = Requerimiento.objects.filter(proyecto_id=pid, estado='SOLICITADO').count()
        return {'req_solicitados': count}
    except Exception:
        return {'req_solicitados': 0}


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
