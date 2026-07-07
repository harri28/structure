from django.db import models
from django.contrib.auth.models import User


TIPOS_NOTIF = [
    ('info',    'Info'),
    ('success', 'Éxito'),
    ('warning', 'Advertencia'),
    ('danger',  'Error'),
]

ACCIONES = [
    ('CREAR',    'Crear'),
    ('EDITAR',   'Editar'),
    ('ELIMINAR', 'Eliminar'),
    ('IMPORTAR', 'Importar'),
    ('APROBAR',  'Aprobar'),
    ('ANULAR',   'Anular'),
    ('LOGIN',    'Iniciar sesión'),
    ('OTRO',     'Otro'),
]

MODULOS = [
    ('Proyectos',    'Proyectos'),
    ('Presupuesto',  'Presupuesto'),
    ('Almacén',      'Almacén'),
    ('Maquinaria',   'Maquinaria'),
    ('Logística',    'Logística'),
    ('Catálogo',     'Catálogo'),
    ('Configuración','Configuración'),
    ('Sesión',       'Sesión'),
]


class RegistroAccion(models.Model):
    usuario     = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL,
                                    related_name='acciones')
    fecha       = models.DateTimeField(auto_now_add=True)
    accion      = models.CharField(max_length=20, choices=ACCIONES, default='OTRO')
    modulo      = models.CharField(max_length=50, choices=MODULOS, default='Otro')
    descripcion = models.TextField()
    ip          = models.GenericIPAddressField(null=True, blank=True)

    class Meta:
        verbose_name        = 'Registro de Acción'
        verbose_name_plural = 'Registro de Actividad'
        ordering            = ['-fecha']

    def __str__(self):
        user = self.usuario.username if self.usuario else 'Sistema'
        return f'[{self.accion}] {user} — {self.descripcion[:60]}'


class Notificacion(models.Model):
    usuario = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notificaciones')
    titulo  = models.CharField(max_length=200)
    mensaje = models.TextField(blank=True)
    url     = models.CharField(max_length=500, blank=True)
    tipo    = models.CharField(max_length=10, choices=TIPOS_NOTIF, default='info')
    leida   = models.BooleanField(default=False)
    fecha   = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-fecha']

    def __str__(self):
        return self.titulo
