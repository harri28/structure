from django.apps import AppConfig


class RegistroConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.registro'
    verbose_name = 'Registro de Actividad'

    def ready(self):
        # Importa los receivers de autenticación (login / logout / login fallido).
        # El import es suficiente — los @receiver se registran al cargarse el módulo.
        from . import signals  # noqa: F401
