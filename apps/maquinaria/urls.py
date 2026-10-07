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

    # Maquinaria (alta/edición/baja; la lista vive por proyecto en maq_principal)
    path('catalogo/nuevo/',                        views.maquinaria_crear,    name='maquinaria_crear'),
    path('catalogo/<int:pk>/editar/',              views.maquinaria_editar,   name='maquinaria_editar'),
    path('catalogo/<int:pk>/eliminar/',            views.maquinaria_eliminar, name='maquinaria_eliminar'),
    path('catalogo/consulta-doc/',                 views.consulta_documento,  name='consulta_doc'),

    # Cuadrillas (catálogo global)
    path('cuadrillas/',                            views.cuadrilla_lista,    name='cuadrilla_lista'),
    path('cuadrillas/nueva/',                      views.cuadrilla_crear,    name='cuadrilla_crear'),
    path('cuadrillas/<int:pk>/',                   views.cuadrilla_detalle,  name='cuadrilla_detalle'),
    path('cuadrillas/<int:pk>/editar/',            views.cuadrilla_editar,   name='cuadrilla_editar'),
    path('cuadrillas/<int:pk>/eliminar/',          views.cuadrilla_eliminar, name='cuadrilla_eliminar'),
    path('cuadrillas/<int:pk>/integrante/agregar/', views.integrante_agregar, name='integrante_agregar'),
    path('cuadrillas/integrante/<int:pk>/eliminar/', views.integrante_eliminar, name='integrante_eliminar'),

    # Personal de Obra / Trabajadores (por proyecto)
    path('proyecto/<int:proyecto_id>/personal/',           views.trabajador_lista,  name='trabajador_lista'),
    path('proyecto/<int:proyecto_id>/personal/nuevo/',     views.trabajador_crear,  name='trabajador_crear'),
    path('personal/<int:pk>/',                             views.trabajador_detalle, name='trabajador_detalle'),
    path('personal/<int:pk>/editar/',                      views.trabajador_editar,  name='trabajador_editar'),
    path('personal/<int:pk>/eliminar/',                    views.trabajador_eliminar, name='trabajador_eliminar'),
    path('personal/<int:pk>/documento/agregar/',           views.documento_agregar,  name='documento_agregar'),
    path('personal/documento/<int:pk>/eliminar/',          views.documento_eliminar, name='documento_eliminar'),

    # Cuadrilla — En desarrollo (solo entrada; registros_crear/editar/eliminar retirados)
    path('proyecto/<int:proyecto_id>/registros/',         views.registro_lista,   name='registro_lista'),

    # Página principal de Maquinaria (lista de máquinas del proyecto)
    path('proyecto/<int:proyecto_id>/equipos/',                          views.maq_principal,           name='maq_principal'),

    # Registros de Maquinaria (por proyecto)
    path('proyecto/<int:proyecto_id>/maquinaria/nuevo/',                 views.maq_registro_crear,      name='maq_registro_crear'),
    path('proyecto/<int:proyecto_id>/maquinaria/nuevo/<int:maq_pk>/',    views.maq_registro_crear,      name='maq_registro_crear'),
    path('proyecto/<int:proyecto_id>/maquinaria/<int:maq_pk>/detalle/',  views.maq_detalle_maquinaria,  name='maq_detalle_maquinaria'),
    path('maquinaria-reg/<int:pk>/',                                     views.maq_registro_detalle,    name='maq_registro_detalle'),
    path('maquinaria-reg/<int:pk>/editar/',                              views.maq_registro_editar,     name='maq_registro_editar'),
    path('maquinaria-reg/<int:pk>/eliminar/',                            views.maq_registro_eliminar,   name='maq_registro_eliminar'),

    # Liquidaciones
    path('liquidacion/<int:pk>/',          views.liquidacion_detalle, name='liquidacion_detalle'),
    path('liquidacion/<int:pk>/cerrar/',   views.liquidacion_cerrar,  name='liquidacion_cerrar'),

    # Resumen HH / HM por partida
    path('proyecto/<int:proyecto_id>/resumen/',         views.resumen,          name='resumen'),
    path('proyecto/<int:proyecto_id>/resumen-mensual/', views.resumen_mensual,  name='resumen_mensual'),
]
