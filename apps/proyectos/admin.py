from django.contrib import admin
from .models import Proyecto


@admin.register(Proyecto)
class ProyectoAdmin(admin.ModelAdmin):
    list_display = ['codigo', 'nombre', 'cliente', 'estado', 'fecha_inicio']
    list_filter = ['estado']
    search_fields = ['codigo', 'nombre', 'cliente']
