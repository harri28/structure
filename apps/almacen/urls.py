from django.urls import path
from . import views

app_name = 'almacen'

urlpatterns = [
    path('proyecto/<int:proyecto_id>/', views.dashboard, name='dashboard'),
    # Stock / Kardex
    path('proyecto/<int:proyecto_id>/stock/', views.stock, name='stock'),
    path('proyecto/<int:proyecto_id>/stock/<int:producto_id>/kardex/', views.kardex, name='kardex'),
    # Requerimientos
    path('proyecto/<int:proyecto_id>/requerimientos/', views.req_lista, name='req_lista'),
    path('proyecto/<int:proyecto_id>/requerimientos/nuevo/', views.req_crear, name='req_crear'),
    path('requerimientos/<int:pk>/', views.req_detalle, name='req_detalle'),
    path('requerimientos/<int:pk>/editar/', views.req_editar, name='req_editar'),
    path('requerimientos/<int:pk>/eliminar/', views.req_eliminar, name='req_eliminar'),
    # Entradas
    path('proyecto/<int:proyecto_id>/entradas/', views.entrada_lista, name='entrada_lista'),
    path('proyecto/<int:proyecto_id>/entradas/nueva/', views.entrada_crear, name='entrada_crear'),
    path('entradas/<int:pk>/', views.entrada_detalle, name='entrada_detalle'),
    path('entradas/<int:pk>/editar/', views.entrada_editar, name='entrada_editar'),
    path('entradas/<int:pk>/eliminar/', views.entrada_eliminar, name='entrada_eliminar'),
    # Salidas
    path('proyecto/<int:proyecto_id>/salidas/', views.salida_lista, name='salida_lista'),
    path('proyecto/<int:proyecto_id>/salidas/nueva/', views.salida_crear, name='salida_crear'),
    path('salidas/<int:pk>/', views.salida_detalle, name='salida_detalle'),
    path('salidas/<int:pk>/editar/', views.salida_editar, name='salida_editar'),
    path('salidas/<int:pk>/eliminar/', views.salida_eliminar, name='salida_eliminar'),
    # Cotizaciones
    path('proyecto/<int:proyecto_id>/cotizaciones/', views.cot_lista, name='cot_lista'),
    path('proyecto/<int:proyecto_id>/cotizaciones/nueva/', views.cot_crear, name='cot_crear'),
    path('cotizaciones/<int:pk>/', views.cot_detalle, name='cot_detalle'),
    path('cotizaciones/<int:pk>/editar/', views.cot_editar, name='cot_editar'),
    path('cotizaciones/<int:pk>/eliminar/', views.cot_eliminar, name='cot_eliminar'),
    # Órdenes de Compra
    path('proyecto/<int:proyecto_id>/ordenes/', views.oc_lista, name='oc_lista'),
    path('proyecto/<int:proyecto_id>/ordenes/nueva/', views.oc_crear, name='oc_crear'),
    path('ordenes/<int:pk>/', views.oc_detalle, name='oc_detalle'),
    path('ordenes/<int:pk>/editar/', views.oc_editar, name='oc_editar'),
    path('ordenes/<int:pk>/eliminar/', views.oc_eliminar, name='oc_eliminar'),
    # AJAX
    path('api/productos/', views.api_productos, name='api_productos'),
]
