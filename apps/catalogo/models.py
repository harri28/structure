from django.db import models


UNIDADES = [
    ('BLS', 'Bolsa (BLS)'),
    ('CAJ', 'Caja (CAJ)'),
    ('GAL', 'Galón (GAL)'),
    ('GL', 'Global (GL)'),
    ('JGO', 'Juego'),
    ('KG', 'Kilogramo (KG)'),
    ('L', 'Litro (L)'),
    ('M2', 'M2'),
    ('M3', 'M3'),
    ('ML', 'Metro Lineal (ML)'),
    ('UND', 'Unidad (UND)'),
    ('PLG', 'Pulgada (PLG)'),
    ('MT', 'Metro (MT)'),
    ('TN', 'Tonelada (TN)'),
    ('RLL', 'Rollo (RLL)'),
    ('PAR', 'Par'),
    ('PZA', 'Pieza (PZA)'),
    ('GR', 'Gramo (GR)'),
    ('SET', 'Set'),
]

CATEGORIAS = [
    ('MATERIAL', 'Material'),
    ('EQUIPO', 'Equipo'),
    ('EPP', 'EPP'),
    ('UTIL', 'Útil'),
    ('HERRAMIENTA', 'Herramienta'),
    ('OTRO', 'Otro'),
]


class Producto(models.Model):
    codigo = models.CharField(max_length=20, unique=True)
    descripcion = models.CharField(max_length=300)
    categoria = models.CharField(max_length=20, choices=CATEGORIAS, default='MATERIAL')
    unidad = models.CharField(max_length=10, choices=UNIDADES, default='UND')
    activo = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Producto'
        verbose_name_plural = 'Productos'
        ordering = ['categoria', 'codigo']

    def __str__(self):
        return f'{self.codigo} - {self.descripcion}'
