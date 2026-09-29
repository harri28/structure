from django.contrib import admin
from .models import (
    TipoPersonal, Maquinaria, Cuadrilla, IntegranteCuadrilla,
    RegistroDiario, RegistroMaquinaria, Trabajador, DocumentoTrabajador,
)


class IntegranteInline(admin.TabularInline):
    model = IntegranteCuadrilla
    extra = 1


@admin.register(TipoPersonal)
class TipoPersonalAdmin(admin.ModelAdmin):
    list_display = ['codigo', 'nombre', 'costo_hora', 'activo']
    list_filter  = ['activo']


@admin.register(Maquinaria)
class MaquinariaAdmin(admin.ModelAdmin):
    list_display = ['codigo', 'nombre', 'tipo_equipo', 'placa', 'propietario_razon_social', 'activo']
    list_filter  = ['tipo_equipo', 'activo']


@admin.register(Cuadrilla)
class CuadrillaAdmin(admin.ModelAdmin):
    list_display = ['nombre', 'activo']
    inlines      = [IntegranteInline]


class DocumentoInline(admin.TabularInline):
    model = DocumentoTrabajador
    extra = 0


@admin.register(Trabajador)
class TrabajadorAdmin(admin.ModelAdmin):
    list_display = ['nombre_completo', 'dni', 'proyecto', 'tipo_personal', 'activo']
    list_filter  = ['proyecto', 'activo']
    inlines      = [DocumentoInline]


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
