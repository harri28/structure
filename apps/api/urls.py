from django.urls import path

from . import views

app_name = 'api'

urlpatterns = [
    path('auth/token/',                                views.obtener_token,         name='obtener_token'),
    path('proyectos/',                                 views.listar_proyectos,      name='listar_proyectos'),
    path('proyectos/<int:proyecto_id>/insumos/',       views.listar_insumos,        name='listar_insumos'),
    path('proyectos/<int:proyecto_id>/requerimientos/', views.listar_requerimientos, name='listar_requerimientos'),
    path('proyectos/<int:proyecto_id>/requerimientos/crear/', views.crear_requerimiento, name='crear_requerimiento'),
    path('requerimientos/<int:pk>/',                   views.detalle_requerimiento, name='detalle_requerimiento'),
]
