from django.urls import path
from . import views

app_name = 'configuracion'

urlpatterns = [
    path('empresa/',                          views.empresa,               name='empresa'),
    path('equipo/',                           views.equipo,                name='equipo'),
    # Roles
    path('roles/',                            views.roles,                 name='roles'),
    path('roles/nuevo/',                      views.rol_crear,             name='rol_crear'),
    path('roles/<int:pk>/editar/',            views.rol_editar,            name='rol_editar'),
    path('roles/<int:pk>/eliminar/',          views.rol_eliminar,          name='rol_eliminar'),
    # Usuarios
    path('usuarios/',                         views.usuarios,              name='usuarios'),
    path('usuarios/nuevo/',                   views.usuario_crear,         name='usuario_crear'),
    path('usuarios/<int:pk>/editar/',         views.usuario_editar,        name='usuario_editar'),
    path('usuarios/<int:pk>/password/',       views.usuario_password,      name='usuario_password'),
    path('usuarios/<int:pk>/eliminar/',       views.usuario_eliminar,      name='usuario_eliminar'),
    path('usuarios/<int:pk>/toggle/',         views.usuario_toggle,        name='usuario_toggle'),
]
