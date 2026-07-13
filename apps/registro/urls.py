from django.urls import path
from . import views

app_name = 'registro'

urlpatterns = [
    path('', views.lista, name='lista'),

    # Notificaciones (AJAX)
    path('notif/json/',          views.notif_json,      name='notif_json'),
    path('notif/<int:pk>/leer/', views.notif_leer,      name='notif_leer'),
    path('notif/leer-todas/',    views.notif_leer_todas, name='notif_leer_todas'),
    path('notif/stream/',        views.notif_stream,     name='notif_stream'),
]
