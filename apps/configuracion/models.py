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


class PerfilUsuario(models.Model):
    usuario = models.OneToOneField(User, on_delete=models.CASCADE, related_name='perfil')
    rol     = models.ForeignKey(
        Rol, null=True, blank=True, on_delete=models.SET_NULL, related_name='usuarios'
    )

    class Meta:
        verbose_name = 'Perfil de Usuario'

    def __str__(self):
        return f'Perfil de {self.usuario.username}'
