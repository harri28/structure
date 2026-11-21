from django.db import models


class SyncLog(models.Model):
    """Trazabilidad de requests idempotentes desde la app móvil.

    Cada acción que crea un recurso (ej: POST /api/requerimientos/) viene con
    un `client_uuid` generado en el cliente. Si la red se corta justo al
    confirmar y el cliente reintenta, el backend busca el uuid en esta tabla
    y devuelve el recurso ya creado en lugar de duplicarlo.
    """
    client_uuid   = models.UUIDField(unique=True, db_index=True)
    usuario       = models.ForeignKey('auth.User', null=True, on_delete=models.SET_NULL)
    endpoint      = models.CharField(max_length=120)   # ej: 'requerimientos:crear'
    requerimiento = models.ForeignKey(
        'requerimientos.Requerimiento', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='sync_logs',
    )
    created_at    = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name        = 'Registro de sincronización'
        verbose_name_plural = 'Registros de sincronización'
        ordering            = ['-created_at']
