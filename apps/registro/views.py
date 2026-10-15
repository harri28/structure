import asyncio
import json
from django.shortcuts import render
from django.contrib.auth.models import User
from django.core.paginator import Paginator
from django.http import JsonResponse, StreamingHttpResponse
from django.views.decorators.http import require_POST
from .models import RegistroAccion, Notificacion, ACCIONES, MODULOS
from config.permisos import requiere


@requiere('puede_ver_actividad')
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


# ── Auditoría (solo superadmin) ────────────────────────────────────

def _es_superadmin(user):
    if user.is_superuser:
        return True
    try:
        return bool(user.perfil.rol and user.perfil.rol.es_superadmin)
    except AttributeError:
        return False


def auditoria(request):
    """Vista de auditoría enfocada en seguridad: logins, logouts, intentos fallidos, IPs.

    Solo accesible por superadmin (superuser o rol es_superadmin).
    """
    from django.shortcuts import redirect
    from django.db.models import Count, Q
    from django.utils import timezone
    from datetime import timedelta

    if not _es_superadmin(request.user):
        return redirect('proyectos:dashboard')

    qs = RegistroAccion.objects.select_related('usuario').all()

    # ── Filtros ──
    accion_sel  = request.GET.get('accion', '')
    usuario_sel = request.GET.get('usuario', '')
    ip_sel      = request.GET.get('ip', '').strip()
    fecha_desde = request.GET.get('desde', '')
    fecha_hasta = request.GET.get('hasta', '')
    solo_sesion = request.GET.get('sesion', '')  # '1' = solo LOGIN/LOGOUT/LOGIN_FAIL

    if solo_sesion == '1':
        qs = qs.filter(accion__in=['LOGIN', 'LOGOUT', 'LOGIN_FAIL'])
    if accion_sel:
        qs = qs.filter(accion=accion_sel)
    if usuario_sel:
        qs = qs.filter(usuario__username=usuario_sel)
    if ip_sel:
        qs = qs.filter(ip=ip_sel)
    if fecha_desde:
        qs = qs.filter(fecha__date__gte=fecha_desde)
    if fecha_hasta:
        qs = qs.filter(fecha__date__lte=fecha_hasta)

    # ── Stats de seguridad (últimas 24h) ──
    desde_24h = timezone.now() - timedelta(hours=24)
    base_24h  = RegistroAccion.objects.filter(fecha__gte=desde_24h)
    stats = {
        'logins_ok':   base_24h.filter(accion='LOGIN').count(),
        'logouts':     base_24h.filter(accion='LOGOUT').count(),
        'logins_fail': base_24h.filter(accion='LOGIN_FAIL').count(),
        'ips_unicas':  base_24h.exclude(ip__isnull=True).values('ip').distinct().count(),
    }
    # IPs con más intentos fallidos (últimas 24h)
    top_fail_ips = (
        base_24h.filter(accion='LOGIN_FAIL')
        .exclude(ip__isnull=True)
        .values('ip')
        .annotate(n=Count('id'))
        .order_by('-n')[:5]
    )

    paginator = Paginator(qs, 50)
    page = paginator.get_page(request.GET.get('page', 1))

    usuarios = User.objects.filter(is_active=True).order_by('username')

    return render(request, 'registro/auditoria.html', {
        'page_obj':     page,
        'acciones':     ACCIONES,
        'usuarios':     usuarios,
        'accion_sel':   accion_sel,
        'usuario_sel':  usuario_sel,
        'ip_sel':       ip_sel,
        'fecha_desde':  fecha_desde,
        'fecha_hasta':  fecha_hasta,
        'solo_sesion':  solo_sesion,
        'stats':        stats,
        'top_fail_ips': top_fail_ips,
        'total':        qs.count(),
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


async def notif_stream(request):
    """SSE: empuja conteo de no leídas al cliente en tiempo real."""
    from asgiref.sync import sync_to_async

    user = request.user
    if not user.is_authenticated:
        return StreamingHttpResponse(status=401)

    @sync_to_async
    def get_count():
        return Notificacion.objects.filter(usuario=user, leida=False).count()

    async def stream():
        last = -1
        ticks = 0
        while True:
            try:
                count = await get_count()
                if count != last:
                    last = count
                    yield f'data: {json.dumps({"no_leidas": count})}\n\n'
                ticks += 1
                if ticks % 3 == 0:
                    yield ': ping\n\n'
                await asyncio.sleep(10)
            except (asyncio.CancelledError, GeneratorExit):
                break
            except Exception:
                break

    response = StreamingHttpResponse(stream(), content_type='text/event-stream')
    response['Cache-Control'] = 'no-cache'
    response['X-Accel-Buffering'] = 'no'
    return response
