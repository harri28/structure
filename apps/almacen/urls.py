from django.urls import path
from . import views

app_name = 'almacen'

urlpatterns = [
    path('proyecto/<int:proyecto_id>/', views.dashboard, name='dashboard'),
    path('proyecto/<int:proyecto_id>/almacenero/', views.dashboard_almacenero, name='dashboard_almacenero'),
    # Stock / Kardex / Consumo
    path('proyecto/<int:proyecto_id>/stock/', views.stock, name='stock'),
    path('proyecto/<int:proyecto_id>/stock/api/', views.stock_api, name='stock_api'),
    path('proyecto/<int:proyecto_id>/consumo/', views.consumo, name='consumo'),
    path('proyecto/<int:proyecto_id>/stock/<int:insumo_id>/kardex/', views.kardex, name='kardex'),
    # Entradas
    path('proyecto/<int:proyecto_id>/entradas/', views.entrada_lista, name='entrada_lista'),
    path('proyecto/<int:proyecto_id>/entradas/nueva/', views.entrada_crear, name='entrada_crear'),
    path('proyecto/<int:proyecto_id>/entradas/aplicar/<int:guia_pk>/',
         views.entrada_aplicar_item, name='entrada_aplicar_item'),
    path('entradas/<int:pk>/', views.entrada_detalle, name='entrada_detalle'),
    path('entradas/<int:pk>/editar/', views.entrada_editar, name='entrada_editar'),
    path('entradas/<int:pk>/eliminar/', views.entrada_eliminar, name='entrada_eliminar'),
    path('entradas/<int:pk>/aceptar/',  views.entrada_aceptar,  name='entrada_aceptar'),
    path('entradas/<int:pk>/rechazar/', views.entrada_rechazar,  name='entrada_rechazar'),
    # Salidas / Atenciones
    path('proyecto/<int:proyecto_id>/salidas/', views.salida_lista, name='salida_lista'),
    path('proyecto/<int:proyecto_id>/salidas/nueva/', views.salida_crear, name='salida_crear'),
    path('proyecto/<int:proyecto_id>/atencion/crear/',       views.atencion_crear,     name='atencion_crear'),
    path('proyecto/<int:proyecto_id>/atencion/api/insumos/', views.api_insumos_buscar, name='api_insumos_buscar'),
    path('proyecto/<int:proyecto_id>/atencion/api/guias/',   views.api_insumo_guias,   name='api_insumo_guias'),
    path('salidas/<int:pk>/', views.salida_detalle, name='salida_detalle'),
    path('salidas/<int:pk>/editar/', views.salida_editar, name='salida_editar'),
    path('salidas/<int:pk>/eliminar/', views.salida_eliminar, name='salida_eliminar'),
    # Guías (perspectiva Almacén — recepción de guías despachadas por Logística)
    path('proyecto/<int:proyecto_id>/guias/', views.guias_almacen_lista, name='guias_almacen_lista'),
    path('guias/<int:pk>/ver/', views.guia_almacen_detalle, name='guia_almacen_detalle'),
    # Cotizaciones
    path('proyecto/<int:proyecto_id>/cotizaciones/', views.cot_lista, name='cot_lista'),
    path('proyecto/<int:proyecto_id>/cotizaciones/nueva/',  views.cot_crear,  name='cot_crear'),
    path('proyecto/<int:proyecto_id>/cotizaciones/rapida/',               views.cot_rapida,    name='cot_rapida'),
    path('proyecto/<int:proyecto_id>/cotizaciones/desde-req/<int:req_pk>/', views.cot_desde_req, name='cot_desde_req'),
    path('cotizaciones/<int:pk>/', views.cot_detalle, name='cot_detalle'),
    path('cotizaciones/<int:pk>/imprimir/', views.cot_imprimir, name='cot_imprimir'),
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
    path('api/req/<int:pk>/detalles/', views.api_req_detalles, name='api_req_detalles'),
    path('api/insumo/<int:insumo_id>/stock/', views.api_insumo_stock, name='api_insumo_stock'),
]
