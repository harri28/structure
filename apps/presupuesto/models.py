from decimal import Decimal
from django.db import models
from apps.proyectos.models import Proyecto


TIPOS_RECURSO = [
    ('MATERIAL', 'Material'),
    ('MANO_OBRA', 'Mano de Obra'),
    ('EQUIPO', 'Equipo/Maquinaria'),
    ('SUBCONTRATO', 'Subcontrato'),
    ('OTRO', 'Otro'),
]

TIPOS_MODIFICACION = [
    ('ADICIONAL', 'Adicional de Obra'),
    ('DEDUCTIVO', 'Deductivo de Obra'),
    ('VINCULANTE', 'Adicional con Deductivo Vinculante'),
]

ESTADOS_MODIFICACION = [
    ('PENDIENTE', 'Pendiente de Aprobación'),
    ('APROBADO', 'Aprobado'),
    ('EJECUTADO', 'Ejecutado'),
    ('RECHAZADO', 'Rechazado'),
]


class Presupuesto(models.Model):
    proyecto = models.OneToOneField(
        Proyecto, on_delete=models.CASCADE, related_name='presupuesto'
    )
    nombre = models.CharField(max_length=200, default='Presupuesto Contractual')
    archivo_origen = models.CharField(max_length=300, blank=True)
    fecha_importacion = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    gastos_generales_pct = models.DecimalField(
        max_digits=6, decimal_places=2, default=Decimal('0'),
        verbose_name='Gastos Generales (%)'
    )
    utilidad_pct = models.DecimalField(
        max_digits=6, decimal_places=2, default=Decimal('0'),
        verbose_name='Utilidad (%)'
    )
    igv_pct = models.DecimalField(
        max_digits=6, decimal_places=2, default=Decimal('18'),
        verbose_name='IGV (%)'
    )
    supervision_pct = models.DecimalField(
        max_digits=6, decimal_places=2, default=Decimal('0'),
        verbose_name='Supervisión (% sobre Costo Total de Obra)'
    )

    class Meta:
        verbose_name = 'Presupuesto'
        verbose_name_plural = 'Presupuestos'

    def __str__(self):
        return f'{self.proyecto.codigo} — {self.nombre}'

    def costo_directo(self):
        if hasattr(self, '_cd_cache'):
            return self._cd_cache
        from django.db.models import Sum, F, DecimalField as DField
        result = (
            self.partidas
            .filter(hijos__isnull=True)
            .aggregate(cd=Sum(
                F('cantidad') * F('precio_unitario'),
                output_field=DField(max_digits=20, decimal_places=4),
            ))['cd'] or Decimal('0')
        )
        self._cd_cache = result.quantize(Decimal('0.01'))
        return self._cd_cache

    def total(self):
        return self.costo_directo()

    def gastos_generales(self):
        return (self.costo_directo() * self.gastos_generales_pct / Decimal('100')).quantize(Decimal('0.01'))

    def utilidad(self):
        return (self.costo_directo() * self.utilidad_pct / Decimal('100')).quantize(Decimal('0.01'))

    def sub_total(self):
        return self.costo_directo() + self.gastos_generales() + self.utilidad()

    def igv(self):
        return (self.sub_total() * self.igv_pct / Decimal('100')).quantize(Decimal('0.01'))

    def costo_total_obra(self):
        return self.sub_total() + self.igv()

    def supervision(self):
        return (self.costo_total_obra() * self.supervision_pct / Decimal('100')).quantize(Decimal('0.01'))

    def total_presupuesto(self):
        return self.costo_total_obra() + self.supervision()

    def monto_vigente(self):
        mods = self.proyecto.modificaciones.filter(estado='APROBADO')
        adicionales = sum(m.total_adicional() for m in mods)
        deductivos = sum(m.total_deductivo() for m in mods)
        return self.total() + adicionales - deductivos


class Partida(models.Model):
    presupuesto = models.ForeignKey(Presupuesto, on_delete=models.CASCADE, related_name='partidas')
    padre = models.ForeignKey('self', null=True, blank=True, on_delete=models.CASCADE, related_name='hijos')
    codigo = models.CharField(max_length=50)
    nombre = models.CharField(max_length=500)
    nivel = models.PositiveSmallIntegerField(default=1)
    orden = models.PositiveIntegerField(default=0)
    unidad = models.CharField(max_length=20, blank=True)
    cantidad = models.DecimalField(max_digits=15, decimal_places=4, default=0)
    precio_unitario = models.DecimalField(max_digits=15, decimal_places=4, default=0)
    parcial = models.DecimalField(
        max_digits=15, decimal_places=2, null=True, blank=True, default=None,
        verbose_name='Total calculado'
    )

    class Meta:
        verbose_name = 'Partida'
        verbose_name_plural = 'Partidas'
        ordering = ['orden']

    def __str__(self):
        return f'{self.codigo} - {self.nombre}'

    def es_hoja(self):
        return not self.hijos.all()

    def total(self):
        if self.parcial is not None:
            return self.parcial
        hijos = list(self.hijos.all())
        if not hijos:
            return self.cantidad * self.precio_unitario
        return sum(h.total() for h in hijos)


