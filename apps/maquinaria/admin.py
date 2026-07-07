from django.contrib import admin
from .models import TipoPersonal, Maquinaria, Cuadrilla, IntegranteCuadrilla, RegistroDiario, RegistroMaquinaria


class IntegranteInline(admin.TabularInline):
    model = IntegranteCuadrilla
    extra = 1


@admin.register(TipoPersonal)
class TipoPersonalAdmin(admin.ModelAdmin):
    list_display = ['codigo', 'nombre', 'costo_hora', 'activo']
    list_filter  = ['activo']


@admin.register(Maquinaria)
class MaquinariaAdmin(admin.ModelAdmin):
    list_display = ['codigo', 'nombre', 'tipo', 'costo_hora', 'placa', 'activo']
    list_filter  = ['tipo', 'activo']


@admin.register(Cuadrilla)
class CuadrillaAdmin(admin.ModelAdmin):
    list_display = ['nombre', 'activo']
    inlines      = [IntegranteInline]


@admin.register(RegistroDiario)
class RegistroDiarioAdmin(admin.ModelAdmin):
    list_display  = ['fecha', 'proyecto', 'cuadrilla', 'horas', 'partida']
    list_filter   = ['proyecto', 'fecha']
    date_hierarchy = 'fecha'


@admin.register(RegistroMaquinaria)
class RegistroMaquinariaAdmin(admin.ModelAdmin):
    list_display  = ['fecha', 'proyecto', 'maquinaria', 'horas', 'operador', 'partida']
    list_filter   = ['proyecto', 'fecha']
    date_hierarchy = 'fecha'
