from django.urls import path
from . import views

app_name = 'catalogo'

urlpatterns = [
    path('', views.lista, name='lista'),
    path('importar/', views.importar, name='importar'),
    path('<int:pk>/editar/', views.editar, name='editar'),
    path('<int:pk>/eliminar/', views.eliminar, name='eliminar'),
    path('api/buscar/', views.api_buscar, name='api_buscar'),
]
