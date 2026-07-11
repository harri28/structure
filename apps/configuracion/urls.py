from django.urls import path
from . import views

app_name = 'configuracion'

urlpatterns = [
    path('',                                  views.hub,                   name='hub'),
    path('empresa/',                          views.empresa,               name='empresa'),
    path('sunat/',                            views.sunat,                 name='sunat'),
    path('equipo/',                           views.equipo,                name='equipo'),
    # Roles
    path('roles/',                            views.roles,                 name='roles'),
    path('roles/nuevo/',                      views.rol_crear,             name='rol_crear'),
    path('roles/<int:pk>/editar/',            views.rol_editar,            name='rol_editar'),
    path('roles/<int:pk>/eliminar/',          views.rol_eliminar,          name='rol_eliminar'),
    # Usuarios
    path('usuarios/',                         views.usuarios,              name='usuarios'),
    path('usuarios/nuevo/',                   views.usuario_crear,         name='usuario_crear'),
    path('usuarios/<int:pk>/editar/',         views.usuario_editar,        name='usuario_editar'),
    path('usuarios/<int:pk>/password/',       views.usuario_password,      name='usuario_password'),
    path('usuarios/<int:pk>/eliminar/',       views.usuario_eliminar,      name='usuario_eliminar'),
    path('usuarios/<int:pk>/toggle/',         views.usuario_toggle,        name='usuario_toggle'),
    path('perfil/',                           views.perfil,                name='perfil'),
    # Unidades de Medida
    path('unidades/',                               views.unidad_lista,                  name='unidad_lista'),
    path('unidades/nueva/',                         views.unidad_crear,                  name='unidad_crear'),
    path('unidades/<int:pk>/editar/',               views.unidad_editar,                 name='unidad_editar'),
    path('unidades/<int:pk>/eliminar/',             views.unidad_eliminar,               name='unidad_eliminar'),
    path('unidades/exportar/',                        views.unidad_exportar,               name='unidad_exportar'),
    path('unidades/importar/',                        views.unidad_importar,               name='unidad_importar'),
    path('unidades/cargar-defaults/',               views.unidad_cargar_defaults,        name='unidad_cargar_defaults'),
    # Decimal
    path('decimal/',                              views.decimal_lista,                 name='decimal_lista'),
    path('decimal/nuevo/',                        views.decimal_crear,                 name='decimal_crear'),
    path('decimal/<int:pk>/editar/',              views.decimal_editar,                name='decimal_editar'),
    # Cargos de Mano de Obra
    path('cargos/',                                views.cargo_lista,                   name='cargo_lista'),
    path('cargos/nuevo/',                          views.cargo_crear,                   name='cargo_crear'),
    path('cargos/<int:pk>/editar/',                views.cargo_editar,                  name='cargo_editar'),
    path('cargos/cargar-defaults/',                views.cargo_cargar_defaults,         name='cargo_cargar_defaults'),
    # Reglas de Detección de Insumos
    path('reglas/',                                views.regla_lista,                   name='regla_lista'),
    path('reglas/nueva/',                          views.regla_crear,                   name='regla_crear'),
    path('reglas/<int:pk>/editar/',                views.regla_editar,                  name='regla_editar'),
    path('reglas/<int:pk>/eliminar/',              views.regla_eliminar,                name='regla_eliminar'),
    path('reglas/cargar-defaults/',                views.regla_cargar_defaults,         name='regla_cargar_defaults'),
]
