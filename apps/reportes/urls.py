from django.urls import path
from . import views

app_name = 'reportes'

urlpatterns = [
    path('proyecto/<int:proyecto_id>/',                         views.hub,                    name='hub'),

    # 1. Consumo de insumos por período
    path('proyecto/<int:proyecto_id>/insumos/',                 views.insumos_consumo,        name='insumos_consumo'),
    path('proyecto/<int:proyecto_id>/insumos/excel/',           views.insumos_consumo_excel,  name='insumos_consumo_excel'),

    # 2. Ejecutado vs presupuestado por partida
    path('proyecto/<int:proyecto_id>/avance/',                  views.avance_partidas,        name='avance_partidas'),
    path('proyecto/<int:proyecto_id>/avance/excel/',            views.avance_partidas_excel,  name='avance_partidas_excel'),

    # 3. Asistencia mensual del personal
    path('proyecto/<int:proyecto_id>/asistencia/',              views.asistencia_mes,         name='asistencia_mes'),
    path('proyecto/<int:proyecto_id>/asistencia/excel/',        views.asistencia_mes_excel,   name='asistencia_mes_excel'),

    # 4. Maquinaria trabajada por período
    path('proyecto/<int:proyecto_id>/maquinaria/',              views.maquinaria_periodo,     name='maquinaria_periodo'),
    path('proyecto/<int:proyecto_id>/maquinaria/excel/',        views.maquinaria_periodo_excel, name='maquinaria_periodo_excel'),
]
