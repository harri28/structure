from django.apps import AppConfig


class RegistroConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.registro'
    verbose_name = 'Registro de Actividad'

    def ready(self):
        from django.contrib.auth.signals import user_logged_in
        from django.dispatch import receiver

        @receiver(user_logged_in)
        def on_login(sender, request, user, **kwargs):
            from .models import RegistroAccion
            ip = request.META.get('HTTP_X_FORWARDED_FOR', request.META.get('REMOTE_ADDR', ''))
            if ip and ',' in ip:
                ip = ip.split(',')[0].strip()
            RegistroAccion.objects.create(
                usuario=user,
                accion='LOGIN',
                modulo='Sesión',
                descripcion=f'{user.username} inició sesión',
                ip=ip or None,
            )
