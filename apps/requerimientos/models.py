from django.db import models
from apps.proyectos.models import Proyecto
from apps.presupuesto.models import InsumoPresupuesto


TIPOS_MATERIAL = [
    ('MATERIAL', 'Material'),
    ('EQUIPO', 'Equipo'),
    ('EPP', 'EPP'),
    ('UTIL', 'Útil'),
    ('HERRAMIENTA', 'Herramienta'),
    ('OTRO', 'Otro'),
]

ESTADOS_REQ = [
    ('BORRADOR', 'Borrador'),
    ('ENVIADO', 'Enviado a Logística'),
    ('EN_REVISION', 'En revisión'),
    ('APROBADO', 'Aprobado'),
    ('ATENDIDO', 'Atendido'),
    ('PARCIAL', 'Atendido Parcial'),
    ('ANULADO', 'Anulado'),
]


class Requerimiento(models.Model):
    proyecto = models.ForeignKey(Proyecto, on_delete=models.CASCADE, related_name='requerimientos')
    numero_global = models.CharField(max_length=10, blank=True)
    numero = models.CharField(max_length=20)
    fecha = models.DateField()
    tipo = models.CharField(max_length=20, choices=TIPOS_MATERIAL, default='MATERIAL')
    obra = models.CharField(max_length=200, blank=True)
    solicitante = models.CharField(max_length=150, blank=True)
    cargo_solicitante = models.CharField(max_length=150, blank=True)
    sector_obra = models.CharField(max_length=200, blank=True)
    estado = models.CharField(max_length=20, choices=ESTADOS_REQ, default='BORRADOR')
    observaciones = models.TextField(blank=True)
    aprobacion_vista = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    cotizacion_sistema = models.ForeignKey(
        'almacen.Cotizacion', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='requerimientos'
    )
    cotizacion_pdf = models.FileField(
        upload_to='requerimientos/cotizaciones/', null=True, blank=True
    )

    class Meta:
        verbose_name = 'Requerimiento'
        verbose_name_plural = 'Requerimientos'
        ordering = ['-fecha', '-numero']
        unique_together = ['proyecto', 'numero']

    def __str__(self):
        return f'REQ-{self.numero} | {self.proyecto.codigo}'


class DetalleRequerimiento(models.Model):
    requerimiento = models.ForeignKey(Requerimiento, on_delete=models.CASCADE, related_name='detalles')
    insumo = models.ForeignKey(InsumoPresupuesto, null=True, blank=True, on_delete=models.SET_NULL)
    codigo = models.CharField(max_length=60, blank=True)
    descripcion = models.CharField(max_length=400, blank=True)
    cantidad = models.DecimalField(max_digits=15, decimal_places=4)
    unidad = models.CharField(max_length=20, blank=True)
    cantidad_requerida = models.DecimalField(max_digits=15, decimal_places=4, default=0)
    cantidad_aprobada = models.DecimalField(max_digits=15, decimal_places=4, null=True, blank=True)
    justificacion = models.CharField(max_length=400, blank=True)
    observacion = models.CharField(max_length=300, blank=True)

    def __str__(self):
        return f'{self.descripcion or (self.insumo.descripcion if self.insumo else "—")} x {self.cantidad}'
