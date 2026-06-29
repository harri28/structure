from django.contrib import admin
from .models import Requerimiento, Entrada, Salida, Cotizacion


@admin.register(Requerimiento)
class RequerimientoAdmin(admin.ModelAdmin):
    list_display = ['numero', 'proyecto', 'fecha', 'tipo', 'estado']
    list_filter = ['estado', 'tipo']


@admin.register(Entrada)
class EntradaAdmin(admin.ModelAdmin):
    list_display = ['numero_guia', 'serie', 'proyecto', 'fecha', 'proveedor']


@admin.register(Salida)
class SalidaAdmin(admin.ModelAdmin):
    list_display = ['numero', 'proyecto', 'fecha', 'destino']


@admin.register(Cotizacion)
class CotizacionAdmin(admin.ModelAdmin):
    list_display = ['numero', 'proyecto', 'fecha', 'proveedor', 'estado']
    list_filter = ['estado']
