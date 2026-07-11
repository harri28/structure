from django.db import models
from django.contrib.auth.models import User


class ConfigEmpresa(models.Model):
    razon_social = models.CharField('Razón Social', max_length=200)
    ruc          = models.CharField('RUC', max_length=11, blank=True)
    direccion    = models.CharField('Dirección', max_length=300, blank=True)
    telefono     = models.CharField('Teléfono', max_length=30, blank=True)
    email        = models.EmailField('E-mail', blank=True)
    web          = models.URLField('Sitio web', blank=True)
    moneda       = models.CharField('Moneda', max_length=10, default='S/.')
    igv          = models.DecimalField('IGV (%)', max_digits=5, decimal_places=2, default=18.00)
    logo         = models.ImageField('Logo', upload_to='empresa/', blank=True)
    updated_at   = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Configuración de Empresa'

    def __str__(self):
        return self.razon_social

    @classmethod
    def get(cls):
        obj, _ = cls.objects.get_or_create(
            pk=1,
            defaults={'razon_social': 'S&S Consultores y Ejecutores E.I.R.L.'}
        )
        return obj


class ConfigSunat(models.Model):
    REGIMENES = [
        ('RG',  'Régimen General'),
        ('RER', 'Régimen Especial de Renta'),
        ('RUS', 'Nuevo RUS'),
        ('MYPE', 'Régimen MYPE Tributario'),
    ]
    regimen_tributario   = models.CharField('Régimen Tributario', max_length=10, choices=REGIMENES, blank=True)
    usuario_sol          = models.CharField('Usuario SOL',        max_length=100, blank=True)
    clave_sol            = models.CharField('Clave SOL',          max_length=100, blank=True)
    tipo_comprobante     = models.CharField('Tipo de Comprobante por defecto', max_length=20, blank=True)
    serie_factura        = models.CharField('Serie Factura',      max_length=10,  blank=True)
    serie_boleta         = models.CharField('Serie Boleta',       max_length=10,  blank=True)
    numero_correlativo   = models.CharField('N° Correlativo',     max_length=20,  blank=True)
    ose                  = models.CharField('OSE / PSE',          max_length=100, blank=True)
    updated_at           = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Configuración SUNAT'

    @classmethod
    def get(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj


# ── Roles y Permisos ──────────────────────────────────────────────

GRUPOS_PERMISOS = [
    ('Proyectos', [
        ('puede_ver_dashboard',      'Ver dashboard general del proyecto'),
        ('puede_crear_proyectos',    'Crear y editar proyectos'),
        ('puede_eliminar_proyectos', 'Eliminar proyectos'),
    ]),
    ('Presupuesto', [
        ('puede_ver_presupuesto',    'Ver presupuesto y partidas'),
        ('puede_editar_presupuesto', 'Importar y editar presupuesto'),
    ]),
    ('Almacén', [
        ('puede_ver_almacen',            'Ver almacén, stock y kardex'),
        ('puede_crear_requerimientos',   'Crear requerimientos'),
        ('puede_aprobar_requerimientos', 'Aprobar y anular requerimientos'),
        ('puede_gestionar_entradas',     'Registrar entradas de material'),
        ('puede_gestionar_salidas',      'Registrar salidas de material'),
        ('puede_gestionar_cotizaciones', 'Crear y gestionar cotizaciones'),
        ('puede_gestionar_oc',           'Crear y gestionar órdenes de compra'),
    ]),
    ('Catálogo', [
        ('puede_editar_catalogo', 'Crear y editar productos del catálogo'),
    ]),
    ('Maquinaria y Cuadrilla', [
        ('puede_ver_maquinaria',      'Ver registros de maquinaria y cuadrilla'),
        ('puede_gestionar_maquinaria', 'Crear y editar registros de maquinaria y cuadrilla'),
    ]),
    ('Logística', [
        ('puede_ver_logistica',             'Ver el módulo de Logística'),
        ('puede_revisar_reqs_log',          'Revisar y aprobar requerimientos recibidos'),
        ('puede_gestionar_inventarios_log', 'Gestionar inventarios'),
        ('puede_gestionar_almacen_log',     'Gestionar almacén de Logística'),
        ('puede_gestionar_ctrl_maq_log',    'Control de maquinaria y equipos'),
        ('puede_gestionar_abastecimiento',  'Gestionar abastecimiento'),
        ('puede_gestionar_cotizaciones_log','Gestionar cotizaciones en Logística'),
        ('puede_gestionar_logistica',       'Crear y gestionar guías de remisión'),
    ]),
    ('Administración', [
        ('puede_administrar_usuarios', 'Gestionar usuarios del sistema'),
        ('puede_administrar_roles',    'Gestionar roles y permisos'),
        ('puede_configurar_empresa',   'Configurar datos de la empresa'),
    ]),
    ('Especiales', [
        ('acceso_todos_proyectos', 'Ver todos los proyectos sin ser miembro'),
        ('es_superadmin',          'Superadmin — acceso total al sistema'),
    ]),
]

TODOS_LOS_PERMISOS = [campo for _, items in GRUPOS_PERMISOS for campo, _ in items]


class Rol(models.Model):
    nombre      = models.CharField(max_length=100, unique=True)
    descripcion = models.TextField(blank=True)

    # Proyectos
    puede_ver_dashboard      = models.BooleanField(default=True)
    puede_crear_proyectos    = models.BooleanField(default=False)
    puede_eliminar_proyectos = models.BooleanField(default=False)

    # Presupuesto
    puede_ver_presupuesto    = models.BooleanField(default=False)
    puede_editar_presupuesto = models.BooleanField(default=False)

    # Almacén
    puede_ver_almacen            = models.BooleanField(default=False)
    puede_crear_requerimientos   = models.BooleanField(default=False)
    puede_aprobar_requerimientos = models.BooleanField(default=False)
    puede_gestionar_entradas     = models.BooleanField(default=False)
    puede_gestionar_salidas      = models.BooleanField(default=False)
    puede_gestionar_cotizaciones = models.BooleanField(default=False)
    puede_gestionar_oc           = models.BooleanField(default=False)

    # Catálogo
    puede_editar_catalogo = models.BooleanField(default=False)

    # Maquinaria y Cuadrilla
    puede_ver_maquinaria       = models.BooleanField(default=False)
    puede_gestionar_maquinaria = models.BooleanField(default=False)

    # Logística
    puede_ver_logistica              = models.BooleanField(default=True)
    puede_revisar_reqs_log           = models.BooleanField(default=False)
    puede_gestionar_inventarios_log  = models.BooleanField(default=False)
    puede_gestionar_almacen_log      = models.BooleanField(default=False)
    puede_gestionar_ctrl_maq_log     = models.BooleanField(default=False)
    puede_gestionar_abastecimiento   = models.BooleanField(default=False)
    puede_gestionar_cotizaciones_log = models.BooleanField(default=False)
    puede_gestionar_logistica        = models.BooleanField(default=False)

    # Administración
    puede_administrar_usuarios = models.BooleanField(default=False)
    puede_administrar_roles    = models.BooleanField(default=False)
    puede_configurar_empresa   = models.BooleanField(default=False)

    # Especiales
    acceso_todos_proyectos = models.BooleanField(default=False)
    es_superadmin          = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name        = 'Rol'
        verbose_name_plural = 'Roles'
        ordering            = ['nombre']

    def __str__(self):
        return self.nombre

    def cantidad_permisos(self):
        return sum(1 for campo in TODOS_LOS_PERMISOS if getattr(self, campo, False))


class UnidadMedida(models.Model):
    """Catálogo de unidades de medida estandarizadas."""
    codigo      = models.CharField('Código', max_length=20, unique=True)
    nombre      = models.CharField('Nombre', max_length=100)
    descripcion = models.CharField('Descripción', max_length=200, blank=True)
    aliases     = models.TextField(
        'Aliases',
        blank=True,
        help_text='Variantes separadas por coma que se normalizan a este código al importar. Ej: hh, hora hombre, horas hombre',
    )
    decimales   = models.PositiveSmallIntegerField(
        'Decimales',
        default=4,
        help_text='Cifras decimales al mostrar cantidades de esta unidad (0 = entero, 4 = predeterminado).',
    )
    activo      = models.BooleanField('Activa', default=True)

    class Meta:
        verbose_name        = 'Unidad de Medida'
        verbose_name_plural = 'Unidades de Medida'
        ordering            = ['codigo']

    def __str__(self):
        return f'{self.codigo} — {self.nombre}'


class ConfigDecimal(models.Model):
    """Configuración de cifras decimales por unidad de medida."""
    codigo      = models.CharField('Código', max_length=20, unique=True)
    nombre      = models.CharField('Nombre', max_length=100)
    descripcion = models.CharField('Descripción', max_length=200, blank=True)
    aliases     = models.TextField(
        'Aliases',
        blank=True,
        help_text='Variantes separadas por coma.',
    )
    decimales   = models.PositiveSmallIntegerField('Decimales', default=0)
    activo      = models.BooleanField('Activo', default=True)

    class Meta:
        verbose_name        = 'Configuración Decimal'
        verbose_name_plural = 'Configuraciones Decimales'
        ordering            = ['codigo']

    def __str__(self):
        return f'{self.codigo} — {self.decimales} dec.'


class CargoManoObra(models.Model):
    """Cargos de mano de obra y sus variantes para normalizar archivos importados."""
    codigo    = models.CharField('Código', max_length=10, unique=True)
    nombre    = models.CharField('Nombre oficial', max_length=100)
    variantes = models.TextField(
        'Variantes',
        blank=True,
        help_text='Palabras clave separadas por coma que identifican este cargo en archivos importados.',
    )
    orden     = models.PositiveSmallIntegerField('Orden', default=0)
    activo    = models.BooleanField('Activo', default=True)

    class Meta:
        verbose_name        = 'Cargo de Mano de Obra'
        verbose_name_plural = 'Cargos de Mano de Obra'
        ordering            = ['orden', 'codigo']

    def __str__(self):
        return f'{self.codigo} — {self.nombre}'


class ReglaDeteccionInsumo(models.Model):
    """Palabras clave para clasificar insumos importados por tipo (EQUIPO, SUBCONTRATO, etc.)."""
    TIPO_CHOICES = [
        ('EQUIPO',      'Equipo'),
        ('MAQUINARIA',  'Maquinaria'),
        ('SUBCONTRATO', 'Subcontrato'),
        ('MATERIAL',    'Material'),
        ('OTRO',        'Otro'),
    ]
    tipo     = models.CharField('Tipo de insumo', max_length=20, choices=TIPO_CHOICES)
    nombre   = models.CharField('Nombre de la regla', max_length=100)
    palabras = models.TextField(
        'Palabras clave',
        blank=True,
        help_text='Palabras clave separadas por coma. Si alguna aparece en la descripción del insumo, se asigna este tipo.',
    )
    orden    = models.PositiveSmallIntegerField('Orden', default=0)
    activo   = models.BooleanField('Activo', default=True)

    class Meta:
        verbose_name        = 'Regla de Detección de Insumo'
        verbose_name_plural = 'Reglas de Detección de Insumos'
        ordering            = ['tipo', 'orden', 'nombre']

    def __str__(self):
        return f'{self.get_tipo_display()} — {self.nombre}'


MODULOS_REPORTE = [
    ('REQUERIMIENTOS', 'Requerimientos'),
    ('LOGISTICA',      'Logística'),
    ('PRESUPUESTO',    'Presupuesto'),
    ('ALMACEN',        'Almacén'),
    ('MAQUINARIA',     'Maquinaria'),
    ('CONFIGURACION',  'Configuración'),
    ('PROYECTOS',      'Proyectos'),
    ('OTRO',           'Otro'),
]

ESTADOS_REPORTE = [
    ('PENDIENTE',   'Pendiente'),
    ('EN_REVISION', 'En revisión'),
    ('RESUELTO',    'Resuelto'),
]


class Reporte(models.Model):
    modulo      = models.CharField('Módulo', max_length=30, choices=MODULOS_REPORTE, default='OTRO')
    titulo      = models.CharField('Título', max_length=200)
    descripcion = models.TextField('Descripción', blank=True)
    estado      = models.CharField('Estado', max_length=20, choices=ESTADOS_REPORTE, default='PENDIENTE')
    created_at  = models.DateTimeField(auto_now_add=True)
    updated_at  = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Reporte'
        ordering = ['-created_at']

    def __str__(self):
        return f'[{self.get_modulo_display()}] {self.titulo}'


class ImagenReporte(models.Model):
    reporte = models.ForeignKey(Reporte, on_delete=models.CASCADE, related_name='imagenes')
    imagen  = models.ImageField('Imagen', upload_to='reportes/')

    def __str__(self):
        return f'Imagen de {self.reporte}'


class PerfilUsuario(models.Model):
    usuario  = models.OneToOneField(User, on_delete=models.CASCADE, related_name='perfil')
    rol      = models.ForeignKey(Rol, null=True, blank=True, on_delete=models.SET_NULL, related_name='usuarios')
    cargo    = models.CharField('Cargo', max_length=100, blank=True)
    telefono = models.CharField('Teléfono', max_length=20, blank=True)

    class Meta:
        verbose_name = 'Perfil de Usuario'

    def __str__(self):
        return f'Perfil de {self.usuario.username}'
