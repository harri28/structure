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
        ('puede_ver_logistica',      'Ver guías de remisión y transportistas'),
        ('puede_gestionar_logistica','Crear y gestionar guías de remisión'),
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
    puede_ver_logistica       = models.BooleanField(default=True)
    puede_gestionar_logistica = models.BooleanField(default=False)

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
    activo      = models.BooleanField('Activa', default=True)

    class Meta:
        verbose_name        = 'Unidad de Medida'
        verbose_name_plural = 'Unidades de Medida'
        ordering            = ['codigo']

    def __str__(self):
        return f'{self.codigo} — {self.nombre}'



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


class PerfilUsuario(models.Model):
    usuario  = models.OneToOneField(User, on_delete=models.CASCADE, related_name='perfil')
    rol      = models.ForeignKey(Rol, null=True, blank=True, on_delete=models.SET_NULL, related_name='usuarios')
    cargo    = models.CharField('Cargo', max_length=100, blank=True)
    telefono = models.CharField('Teléfono', max_length=20, blank=True)

    class Meta:
        verbose_name = 'Perfil de Usuario'

    def __str__(self):
        return f'Perfil de {self.usuario.username}'
