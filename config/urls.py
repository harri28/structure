from django.contrib import admin
from django.urls import path, include

admin.site.site_header = 'S&S Gestión'
admin.site.site_title  = 'S&S Gestión'
admin.site.index_title = 'Panel de Administración'
from django.conf import settings
from django.conf.urls.static import static
from django.shortcuts import redirect
from django.contrib.auth import views as auth_views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('login/',  auth_views.LoginView.as_view(template_name='registration/login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
    path('', lambda request: redirect('proyectos:dashboard'), name='home'),
    path('proyectos/', include('apps.proyectos.urls', namespace='proyectos')),
    path('presupuesto/', include('apps.presupuesto.urls', namespace='presupuesto')),
    path('almacen/', include('apps.almacen.urls', namespace='almacen')),
    path('catalogo/', include('apps.catalogo.urls', namespace='catalogo')),
    path('configuracion/', include('apps.configuracion.urls', namespace='configuracion')),
    path('maquinaria/', include('apps.maquinaria.urls', namespace='maquinaria')),
    path('logistica/', include('apps.logistica.urls', namespace='logistica')),
    path('registro/', include('apps.registro.urls', namespace='registro')),
    path('requerimientos/', include('apps.requerimientos.urls', namespace='requerimientos')),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

if settings.DEBUG:
    from django.contrib.staticfiles.urls import staticfiles_urlpatterns
    urlpatterns += staticfiles_urlpatterns()
