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
            'tema_favicon':        cfg.favicon.url if cfg.favicon else '',
            'tema_fondo_login':    cfg.imagen_fondo_login.url if cfg.imagen_fondo_login else '',
            'tema_login_titulo':    cfg.login_titulo or '',
            'tema_login_subtitulo': cfg.login_subtitulo or '',
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

    Alimenta el badge de la 'Bandeja de Entrada' del Jefe de obra.
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
        from config.permisos import permisos_dict, _rol_efectivo
        # Preferimos el proyecto del URL (la vista que se está ejecutando)
        # sobre el activo de sesión, para que {{ permisos }} coincida con
        # lo que @requiere acaba de autorizar.
        pid = None
        try:
            rm = getattr(request, 'resolver_match', None)
            if rm and rm.kwargs:
                pid = rm.kwargs.get('proyecto_id')
        except Exception:
            pass
        if not pid:
            pid = request.session.get('proyecto_id')
        rol = _rol_efectivo(request.user, pid)
        return {
            'permisos':    permisos_dict(request.user, pid),
            'rol_actual':  rol,
        }
    except Exception:
        return {'permisos': {}}
