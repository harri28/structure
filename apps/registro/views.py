from django.shortcuts import render
from django.contrib.auth.models import User
from django.core.paginator import Paginator
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from .models import RegistroAccion, Notificacion, ACCIONES, MODULOS


def lista(request):
    qs = RegistroAccion.objects.select_related('usuario').all()

    accion_sel  = request.GET.get('accion', '')
    modulo_sel  = request.GET.get('modulo', '')
    usuario_sel = request.GET.get('usuario', '')
    fecha_desde = request.GET.get('desde', '')
    fecha_hasta = request.GET.get('hasta', '')

    if accion_sel:
        qs = qs.filter(accion=accion_sel)
    if modulo_sel:
        qs = qs.filter(modulo=modulo_sel)
    if usuario_sel:
        qs = qs.filter(usuario__username=usuario_sel)
    if fecha_desde:
        qs = qs.filter(fecha__date__gte=fecha_desde)
    if fecha_hasta:
        qs = qs.filter(fecha__date__lte=fecha_hasta)

    paginator = Paginator(qs, 50)
    page = paginator.get_page(request.GET.get('page', 1))

    usuarios = User.objects.filter(is_active=True).order_by('username')

    return render(request, 'registro/lista.html', {
        'page_obj':    page,
        'acciones':    ACCIONES,
        'modulos':     MODULOS,
        'usuarios':    usuarios,
        'accion_sel':  accion_sel,
        'modulo_sel':  modulo_sel,
        'usuario_sel': usuario_sel,
        'fecha_desde': fecha_desde,
        'fecha_hasta': fecha_hasta,
        'total':       qs.count(),
    })


# ── Notificaciones ────────────────────────────────────────────────

def notif_json(request):
    """AJAX: últimas 20 notificaciones del usuario actual."""
    qs = Notificacion.objects.filter(usuario=request.user).order_by('-fecha')[:20]
    data = [
        {
            'id':     n.pk,
            'titulo': n.titulo,
            'mensaje': n.mensaje,
            'url':    n.url,
            'tipo':   n.tipo,
            'leida':  n.leida,
            'fecha':  n.fecha.strftime('%d/%m %H:%M'),
        }
        for n in qs
    ]
    no_leidas = Notificacion.objects.filter(usuario=request.user, leida=False).count()
    return JsonResponse({'notificaciones': data, 'no_leidas': no_leidas})


@require_POST
def notif_leer(request, pk):
    """Marca una notificación del usuario como leída."""
    Notificacion.objects.filter(usuario=request.user, pk=pk).update(leida=True)
    no_leidas = Notificacion.objects.filter(usuario=request.user, leida=False).count()
    return JsonResponse({'ok': True, 'no_leidas': no_leidas})


@require_POST
def notif_leer_todas(request):
    """Marca todas las notificaciones del usuario como leídas."""
    Notificacion.objects.filter(usuario=request.user, leida=False).update(leida=True)
    return JsonResponse({'ok': True, 'no_leidas': 0})
