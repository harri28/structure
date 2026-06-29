from django.contrib import admin
from .models import Producto


@admin.register(Producto)
class ProductoAdmin(admin.ModelAdmin):
    list_display = ['codigo', 'descripcion', 'categoria', 'unidad', 'activo']
    list_filter = ['categoria', 'activo']
    search_fields = ['codigo', 'descripcion']
    list_editable = ['activo']
