def log(request, accion, modulo, descripcion):
    """Registra una acción del usuario en el sistema."""
    from .models import RegistroAccion
    ip = request.META.get('HTTP_X_FORWARDED_FOR', request.META.get('REMOTE_ADDR', ''))
    if ip and ',' in ip:
        ip = ip.split(',')[0].strip()
    RegistroAccion.objects.create(
        usuario=request.user if request.user.is_authenticated else None,
        accion=accion,
        modulo=modulo,
        descripcion=descripcion,
        ip=ip or None,
    )


def notificar(titulo, mensaje='', url='', tipo='info', usuario=None):
    """
    Crea notificaciones en la base de datos.
    usuario=None → se envía a todos los usuarios activos.
    usuario=<User> → solo para ese usuario.
    """
    from .models import Notificacion
    from django.contrib.auth.models import User

    if usuario is None:
        usuarios = list(User.objects.filter(is_active=True).only('pk'))
    else:
        usuarios = [usuario]

    Notificacion.objects.bulk_create([
        Notificacion(usuario=u, titulo=titulo, mensaje=mensaje, url=url, tipo=tipo)
        for u in usuarios
    ])
