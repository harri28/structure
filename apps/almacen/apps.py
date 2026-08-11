from django.apps import AppConfig


class AlmacenConfig(AppConfig):
    name = 'apps.almacen'

    def ready(self):
        from . import signals  # noqa: F401
