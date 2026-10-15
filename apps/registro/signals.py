from django.contrib.auth.signals import user_logged_in, user_logged_out, user_login_failed
from django.dispatch import receiver

from .utils import _ip_from_request, _ua_from_request, log_evento


@receiver(user_logged_in)
def _on_logged_in(sender, request, user, **kwargs):
    log_evento(
        usuario=user,
        accion='LOGIN',
        modulo='Sesión',
        descripcion=f'Inicio de sesión: {user.username}',
        ip=_ip_from_request(request) if request else None,
        user_agent=_ua_from_request(request) if request else '',
    )


@receiver(user_logged_out)
def _on_logged_out(sender, request, user, **kwargs):
    if user is None:
        return
    log_evento(
        usuario=user,
        accion='LOGOUT',
        modulo='Sesión',
        descripcion=f'Cierre de sesión: {user.username}',
        ip=_ip_from_request(request) if request else None,
        user_agent=_ua_from_request(request) if request else '',
    )


@receiver(user_login_failed)
def _on_login_failed(sender, credentials, request=None, **kwargs):
    username = (credentials or {}).get('username', '')
    log_evento(
        usuario=None,  # el usuario no se autenticó
        accion='LOGIN_FAIL',
        modulo='Sesión',
        descripcion=f'Intento fallido de login con usuario="{username}"',
        ip=_ip_from_request(request) if request else None,
        user_agent=_ua_from_request(request) if request else '',
    )
