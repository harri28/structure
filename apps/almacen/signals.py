from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from .models import DetalleEntrada, DetalleSalida
from .utils import actualizar_stock_almacen


@receiver([post_save, post_delete], sender=DetalleEntrada)
def _sync_entrada(sender, instance, **kwargs):
    if instance.insumo_id:
        actualizar_stock_almacen(instance.insumo)


@receiver([post_save, post_delete], sender=DetalleSalida)
def _sync_salida(sender, instance, **kwargs):
    if instance.insumo_id:
        actualizar_stock_almacen(instance.insumo)
