from django.urls import path
from . import views

app_name = 'requerimientos'

urlpatterns = [
    path('proyecto/<int:proyecto_id>/',          views.lista,    name='lista'),
    path('proyecto/<int:proyecto_id>/nuevo/',    views.crear,    name='crear'),
    path('<int:pk>/',                            views.detalle,  name='detalle'),
    path('<int:pk>/editar/',                     views.editar,   name='editar'),
    path('<int:pk>/eliminar/',                   views.eliminar, name='eliminar'),
    path('<int:pk>/aprobar/',                    views.aprobar,       name='aprobar'),
    path('proyecto/<int:proyecto_id>/vs-atenciones/', views.vs_atenciones, name='vs_atenciones'),
]