class RecursoPartida(models.Model):
    partida = models.ForeignKey(Partida, on_delete=models.CASCADE, related_name='recursos')
    tipo = models.CharField(max_length=20, choices=TIPOS_RECURSO, default='MATERIAL')
    codigo = models.CharField(max_length=50, blank=True)
    descripcion = models.CharField(max_length=400)
    unidad = models.CharField(max_length=20, blank=True)
    cantidad = models.DecimalField(max_digits=15, decimal_places=4, default=0)
    precio_unitario = models.DecimalField(max_digits=15, decimal_places=4, default=0)

    class Meta:
        verbose_name = 'Recurso de Partida'
        verbose_name_plural = 'Recursos de Partida'

    def __str__(self):
        return self.descripcion

    def total(self):
        return self.cantidad * self.precio_unitario


class InsumoPresupuesto(models.Model):
    presupuesto = models.ForeignKey(Presupuesto, on_delete=models.CASCADE, related_name='insumos')
    tipo = models.CharField(max_length=20, choices=TIPOS_RECURSO, default='MATERIAL')
    codigo = models.CharField(max_length=60, blank=True)
    descripcion = models.CharField(max_length=400)
    unidad = models.CharField(max_length=20, blank=True)
    cantidad = models.DecimalField(max_digits=18, decimal_places=4, default=0)
    costo_unitario = models.DecimalField(max_digits=15, decimal_places=4, default=0)
    total = models.DecimalField(max_digits=15, decimal_places=2, default=0)

    class Meta:
        verbose_name = 'Insumo del Presupuesto'
        verbose_name_plural = 'Insumos del Presupuesto'
        ordering = ['tipo', 'descripcion']

    def __str__(self):
        return f'{self.codigo} - {self.descripcion}'


class Modificacion(models.Model):
    proyecto = models.ForeignKey(Proyecto, on_delete=models.CASCADE, related_name='modificaciones')
    tipo = models.CharField(max_length=20, choices=TIPOS_MODIFICACION)
    numero = models.PositiveIntegerField()
    nombre = models.CharField(max_length=300)
    estado = models.CharField(max_length=20, choices=ESTADOS_MODIFICACION, default='PENDIENTE')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Modificación'
        verbose_name_plural = 'Modificaciones'
        unique_together = ['proyecto', 'tipo', 'numero']
        ordering = ['tipo', 'numero']

    def __str__(self):
        return f'{self.get_tipo_display()} N°{self.numero} — {self.nombre}'

    def total_adicional(self):
        return sum(p.subtotal() for p in self.partidas.filter(subtipo='ADICIONAL'))

    def total_deductivo(self):
        return sum(p.subtotal() for p in self.partidas.filter(subtipo='DEDUCTIVO'))

    def total_neto(self):
        return self.total_adicional() - self.total_deductivo()


class PartidaModificacion(models.Model):
    SUBTIPOS = [
        ('ADICIONAL', 'Adicional'),
        ('DEDUCTIVO', 'Deductivo'),
    ]
    modificacion = models.ForeignKey(Modificacion, on_delete=models.CASCADE, related_name='partidas')
    subtipo = models.CharField(max_length=20, choices=SUBTIPOS, default='ADICIONAL')
    partida_origen = models.ForeignKey(
        Partida, null=True, blank=True, on_delete=models.SET_NULL,
        related_name='en_modificaciones'
    )
    codigo = models.CharField(max_length=50, blank=True)
    nombre = models.CharField(max_length=500)
    unidad = models.CharField(max_length=20, blank=True)
    cantidad = models.DecimalField(max_digits=15, decimal_places=4, default=0)
    precio_unitario = models.DecimalField(max_digits=15, decimal_places=4, default=0)
    orden = models.PositiveIntegerField(default=0)

    class Meta:
        verbose_name = 'Partida de Modificación'
        verbose_name_plural = 'Partidas de Modificación'
        ordering = ['subtipo', 'orden']

    def subtotal(self):
        return self.cantidad * self.precio_unitario

    def __str__(self):
        return f'[{self.subtipo}] {self.codigo} - {self.nombre}'
