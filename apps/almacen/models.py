from django.db import models
from apps.proyectos.models import Proyecto
from apps.catalogo.models import Producto, UNIDADES


TIPOS_MATERIAL = [
    ('MATERIAL', 'Material'),
    ('EQUIPO', 'Equipo'),
    ('EPP', 'EPP'),
    ('UTIL', 'Útil'),
    ('HERRAMIENTA', 'Herramienta'),
    ('OTRO', 'Otro'),
]

ESTADOS_REQ = [
    ('PENDIENTE', 'Pendiente'),
    ('APROBADO', 'Aprobado'),
    ('ATENDIDO', 'Atendido'),
    ('PARCIAL', 'Atendido Parcial'),
    ('ANULADO', 'Anulado'),
]

ESTADOS_COT = [
    ('PENDIENTE', 'Pendiente'),
    ('APROBADA', 'Aprobada'),
    ('RECHAZADA', 'Rechazada'),
]


class Requerimiento(models.Model):
    proyecto = models.ForeignKey(Proyecto, on_delete=models.CASCADE, related_name='requerimientos')
    numero = models.CharField(max_length=20)
    fecha = models.DateField()
    tipo = models.CharField(max_length=20, choices=TIPOS_MATERIAL, default='MATERIAL')
    solicitante = models.CharField(max_length=150, blank=True)
    estado = models.CharField(max_length=20, choices=ESTADOS_REQ, default='PENDIENTE')
    observaciones = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Requerimiento'
        verbose_name_plural = 'Requerimientos'
        ordering = ['-fecha', '-numero']
        unique_together = ['proyecto', 'numero']

    def __str__(self):
        return f'REQ-{self.numero} | {self.proyecto.codigo}'


class DetalleRequerimiento(models.Model):
    requerimiento = models.ForeignKey(Requerimiento, on_delete=models.CASCADE, related_name='detalles')
    producto = models.ForeignKey(Producto, on_delete=models.PROTECT)
    cantidad = models.DecimalField(max_digits=15, decimal_places=4)
    unidad = models.CharField(max_length=10, choices=UNIDADES, default='UND')
    observacion = models.CharField(max_length=300, blank=True)

    def __str__(self):
        return f'{self.producto.descripcion} x {self.cantidad}'


class Entrada(models.Model):
    proyecto = models.ForeignKey(Proyecto, on_delete=models.CASCADE, related_name='entradas')
    requerimiento = models.ForeignKey(Requerimiento, null=True, blank=True, on_delete=models.SET_NULL, related_name='entradas')
    serie = models.CharField(max_length=10, default='001')
    numero_guia = models.CharField(max_length=50)
    fecha = models.DateField()
    proveedor = models.CharField(max_length=200, blank=True)
    descripcion = models.CharField(max_length=300, blank=True)
    observaciones = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Entrada'
        verbose_name_plural = 'Entradas'
        ordering = ['-fecha']

    def __str__(self):
        return f'GUIA {self.serie}-{self.numero_guia} | {self.proyecto.codigo}'

    def total(self):
        return sum(d.subtotal() for d in self.detalles.all())


class DetalleEntrada(models.Model):
    entrada = models.ForeignKey(Entrada, on_delete=models.CASCADE, related_name='detalles')
    producto = models.ForeignKey(Producto, on_delete=models.PROTECT)
    cantidad = models.DecimalField(max_digits=15, decimal_places=4)
    precio_unitario = models.DecimalField(max_digits=15, decimal_places=4, default=0)
    unidad = models.CharField(max_length=10, choices=UNIDADES, default='UND')

    def subtotal(self):
        return self.cantidad * self.precio_unitario

    def __str__(self):
        return f'{self.producto.descripcion} x {self.cantidad}'


class Salida(models.Model):
    proyecto = models.ForeignKey(Proyecto, on_delete=models.CASCADE, related_name='salidas')
    numero = models.CharField(max_length=20)
    fecha = models.DateField()
    destino = models.CharField(max_length=200, blank=True)
    responsable = models.CharField(max_length=150, blank=True)
    observaciones = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Salida'
        verbose_name_plural = 'Salidas'
        ordering = ['-fecha']

    def __str__(self):
        return f'SAL-{self.numero} | {self.proyecto.codigo}'

    def total(self):
        return sum(d.subtotal() for d in self.detalles.all())


