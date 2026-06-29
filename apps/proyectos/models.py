from django.db import models
from django.contrib.auth.models import User


ESTADOS_PROYECTO = [
    ('FORMULACION', 'En Formulación'),
    ('EJECUCION', 'En Ejecución'),
    ('PAUSADO', 'Pausado'),
    ('TERMINADO', 'Terminado'),
    ('LIQUIDADO', 'Liquidado'),
]


class Proyecto(models.Model):
    codigo = models.CharField(max_length=30, unique=True)
    nombre = models.CharField(max_length=300)
    cliente = models.CharField(max_length=200, blank=True)
    ubicacion = models.CharField(max_length=300, blank=True)
    responsable = models.CharField(max_length=150, blank=True)
    fecha_inicio = models.DateField(null=True, blank=True)
    fecha_fin = models.DateField(null=True, blank=True)
    estado = models.CharField(max_length=20, choices=ESTADOS_PROYECTO, default='FORMULACION')
    descripcion = models.TextField(blank=True)
    activo = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Proyecto'
        verbose_name_plural = 'Proyectos'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.codigo} - {self.nombre}'

    def save(self, *args, **kwargs):
        if self.activo:
            Proyecto.objects.exclude(pk=self.pk).update(activo=False)
        super().save(*args, **kwargs)


class ProyectoMiembro(models.Model):
    proyecto  = models.ForeignKey(Proyecto, on_delete=models.CASCADE, related_name='miembros')
    usuario   = models.ForeignKey(User, on_delete=models.CASCADE, related_name='proyectos_asignados')
    agregado  = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name        = 'Miembro del Proyecto'
        verbose_name_plural = 'Miembros del Proyecto'
        unique_together     = ['proyecto', 'usuario']

    def __str__(self):
        return f'{self.usuario.username} → {self.proyecto.codigo}'
