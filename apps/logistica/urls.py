from django.urls import path
from . import views

app_name = 'logistica'

urlpatterns = [
    # Dashboard por proyecto
    path('proyecto/<int:proyecto_id>/',              views.dashboard,   name='dashboard'),

    # Guías de Remisión
    path('proyecto/<int:proyecto_id>/guias/',        views.guia_lista,  name='guia_lista'),
    path('proyecto/<int:proyecto_id>/guias/nueva/',  views.guia_crear,  name='guia_crear'),
    path('guia/<int:pk>/',                           views.guia_detalle, name='guia_detalle'),
    path('guia/<int:pk>/editar/',                    views.guia_editar,  name='guia_editar'),
    path('guia/<int:pk>/estado/',                    views.guia_estado,  name='guia_estado'),
    path('guia/<int:pk>/eliminar/',                  views.guia_eliminar,name='guia_eliminar'),

    # Transportistas (catálogo global)
    path('transportistas/',           views.transportista_lista,  name='transportista_lista'),
    path('transportistas/nuevo/',     views.transportista_crear,  name='transportista_crear'),
    path('transportistas/<int:pk>/',  views.transportista_editar, name='transportista_editar'),

    # Requerimientos recibidos
    path('proyecto/<int:proyecto_id>/requerimientos/', views.requerimientos_log, name='requerimientos_log'),

    # Sub-módulos
    path('proyecto/<int:proyecto_id>/inventarios/',        views.inventarios,        name='inventarios'),
    path('proyecto/<int:proyecto_id>/almacen/',            views.almacen_log,        name='almacen_log'),
    path('proyecto/<int:proyecto_id>/control-maquinaria/', views.control_maquinaria, name='control_maquinaria'),
    path('proyecto/<int:proyecto_id>/abastecimiento/',     views.abastecimiento,     name='abastecimiento'),
]
