from django.urls import path
from . import views

app_name = 'maquinaria'

urlpatterns = [
    # Dashboard del proyecto
    path('proyecto/<int:proyecto_id>/',            views.dashboard,         name='dashboard'),

    # Tipos de Personal (catálogo global)
    path('tipos-personal/',                        views.tipo_personal_lista,   name='tipo_personal_lista'),
    path('tipos-personal/nuevo/',                  views.tipo_personal_crear,   name='tipo_personal_crear'),
    path('tipos-personal/<int:pk>/editar/',        views.tipo_personal_editar,  name='tipo_personal_editar'),
    path('tipos-personal/<int:pk>/eliminar/',      views.tipo_personal_eliminar, name='tipo_personal_eliminar'),

    # Maquinaria (catálogo global)
    path('catalogo/',                              views.maquinaria_lista,    name='maquinaria_lista'),
    path('catalogo/nuevo/',                        views.maquinaria_crear,    name='maquinaria_crear'),
    path('catalogo/<int:pk>/editar/',              views.maquinaria_editar,   name='maquinaria_editar'),
    path('catalogo/<int:pk>/eliminar/',            views.maquinaria_eliminar, name='maquinaria_eliminar'),

    # Cuadrillas (catálogo global)
    path('cuadrillas/',                            views.cuadrilla_lista,    name='cuadrilla_lista'),
    path('cuadrillas/nueva/',                      views.cuadrilla_crear,    name='cuadrilla_crear'),
    path('cuadrillas/<int:pk>/',                   views.cuadrilla_detalle,  name='cuadrilla_detalle'),
    path('cuadrillas/<int:pk>/editar/',            views.cuadrilla_editar,   name='cuadrilla_editar'),
    path('cuadrillas/<int:pk>/eliminar/',          views.cuadrilla_eliminar, name='cuadrilla_eliminar'),
    path('cuadrillas/<int:pk>/integrante/agregar/', views.integrante_agregar, name='integrante_agregar'),
    path('cuadrillas/integrante/<int:pk>/eliminar/', views.integrante_eliminar, name='integrante_eliminar'),

    # Registros Diarios de Cuadrilla (por proyecto)
    path('proyecto/<int:proyecto_id>/registros/',         views.registro_lista,   name='registro_lista'),
    path('proyecto/<int:proyecto_id>/registros/nuevo/',   views.registro_crear,   name='registro_crear'),
    path('registros/<int:pk>/editar/',                    views.registro_editar,  name='registro_editar'),
    path('registros/<int:pk>/eliminar/',                  views.registro_eliminar, name='registro_eliminar'),

    # Registros de Maquinaria (por proyecto)
    path('proyecto/<int:proyecto_id>/maquinaria/',        views.maq_registro_lista,   name='maq_registro_lista'),
    path('proyecto/<int:proyecto_id>/maquinaria/nuevo/',  views.maq_registro_crear,   name='maq_registro_crear'),
    path('maquinaria-reg/<int:pk>/',                       views.maq_registro_detalle,  name='maq_registro_detalle'),
    path('maquinaria-reg/<int:pk>/editar/',               views.maq_registro_editar,   name='maq_registro_editar'),
    path('maquinaria-reg/<int:pk>/eliminar/',             views.maq_registro_eliminar, name='maq_registro_eliminar'),

    # Resumen HH / HM por partida
    path('proyecto/<int:proyecto_id>/resumen/',           views.resumen, name='resumen'),
]