class DetalleSalida(models.Model):
    salida = models.ForeignKey(Salida, on_delete=models.CASCADE, related_name='detalles')
    producto = models.ForeignKey(Producto, on_delete=models.PROTECT)
    cantidad = models.DecimalField(max_digits=15, decimal_places=4)
    precio_unitario = models.DecimalField(max_digits=15, decimal_places=4, default=0)
    unidad = models.CharField(max_length=10, choices=UNIDADES, default='UND')

    def subtotal(self):
        return self.cantidad * self.precio_unitario

    def __str__(self):
        return f'{self.producto.descripcion} x {self.cantidad}'


class Cotizacion(models.Model):
    proyecto = models.ForeignKey(Proyecto, on_delete=models.CASCADE, related_name='cotizaciones')
    numero = models.CharField(max_length=20)
    fecha = models.DateField()
    proveedor = models.CharField(max_length=200)
    estado = models.CharField(max_length=20, choices=ESTADOS_COT, default='PENDIENTE')
    observaciones = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Cotización'
        verbose_name_plural = 'Cotizaciones'
        ordering = ['-fecha']

    def __str__(self):
        return f'COT-{self.numero} | {self.proveedor}'

    def total(self):
        return sum(d.subtotal() for d in self.detalles.all())


class DetalleCotizacion(models.Model):
    cotizacion = models.ForeignKey(Cotizacion, on_delete=models.CASCADE, related_name='detalles')
    producto = models.ForeignKey(Producto, on_delete=models.PROTECT)
    cantidad = models.DecimalField(max_digits=15, decimal_places=4)
    precio_unitario = models.DecimalField(max_digits=15, decimal_places=4)
    unidad = models.CharField(max_length=10, choices=UNIDADES, default='UND')

    def subtotal(self):
        return self.cantidad * self.precio_unitario

    def __str__(self):
        return f'{self.producto.descripcion} x {self.cantidad}'


ESTADOS_OC = [
    ('BORRADOR',   'Borrador'),
    ('ENVIADA',    'Enviada'),
    ('PARCIAL',    'Recibida Parcial'),
    ('COMPLETADA', 'Completada'),
    ('ANULADA',    'Anulada'),
]


class OrdenCompra(models.Model):
    proyecto      = models.ForeignKey(Proyecto, on_delete=models.CASCADE, related_name='ordenes_compra')
    numero        = models.CharField(max_length=20)
    fecha         = models.DateField()
    proveedor     = models.CharField(max_length=200)
    requerimiento = models.ForeignKey(Requerimiento, null=True, blank=True,
                                      on_delete=models.SET_NULL, related_name='ordenes')
    cotizacion    = models.ForeignKey(Cotizacion, null=True, blank=True,
                                      on_delete=models.SET_NULL, related_name='ordenes')
    estado        = models.CharField(max_length=20, choices=ESTADOS_OC, default='BORRADOR')
    plazo_entrega = models.CharField(max_length=100, blank=True)
    observaciones = models.TextField(blank=True)
    created_at    = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Orden de Compra'
        verbose_name_plural = 'Órdenes de Compra'
        ordering = ['-fecha', '-numero']
        unique_together = ['proyecto', 'numero']

    def __str__(self):
        return f'OC-{self.numero} | {self.proveedor}'

    def total(self):
        return sum(d.subtotal() for d in self.detalles.all())


class DetalleOrdenCompra(models.Model):
    orden          = models.ForeignKey(OrdenCompra, on_delete=models.CASCADE, related_name='detalles')
    producto       = models.ForeignKey(Producto, on_delete=models.PROTECT)
    cantidad       = models.DecimalField(max_digits=15, decimal_places=4)
    precio_unitario = models.DecimalField(max_digits=15, decimal_places=4, default=0)
    unidad         = models.CharField(max_length=10, choices=UNIDADES, default='UND')

    def subtotal(self):
        return self.cantidad * self.precio_unitario

    def __str__(self):
        return f'{self.producto.descripcion} x {self.cantidad}'
