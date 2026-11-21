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
    ('SOLICITADO', 'Solicitado por Almacén'),
    ('ENVIADO', 'Enviado a Logística'),
    ('EN_REVISION', 'En revisión'),
    ('APROBADO', 'Aprobado'),
    ('COTIZADO', 'Cotizado'),
    ('ATENDIDO', 'Atendido'),
    ('PARCIAL', 'Atendido Parcial'),
    ('ANULADO', 'Anulado'),
]

# Origen del requerimiento. El Jefe de Obra y el Almacenero comparten modelo
# porque todo el flujo downstream (aprobación, cotización, guía) es idéntico,
# pero cada uno tiene su propio correlativo para que no colisionen y para que
# el Almacenero vea "Requerimientos de Almacén" en su UI sin tocar la del JO.
ORIGEN_REQ = [
    ('OBRA',    'Jefe de Obra'),
    ('ALMACEN', 'Almacén'),
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
    # Usuario que creó el requerimiento (Almacenero, Admin de Obra, etc.).
    # Usado para filtrar "Mis solicitudes" en el dashboard del Almacenero.
    created_by = models.ForeignKey(
        'auth.User', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='requerimientos_creados',
    )
    cotizacion_sistema = models.ForeignKey(
        'almacen.Cotizacion', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='requerimientos'
    )
    cotizacion_pdf = models.FileField(
        upload_to='requerimientos/cotizaciones/', null=True, blank=True
    )
    # Marca "Ajuste": solicitud que excede el stock presupuestado (adicional).
    # El impacto formal en el presupuesto (crear Modificacion / aumentar cantidad_total)
    # NO está implementado — ver REGLAS_NEGOCIO.md §14 (TODO).
    es_ajuste = models.BooleanField(default=False)
    # Origen: discrimina entre REQ del Jefe de Obra (REQ001, REQ002, ...) y REQ
    # del Almacenero (REQA001, REQA002, ...) — correlativos independientes por
    # proyecto para que puedan existir REQ001 y REQA001 sin colisión.
    origen = models.CharField(max_length=10, choices=ORIGEN_REQ, default='OBRA')

    class Meta:
        verbose_name = 'Requerimiento'
        verbose_name_plural = 'Requerimientos'
        ordering = ['-fecha', '-numero']
        unique_together = ['proyecto', 'numero']

    def __str__(self):
        return f'REQ{self.numero} | {self.proyecto.codigo}'


class DetalleRequerimiento(models.Model):
    requerimiento = models.ForeignKey(Requerimiento, on_delete=models.CASCADE, related_name='detalles')
    insumo = models.ForeignKey(InsumoPresupuesto, null=True, blank=True, on_delete=models.SET_NULL)
    codigo = models.CharField(max_length=60, blank=True)
    descripcion = models.CharField(max_length=400, blank=True)
    cantidad = models.DecimalField(max_digits=15, decimal_places=4)
    unidad = models.CharField(max_length=20, blank=True)
    cantidad_requerida = models.DecimalField(max_digits=15, decimal_places=4, default=0)
    cantidad_aprobada = models.DecimalField(max_digits=15, decimal_places=4, null=True, blank=True)
    insumo_sustituto = models.ForeignKey(
        InsumoPresupuesto, null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='detalles_sustituto',
        verbose_name='Insumo sustituto',
    )
    justificacion = models.CharField(max_length=400, blank=True)
    observacion = models.CharField(max_length=300, blank=True)

    def __str__(self):
        return f'{self.descripcion or (self.insumo.descripcion if self.insumo else "—")} x {self.cantidad}'


class HistorialRevisionReq(models.Model):
    ACCIONES = [
        ('ELIMINAR',   'Ítem eliminado'),
        ('AGREGAR',    'Ítem agregado'),
        ('SUSTITUIR',  'Insumo sustituido'),
        ('ANULAR',     'Requerimiento anulado'),
        ('RECUPERAR',  'Requerimiento recuperado'),
    ]
    requerimiento = models.ForeignKey(Requerimiento, on_delete=models.CASCADE, related_name='historial_revision')
    accion        = models.CharField(max_length=10, choices=ACCIONES)
    insumo        = models.ForeignKey(InsumoPresupuesto, null=True, blank=True, on_delete=models.SET_NULL)
    insumo_original = models.ForeignKey(
        InsumoPresupuesto, null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='historial_como_original',
        verbose_name='Insumo original (para sustituciones)',
    )
    descripcion   = models.CharField(max_length=400)
    unidad        = models.CharField(max_length=20, blank=True)
    cantidad      = models.DecimalField(max_digits=15, decimal_places=4)
    justificacion = models.TextField(blank=True)
    usuario       = models.ForeignKey('auth.User', null=True, on_delete=models.SET_NULL)
    fecha         = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering            = ['-fecha']
        verbose_name        = 'Historial de revisión'
        verbose_name_plural = 'Historial de revisiones'
