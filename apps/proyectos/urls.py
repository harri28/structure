from django.urls import path
from . import views

app_name = 'proyectos'

urlpatterns = [
    path('dashboard/',                                      views.dashboard,       name='dashboard'),
    path('seleccionar/<int:pk>/',                           views.seleccionar,     name='seleccionar'),
    path('salir/',                                          views.salir_proyecto,  name='salir'),
    path('',                                               views.lista,           name='lista'),
    path('nuevo/',                                         views.crear,           name='crear'),
    path('<int:pk>/',                                      views.detalle,         name='detalle'),
    path('<int:pk>/editar/',                               views.editar,          name='editar'),
    path('<int:pk>/eliminar/',                             views.eliminar,        name='eliminar'),
    path('<int:pk>/personal/',                             views.personal,        name='personal'),
    path('<int:pk>/equipo/agregar/',                       views.miembro_agregar, name='miembro_agregar'),
    path('<int:pk>/equipo/<int:usuario_id>/quitar/',       views.miembro_quitar,      name='miembro_quitar'),
    path('<int:pk>/restablecer/',                          views.proyecto_restablecer, name='restablecer'),
]
