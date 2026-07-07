from decimal import Decimal
from django.db import models
from apps.proyectos.models import Proyecto


TIPOS_MAQUINARIA = [
    ('EQUIPO',       'Equipo'),
    ('VEHICULO',     'Vehículo'),
    ('HERRAMIENTA',  'Herramienta'),
    ('OTRO',         'Otro'),
]

TIPOS_EQUIPO = [
    ('CAMIONETA',       'Camioneta'),
    ('TRACTOR',         'Tractor'),
    ('RETROEXCAVADORA', 'Retroexcavadora'),
    ('EXCAVADORA',      'Excavadora'),
    ('CARGADOR',        'Cargador Frontal'),
    ('VOLQUETE',        'Volquete'),
    ('GRUA',            'Grúa'),
    ('COMPACTADORA',    'Compactadora'),
    ('MOTONIVELADORA',  'Motoniveladora'),
    ('BUS',             'Bus / Minibús'),
    ('OTRO',            'Otro'),
]

MODALIDADES_COSTO = [
    ('MENSUAL',   'Mensual'),
    ('SEMANAL',   'Semanal'),
    ('QUINCENAL', 'Quincenal'),
]

MODALIDADES = [
    ('MENSUAL', 'Mensual'),
    ('DIARIO',  'Diario'),
    ('SEMANAL', 'Semanal'),
    ('SECA',    'Maquinaria Seca'),
]


class TipoPersonal(models.Model):
    codigo     = models.CharField(max_length=20, unique=True)
    nombre     = models.CharField(max_length=100)
    costo_hora = models.DecimalField(max_digits=12, decimal_places=4, default=0)
    activo     = models.BooleanField(default=True)

    class Meta:
        verbose_name        = 'Tipo de Personal'
        verbose_name_plural = 'Tipos de Personal'
        ordering            = ['nombre']

    def __str__(self):
        return f'{self.codigo} — {self.nombre}'


class Maquinaria(models.Model):
    codigo     = models.CharField(max_length=30, unique=True)
    nombre     = models.CharField(max_length=200)
    tipo       = models.CharField(max_length=20, choices=TIPOS_MAQUINARIA, default='EQUIPO')
    costo_hora = models.DecimalField(max_digits=12, decimal_places=4, default=0)
    placa      = models.CharField(max_length=20, blank=True)
    activo     = models.BooleanField(default=True)

    class Meta:
        verbose_name        = 'Maquinaria'
        verbose_name_plural = 'Maquinaria'
        ordering            = ['nombre']

    def __str__(self):
        return f'{self.codigo} — {self.nombre}'


class Cuadrilla(models.Model):
    nombre      = models.CharField(max_length=200)
    descripcion = models.TextField(blank=True)
    activo      = models.BooleanField(default=True)

    class Meta:
        verbose_name        = 'Cuadrilla'
        verbose_name_plural = 'Cuadrillas'
        ordering            = ['nombre']

    def __str__(self):
        return self.nombre

    def hh_por_hora(self):
        """Personas-hora por cada hora trabajada (suma de cantidades de integrantes)."""
        return sum((i.cantidad for i in self.integrantes.all()), Decimal('0'))

    def costo_hora(self):
        """Costo total por hora de la cuadrilla completa."""
        return sum(
            (i.cantidad * i.tipo_personal.costo_hora
             for i in self.integrantes.select_related('tipo_personal').all()),
            Decimal('0')
        )


class IntegranteCuadrilla(models.Model):
    cuadrilla      = models.ForeignKey(Cuadrilla, on_delete=models.CASCADE, related_name='integrantes')
    tipo_personal  = models.ForeignKey(TipoPersonal, on_delete=models.CASCADE)
    cantidad       = models.DecimalField(max_digits=6, decimal_places=2, default=1)

    class Meta:
        verbose_name        = 'Integrante de Cuadrilla'
        verbose_name_plural = 'Integrantes de Cuadrilla'
        unique_together     = ['cuadrilla', 'tipo_personal']

    def __str__(self):
        return f'{self.cantidad} × {self.tipo_personal}'

    def costo_parcial_hora(self):
        return self.cantidad * self.tipo_personal.costo_hora


class RegistroDiario(models.Model):
    proyecto     = models.ForeignKey(Proyecto, on_delete=models.CASCADE, related_name='registros_cuadrilla')
    fecha        = models.DateField()
    partida      = models.ForeignKey(
        'presupuesto.Partida', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='registros_cuadrilla'
    )
    cuadrilla    = models.ForeignKey(Cuadrilla, on_delete=models.CASCADE)
    horas        = models.DecimalField(max_digits=6, decimal_places=2, default=8)
    observacion  = models.TextField(blank=True)
    created_at   = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name        = 'Registro Diario de Cuadrilla'
        verbose_name_plural = 'Registros Diarios de Cuadrilla'
        ordering            = ['-fecha', '-created_at']

    def __str__(self):
        return f'{self.fecha} — {self.cuadrilla}'

    def horas_hombre(self):
        return (self.cuadrilla.hh_por_hora() * self.horas).quantize(Decimal('0.01'))

    def costo_mano_obra(self):
        return (self.cuadrilla.costo_hora() * self.horas).quantize(Decimal('0.01'))


class RegistroMaquinaria(models.Model):
    proyecto    = models.ForeignKey(Proyecto, on_delete=models.CASCADE, related_name='registros_maquinaria')
    fecha       = models.DateField()
    partida     = models.ForeignKey(
        'presupuesto.Partida', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='registros_maquinaria'
    )
    maquinaria  = models.ForeignKey(Maquinaria, null=True, blank=True, on_delete=models.SET_NULL)

    # Identificación
    codigo      = models.CharField(max_length=30, blank=True)
    nombre      = models.CharField(max_length=200, blank=True)
    tipo_equipo = models.CharField(max_length=20, choices=TIPOS_EQUIPO, blank=True)
    marca       = models.CharField(max_length=100, blank=True)
    modelo      = models.CharField(max_length=100, blank=True)
    placa       = models.CharField(max_length=20, blank=True)

    # Contrato
    costo            = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    modalidad_costo  = models.CharField(max_length=15, choices=MODALIDADES_COSTO, blank=True)
    modalidad        = models.CharField(max_length=15, choices=MODALIDADES, blank=True)

    # Personal
    propietario = models.CharField(max_length=200, blank=True)
    operador    = models.CharField(max_length=200, blank=True)

    # Actividad
    horas       = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    observacion = models.TextField(blank=True)

    # Fechas de obra
    fecha_llegada  = models.DateField(null=True, blank=True)
    fecha_reinicio = models.DateField(null=True, blank=True)
    fecha_salida   = models.DateField(null=True, blank=True)

    created_at  = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name        = 'Registro de Maquinaria'
        verbose_name_plural = 'Registros de Maquinaria'
        ordering            = ['-fecha', '-created_at']

    def __str__(self):
        return f'{self.fecha} — {self.nombre or (self.maquinaria or "")}'

    def costo_maquinaria(self):
        if self.maquinaria:
            return (self.maquinaria.costo_hora * self.horas).quantize(Decimal('0.01'))
        return Decimal('0.00')
