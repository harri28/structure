from django.urls import path
from . import views

app_name = 'proyectos'

urlpatterns = [
    path('dashboard/', views.dashboard, name='dashboard'),
    path('', views.lista, name='lista'),
    path('nuevo/', views.crear, name='crear'),
    path('<int:pk>/', views.detalle, name='detalle'),
    path('<int:pk>/editar/', views.editar, name='editar'),
    path('<int:pk>/eliminar/', views.eliminar, name='eliminar'),
    # Equipo
    path('<int:pk>/activar/', views.activar, name='activar'),
    path('<int:pk>/equipo/agregar/', views.miembro_agregar, name='miembro_agregar'),
    path('<int:pk>/equipo/<int:usuario_id>/quitar/', views.miembro_quitar, name='miembro_quitar'),
]
