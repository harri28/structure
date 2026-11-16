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


class Proveedor(models.Model):
    """Catálogo global de proveedores de mercadería."""
    ruc              = models.CharField('RUC / DNI', max_length=11)
    razon_social     = models.CharField('Razón Social', max_length=200)
    nombre_comercial = models.CharField('Nombre Comercial', max_length=200, blank=True)
    telefono         = models.CharField('Teléfono', max_length=50, blank=True)
    email            = models.EmailField('E-mail', blank=True)
    persona_contacto = models.CharField('Persona de Contacto', max_length=150, blank=True)
    direccion        = models.CharField('Dirección', max_length=300, blank=True)
    referencia       = models.CharField('Referencia', max_length=300, blank=True)
    # Datos SUNAT (se autocompletan al consultar; editables si hay que corregir)
    estado_sunat             = models.CharField('Estado SUNAT', max_length=40, blank=True)
    condicion_sunat          = models.CharField('Condición SUNAT', max_length=40, blank=True)
    tipo_contribuyente       = models.CharField('Tipo de Contribuyente', max_length=100, blank=True)
    fecha_inicio_actividades = models.CharField('Fecha Inicio Actividades', max_length=20, blank=True)
    activo           = models.BooleanField(default=True)
    created_at       = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering            = ['razon_social']
        verbose_name        = 'Proveedor'
        verbose_name_plural = 'Proveedores'

    def __str__(self):
        return self.razon_social


class GuiaRemision(models.Model):
    proyecto       = models.ForeignKey('proyectos.Proyecto', on_delete=models.CASCADE, related_name='guias')
    numero         = models.CharField('N° Guía', max_length=30)
    fecha_emision  = models.DateField('Fecha emisión')
    fecha_traslado = models.DateField('Fecha traslado')
    motivo         = models.CharField('Motivo', max_length=20, choices=MOTIVOS_TRASLADO, default='TRASLADO_OBRA')
    motivo_otro    = models.CharField('Otro motivo', max_length=200, blank=True)
    origen         = models.CharField('Punto de partida', max_length=300)
    destino        = models.CharField('Punto de llegada', max_length=300)
    transportista  = models.ForeignKey(Transportista, null=True, blank=True, on_delete=models.SET_NULL, related_name='guias')
    placa          = models.CharField('Placa vehículo', max_length=15, blank=True)
    conductor      = models.CharField('Conductor', max_length=100, blank=True)
    licencia       = models.CharField('N° Licencia', max_length=20, blank=True)
    peso_kg        = models.DecimalField('Peso bruto (kg)', max_digits=10, decimal_places=2, null=True, blank=True)
    observaciones  = models.TextField(blank=True)
    estado         = models.CharField(max_length=20, choices=ESTADOS_GUIA, default='PENDIENTE')
    requerimiento  = models.ForeignKey(
        'requerimientos.Requerimiento',
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='guias_remision',
    )
    # Cotizaciones aprobadas cuyos ítems viajan en esta guía. LEGACY — el flujo
    # nuevo usa `ocs` (Órdenes de Compra). Se conserva para no romper guías ya
    # creadas con el flujo anterior.
    cotizaciones   = models.ManyToManyField(
        'almacen.Cotizacion',
        blank=True,
        related_name='guias_remision',
    )
    # Órdenes de Compra cuyos ítems viajan en esta guía. Una OC solo puede estar
    # en una guía activa (no anulada): evita descontar el stock dos veces.
    ocs            = models.ManyToManyField(
        'logistica.OrdenCompraLog',
        blank=True,
        related_name='guias_remision',
    )
    # Marca "sin ver" del Almacén: cuando Logística despacha, arranca en False.
    # Se pasa a True cuando el Almacenero abre el detalle en Almacén → Guías.
    # Usado para resaltar en verde suave las guías nuevas en la lista.
    vista_por_almacen = models.BooleanField(default=False)
    creado_en      = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering            = ['-fecha_emision', '-pk']
        verbose_name        = 'Guía de Remisión'
        verbose_name_plural = 'Guías de Remisión'

    def __str__(self):
        return f'Guía {self.numero}'

    @property
    def motivo_texto(self):
        """Motivo a mostrar: el escrito a mano si es 'Otro', o la etiqueta de la opción."""
        if self.motivo == 'OTRO' and self.motivo_otro:
            return self.motivo_otro
        return self.get_motivo_display()

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


# ── Órdenes de Compra (módulo Compras de Logística) ─────────────────────

TIPOS_PAGO_OC = [
    ('EFECTIVO',      'Efectivo'),
    ('TRANSFERENCIA', 'Transferencia'),
    ('CREDITO',       'Crédito'),
]


class OrdenCompraLog(models.Model):
    """Orden de Compra gestionada desde el módulo Compras de Logística.
    Independiente de almacen.OrdenCompra (ese modelo pertenece a un flujo
    legacy)."""
    proyecto         = models.ForeignKey('proyectos.Proyecto', on_delete=models.CASCADE, related_name='ordenes_compra_log')
    numero           = models.CharField('N° Orden', max_length=30)
    proveedor        = models.ForeignKey(Proveedor, null=True, blank=True, on_delete=models.SET_NULL, related_name='ordenes_compra')
    fecha_entrega    = models.DateField('Fecha de entrega esperada')
    tipo_pago        = models.CharField('Tipo de pago', max_length=20, choices=TIPOS_PAGO_OC, default='EFECTIVO')
    numero_factura   = models.CharField('N° de factura', max_length=50, blank=True)
    costo_envio      = models.DecimalField('Costo de envío', max_digits=12, decimal_places=2, default=Decimal('0'))
    observaciones    = models.TextField(blank=True)
    created_by       = models.ForeignKey('auth.User', null=True, blank=True, on_delete=models.SET_NULL, related_name='ordenes_compra_creadas')
    created_at       = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name        = 'Orden de Compra'
        verbose_name_plural = 'Órdenes de Compra'
        ordering            = ['-created_at']
        unique_together     = [('proyecto', 'numero')]

    def __str__(self):
        return self.numero

    def subtotal_items(self):
        return sum((d.subtotal() for d in self.detalles.all()), Decimal('0'))

    def total(self):
        return self.subtotal_items() + (self.costo_envio or Decimal('0'))


class DetalleOrdenCompraLog(models.Model):
    orden           = models.ForeignKey(OrdenCompraLog, on_delete=models.CASCADE, related_name='detalles')
    insumo          = models.ForeignKey('presupuesto.InsumoPresupuesto', null=True, blank=True, on_delete=models.SET_NULL, related_name='en_ordenes_compra')
    descripcion     = models.CharField(max_length=400)
    unidad          = models.CharField(max_length=20, blank=True)
    cantidad        = models.DecimalField(max_digits=12, decimal_places=3, default=Decimal('0'))
    precio_unitario = models.DecimalField(max_digits=12, decimal_places=4, default=Decimal('0'))

    class Meta:
        ordering = ['id']

    def subtotal(self):
        return (self.cantidad or Decimal('0')) * (self.precio_unitario or Decimal('0'))

    def __str__(self):
        return f'{self.descripcion} x {self.cantidad}'
