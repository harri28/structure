from django.db import models
from decimal import Decimal

ESTADOS_GUIA = [
    ('PENDIENTE',   'Pendiente'),
    ('EN_TRANSITO', 'En Tránsito'),
    ('ENTREGADO',   'Entregado'),
    ('ANULADO',     'Anulado'),
]

MOTIVOS_TRASLADO = [
    ('TRASLADO_OBRA',    'Traslado a obra'),
    ('TRASLADO_ALMACEN', 'Traslado a almacén'),
    ('COMPRA',           'Compra'),
    ('VENTA',            'Venta'),
    ('DEVOLUCION',       'Devolución'),
    ('OTRO',             'Otro'),
]


class Transportista(models.Model):
    ruc          = models.CharField('RUC', max_length=11, blank=True)
    razon_social = models.CharField('Razón Social', max_length=200)
    contacto     = models.CharField('Contacto', max_length=100, blank=True)
    telefono     = models.CharField('Teléfono', max_length=20, blank=True)
    email        = models.EmailField('E-mail', blank=True)
    activo       = models.BooleanField(default=True)

    class Meta:
        ordering            = ['razon_social']
        verbose_name        = 'Transportista'
        verbose_name_plural = 'Transportistas'

    def __str__(self):
        return self.razon_social


class GuiaRemision(models.Model):
    proyecto       = models.ForeignKey('proyectos.Proyecto', on_delete=models.CASCADE, related_name='guias')
    numero         = models.CharField('N° Guía', max_length=30)
    fecha_emision  = models.DateField('Fecha emisión')
    fecha_traslado = models.DateField('Fecha traslado')
    motivo         = models.CharField('Motivo', max_length=20, choices=MOTIVOS_TRASLADO, default='TRASLADO_OBRA')
    origen         = models.CharField('Punto de partida', max_length=300)
    destino        = models.CharField('Punto de llegada', max_length=300)
    transportista  = models.ForeignKey(Transportista, null=True, blank=True, on_delete=models.SET_NULL, related_name='guias')
    placa          = models.CharField('Placa vehículo', max_length=15, blank=True)
    conductor      = models.CharField('Conductor', max_length=100, blank=True)
    licencia       = models.CharField('N° Licencia', max_length=20, blank=True)
    peso_kg        = models.DecimalField('Peso bruto (kg)', max_digits=10, decimal_places=2, null=True, blank=True)
    observaciones  = models.TextField(blank=True)
    estado         = models.CharField(max_length=20, choices=ESTADOS_GUIA, default='PENDIENTE')
    creado_en      = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering            = ['-fecha_emision', '-pk']
        verbose_name        = 'Guía de Remisión'
        verbose_name_plural = 'Guías de Remisión'

    def __str__(self):
        return f'Guía {self.numero}'

    @property
    def estado_badge(self):
        return {
            'PENDIENTE':   ('warning',  'bi-clock'),
            'EN_TRANSITO': ('primary',  'bi-truck'),
            'ENTREGADO':   ('success',  'bi-check-circle-fill'),
            'ANULADO':     ('danger',   'bi-x-circle'),
        }.get(self.estado, ('secondary', 'bi-circle'))


class DetalleGuia(models.Model):
    guia        = models.ForeignKey(GuiaRemision, on_delete=models.CASCADE, related_name='detalles')
    descripcion = models.CharField('Descripción', max_length=400)
    unidad      = models.CharField('Unidad', max_length=20, blank=True)
    cantidad    = models.DecimalField('Cantidad', max_digits=12, decimal_places=3, default=Decimal('0'))

    class Meta:
        verbose_name = 'Detalle de Guía'

    def __str__(self):
        return self.descripcion
