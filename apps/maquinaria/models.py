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
    ('COMPRESORA',      'Compresora'),
    ('RODILLO',         'Rodillo'),
    ('ROCK_DRILL',      'Rock Drill'),
    ('GRUA',            'Grúa'),
    ('COMPACTADORA',    'Compactadora'),
    ('MOTONIVELADORA',  'Motoniveladora'),
    ('BUS',             'Bus / Minibús'),
    ('OTRO',            'Otro'),
]

MODALIDADES_COSTO = [
    ('MENSUAL',   'Mensual (tarifa fija)'),
    ('SECA',      'Maquinaria Seca (por hora)'),
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
    # Identificación
    codigo      = models.CharField(max_length=30, unique=True)
    nombre      = models.CharField(max_length=200)
    tipo_equipo = models.CharField('Tipo de equipo', max_length=20, choices=TIPOS_EQUIPO, blank=True)
    marca       = models.CharField('Marca', max_length=100, blank=True)
    modelo      = models.CharField('Modelo', max_length=100, blank=True)
    placa       = models.CharField('Placa', max_length=20, blank=True)

    # Contrato
    costo          = models.DecimalField('Costo', max_digits=14, decimal_places=2, default=0)
    modalidad_costo = models.CharField('Modalidad', max_length=15, choices=MODALIDADES_COSTO, blank=True)
    costo_hora     = models.DecimalField('Costo por hora', max_digits=12, decimal_places=4, default=0)

    # Personal
    propietario_documento    = models.CharField('RUC / DNI', max_length=15, blank=True)
    propietario_razon_social = models.CharField('Razón social', max_length=200, blank=True)
    propietario_celular      = models.CharField('Celular', max_length=20, blank=True)
    propietario_direccion    = models.CharField('Dirección', max_length=300, blank=True)
    operador    = models.CharField('Operador', max_length=200, blank=True)

    # Fechas de obra
    fecha_llegada       = models.DateField('Fecha de llegada', null=True, blank=True)
    fecha_reinicio      = models.DateField('Fecha de reinicio de trabajo', null=True, blank=True)
    fecha_salida_obra   = models.DateField('Fecha de salida de obra', null=True, blank=True)

    activo = models.BooleanField(default=True)

    class Meta:
        verbose_name        = 'Maquinaria'
        verbose_name_plural = 'Maquinaria'
        ordering            = ['codigo']

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


SEXO_CHOICES = [
    ('M', 'Masculino'),
    ('F', 'Femenino'),
]

ESTADO_CIVIL_CHOICES = [
    ('SOLTERO',     'Soltero/a'),
    ('CASADO',      'Casado/a'),
    ('CONVIVIENTE', 'Conviviente'),
    ('DIVORCIADO',  'Divorciado/a'),
    ('VIUDO',       'Viudo/a'),
]

LICENCIA_CATEGORIAS = [
    ('A-I',    'A-I  (Autos particulares)'),
    ('A-IIA',  'A-IIa (Taxi)'),
    ('A-IIB',  'A-IIb (Transporte interurbano)'),
    ('A-IIIA', 'A-IIIa (Transporte interprovincial)'),
    ('A-IIIB', 'A-IIIb (Transporte mercancías pesado)'),
    ('A-IIIC', 'A-IIIc (Carga especial)'),
    ('B-I',    'B-I (Motos lineales)'),
    ('B-IIA',  'B-IIa (Mototaxi)'),
    ('B-IIB',  'B-IIb (Motocarga)'),
    ('B-IIC',  'B-IIc (Motocicleta carga)'),
]

REGIMEN_PENSION_CHOICES = [
    ('NINGUNO',  'No afiliado'),
    ('ONP',      'ONP'),
    ('INTEGRA',  'AFP Integra'),
    ('PRIMA',    'AFP Prima'),
    ('HABITAT',  'AFP Habitat'),
    ('PROFUTURO','AFP Profuturo'),
]


class Trabajador(models.Model):
    proyecto     = models.ForeignKey(Proyecto, on_delete=models.CASCADE, related_name='trabajadores')

    # — Datos personales —
    nombres          = models.CharField(max_length=150)
    apellidos        = models.CharField(max_length=150)
    dni              = models.CharField('DNI', max_length=15, blank=True)
    fecha_nacimiento = models.DateField('Fecha de nacimiento', null=True, blank=True)
    sexo             = models.CharField('Sexo', max_length=1, choices=SEXO_CHOICES, blank=True)
    estado_civil     = models.CharField('Estado civil', max_length=15, choices=ESTADO_CIVIL_CHOICES, blank=True)
    lugar_nacimiento = models.CharField('Lugar de nacimiento', max_length=150, blank=True)

    # — Contacto —
    telefono     = models.CharField('Teléfono', max_length=20, blank=True)
    telefono2    = models.CharField('Teléfono alternativo', max_length=20, blank=True)
    email        = models.EmailField('Correo electrónico', blank=True)
    direccion    = models.CharField('Dirección', max_length=300, blank=True)
    distrito     = models.CharField('Distrito', max_length=80, blank=True)
    provincia    = models.CharField('Provincia', max_length=80, blank=True)
    departamento = models.CharField('Departamento', max_length=80, blank=True)

    # — Contacto de emergencia —
    emergencia_nombre     = models.CharField('Contacto de emergencia', max_length=150, blank=True)
    emergencia_parentesco = models.CharField('Parentesco', max_length=50, blank=True)
    emergencia_telefono   = models.CharField('Teléfono de emergencia', max_length=20, blank=True)

    # — Laboral —
    tipo_personal = models.ForeignKey(
        TipoPersonal, null=True, blank=True,
        on_delete=models.SET_NULL, related_name='trabajadores',
        verbose_name='Cargo',
    )
    fecha_ingreso           = models.DateField('Fecha de ingreso a obra', null=True, blank=True)
    anios_experiencia       = models.PositiveIntegerField('Años de experiencia', null=True, blank=True)
    experiencia_descripcion = models.TextField('Experiencia laboral (empresas, obras, cargos)', blank=True)

    # — Habilidades y oficios —
    habilidades = models.TextField(
        'Habilidades y oficios',
        blank=True,
        help_text='Albañilería, carpintería, encofrado, fierrería, soldadura, electricidad, gasfitería, etc.',
    )

    # — Licencia de conducir —
    tiene_licencia      = models.BooleanField('¿Tiene licencia de conducir?', default=False)
    licencia_categoria  = models.CharField('Categoría', max_length=10, choices=LICENCIA_CATEGORIAS, blank=True)
    licencia_numero     = models.CharField('N° de licencia', max_length=30, blank=True)
    licencia_vencimiento = models.DateField('Vencimiento de licencia', null=True, blank=True)

    # — Maquinaria pesada —
    opera_maquinaria_pesada = models.BooleanField('¿Opera maquinaria pesada?', default=False)
    maquinas_opera          = models.TextField(
        'Maquinaria que opera', blank=True,
        help_text='Ej: retroexcavadora, cargador frontal, volquete, rodillo, grúa.',
    )

    # — Seguridad social / Pagos —
    regimen_pension = models.CharField('Régimen de pensiones', max_length=15, choices=REGIMEN_PENSION_CHOICES, blank=True)
    cuspp           = models.CharField('CUSPP', max_length=20, blank=True)
    tiene_essalud   = models.BooleanField('EsSalud', default=False)
    tiene_sctr      = models.BooleanField('SCTR vigente', default=False)
    banco           = models.CharField('Banco', max_length=50, blank=True)
    cuenta_cci      = models.CharField('CCI (20 dígitos)', max_length=25, blank=True)

    # — Archivos —
    foto = models.ImageField('Foto', upload_to='trabajadores/fotos/', blank=True)
    cv   = models.FileField('CV', upload_to='trabajadores/cv/', blank=True)

    # — Observaciones —
    observaciones = models.TextField('Observaciones', blank=True)

    # — Control —
    activo     = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name        = 'Trabajador'
        verbose_name_plural = 'Trabajadores'
        ordering            = ['apellidos', 'nombres']

    def __str__(self):
        return f'{self.apellidos}, {self.nombres}'

    def nombre_completo(self):
        return f'{self.nombres} {self.apellidos}'.strip()


class DocumentoTrabajador(models.Model):
    trabajador   = models.ForeignKey(Trabajador, on_delete=models.CASCADE, related_name='documentos')
    nombre       = models.CharField('Nombre del documento', max_length=150)
    archivo      = models.FileField('Archivo', upload_to='trabajadores/documentos/')
    fecha_subida = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name        = 'Documento de Trabajador'
        verbose_name_plural = 'Documentos de Trabajador'
        ordering            = ['-fecha_subida']

    def __str__(self):
        return f'{self.nombre} — {self.trabajador}'


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


class Liquidacion(models.Model):
    """Agrupa los partes diarios de una máquina en un período mensual."""
    ESTADOS = [('ABIERTA', 'Abierta'), ('CERRADA', 'Cerrada')]

    proyecto   = models.ForeignKey(Proyecto, on_delete=models.CASCADE, related_name='liquidaciones_maq')
    maquinaria = models.ForeignKey(Maquinaria, on_delete=models.CASCADE, related_name='liquidaciones')
    numero     = models.PositiveIntegerField()
    periodo    = models.DateField()
    estado     = models.CharField(max_length=10, choices=ESTADOS, default='ABIERTA')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name        = 'Liquidación'
        verbose_name_plural = 'Liquidaciones'
        ordering            = ['-periodo', 'maquinaria__codigo']
        unique_together     = [['maquinaria', 'numero']]

    def __str__(self):
        return f'LIQ-{self.numero:03d} — {self.maquinaria.codigo} ({self.periodo_display()})'

    def periodo_display(self):
        meses = ['Enero','Febrero','Marzo','Abril','Mayo','Junio',
                 'Julio','Agosto','Septiembre','Octubre','Noviembre','Diciembre']
        return f'{meses[self.periodo.month - 1]} {self.periodo.year}'

    def total_horas(self):
        from django.db.models import Sum
        return self.partes.aggregate(t=Sum('horas'))['t'] or Decimal('0')

    def total_combustible(self):
        from django.db.models import Sum
        return self.partes.filter(combustible__isnull=False).aggregate(t=Sum('combustible'))['t'] or Decimal('0')

    def monto_a_pagar(self):
        maq = self.maquinaria
        if maq.modalidad_costo == 'MENSUAL':
            return Decimal(str(maq.costo))
        return (self.total_horas() * maq.costo_hora).quantize(Decimal('0.01'))


class RegistroMaquinaria(models.Model):
    proyecto    = models.ForeignKey(Proyecto, on_delete=models.CASCADE, related_name='registros_maquinaria')
    fecha       = models.DateField()
    partida     = models.ForeignKey(
        'presupuesto.Partida', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='registros_maquinaria'
    )
    insumo      = models.ForeignKey(
        'presupuesto.InsumoPresupuesto', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='registros_maquinaria',
        verbose_name='Insumo presupuesto',
    )
    maquinaria  = models.ForeignKey(Maquinaria, null=True, blank=True, on_delete=models.SET_NULL)
    liquidacion = models.ForeignKey(
        Liquidacion, null=True, blank=True,
        on_delete=models.SET_NULL, related_name='partes',
        verbose_name='Liquidación',
    )

    # Parte diario
    numero_parte = models.PositiveIntegerField('N° de parte', null=True, blank=True)
    combustible  = models.DecimalField('Combustible (gal)', max_digits=8, decimal_places=2, null=True, blank=True)

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

    # Turno — horómetro (lectura del contador de horas de la máquina)
    hora_entrada = models.DecimalField('Horómetro entrada', max_digits=10, decimal_places=2, null=True, blank=True)
    hora_salida  = models.DecimalField('Horómetro salida',  max_digits=10, decimal_places=2, null=True, blank=True)

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

    def save(self, *args, **kwargs):
        if self.hora_entrada is not None and self.hora_salida is not None:
            diff = self.hora_salida - self.hora_entrada
            if diff > 0:
                self.horas = diff.quantize(Decimal('0.01'))
        if not self.numero_parte and self.maquinaria_id:
            qs = RegistroMaquinaria.objects.filter(maquinaria_id=self.maquinaria_id)
            if self.pk:
                qs = qs.exclude(pk=self.pk)
            ultimo = qs.order_by('-numero_parte').values_list('numero_parte', flat=True).first() or 0
            self.numero_parte = ultimo + 1
        super().save(*args, **kwargs)

    def costo_maquinaria(self):
        if self.maquinaria:
            return (self.maquinaria.costo_hora * self.horas).quantize(Decimal('0.01'))
        return Decimal('0.00')
