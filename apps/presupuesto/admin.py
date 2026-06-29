from django.contrib import admin
from .models import Presupuesto, Partida, RecursoPartida, Modificacion, PartidaModificacion


class PartidaInline(admin.TabularInline):
    model = Partida
    extra = 0
    fields = ['codigo', 'nombre', 'nivel', 'unidad', 'cantidad', 'precio_unitario']


@admin.register(Presupuesto)
class PresupuestoAdmin(admin.ModelAdmin):
    list_display = ['proyecto', 'nombre', 'fecha_importacion', 'created_at']


@admin.register(Partida)
class PartidaAdmin(admin.ModelAdmin):
    list_display = ['codigo', 'nombre', 'nivel', 'presupuesto', 'cantidad', 'precio_unitario']
    list_filter = ['nivel', 'presupuesto__proyecto']
    search_fields = ['codigo', 'nombre']


@admin.register(Modificacion)
class ModificacionAdmin(admin.ModelAdmin):
    list_display = ['proyecto', 'tipo', 'numero', 'nombre', 'estado', 'created_at']
    list_filter = ['tipo', 'estado']
