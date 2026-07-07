from django.urls import path
from . import views

app_name = 'presupuesto'

urlpatterns = [
    # Contractual
    path('proyecto/<int:proyecto_id>/',       views.lista,    name='lista'),
    path('proyecto/<int:proyecto_id>/nuevo/', views.crear,    name='crear'),
    path('<int:pk>/',                         views.detalle,  name='detalle'),
    path('<int:pk>/insumos/',                 views.insumos,  name='insumos'),
    path('<int:pk>/importar/',                views.importar, name='importar'),
    path('<int:pk>/eliminar/',                views.eliminar,         name='eliminar'),
    path('<int:pk>/partidas/limpiar/',        views.partidas_limpiar, name='partidas_limpiar'),
    path('<int:pk>/insumos/limpiar/',         views.insumos_limpiar,  name='insumos_limpiar'),

    # Lazy tree expand (AJAX)
    path('partida/<int:pk>/hijos/',          views.partida_hijos,        name='partida_hijos'),

    # Panel lateral AJAX
    path('partida/<int:pk>/panel/',          views.partida_panel,        name='partida_panel'),

    # ACU — Análisis de Costos Unitarios por partida
    path('partida/<int:pk>/acu/',            views.acu_partida,          name='acu_partida'),
    path('acu/recurso/<int:pk>/editar/',     views.acu_recurso_editar,   name='acu_recurso_editar'),
    path('acu/recurso/<int:pk>/eliminar/',   views.acu_recurso_eliminar, name='acu_recurso_eliminar'),

    # ML — Aprendizaje automático
    path('partida/<int:pk>/ml/sugeridos/',   views.ml_sugeridos,         name='ml_sugeridos'),
    path('partida/<int:pk>/ml/importar/',    views.ml_importar,          name='ml_importar'),
    path('<int:pk>/ml/buscar/',              views.ml_buscar,            name='ml_buscar'),

    # Modificaciones
    path('proyecto/<int:proyecto_id>/modificacion/nueva/',    views.modificacion_crear,    name='modificacion_crear'),
    path('modificacion/<int:pk>/',                            views.modificacion_detalle,  name='modificacion_detalle'),
    path('modificacion/<int:pk>/editar/',                     views.modificacion_editar,   name='modificacion_editar'),
    path('modificacion/<int:pk>/estado/',                     views.modificacion_estado,   name='modificacion_estado'),
    path('modificacion/<int:pk>/eliminar/',                   views.modificacion_eliminar, name='modificacion_eliminar'),
]
