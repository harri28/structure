from decimal import Decimal, InvalidOperation

from django.contrib.auth import authenticate
from django.db import transaction
from django.shortcuts import get_object_or_404

from rest_framework import status
from rest_framework.authentication import TokenAuthentication
from rest_framework.authtoken.models import Token
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response

from apps.proyectos.models import Proyecto
from apps.presupuesto.models import InsumoPresupuesto
from apps.requerimientos.models import Requerimiento, DetalleRequerimiento
from apps.requerimientos.views import _siguiente_numero, _siguiente_numero_global, _sync_snapshot
from apps.presupuesto.services import saldo_disponible_insumo, consolidar_por_insumo
from config.permisos import proyectos_visibles, tiene

from .models import SyncLog
from .serializers import (
    ProyectoSerializer, InsumoSerializer, RequerimientoSerializer,
)


# ── Auth ───────────────────────────────────────────────────────────────────

@api_view(['POST'])
@authentication_classes([])
@permission_classes([AllowAny])
def obtener_token(request):
    """POST /api/auth/token/ — login → devuelve token + datos básicos del usuario."""
    username = request.data.get('username', '').strip()
    password = request.data.get('password', '')
    user = authenticate(username=username, password=password)
    if not user or not user.is_active:
        return Response(
            {'detail': 'Usuario o contraseña incorrectos.'},
            status=status.HTTP_401_UNAUTHORIZED,
        )
    token, _ = Token.objects.get_or_create(user=user)
    rol_nombre = ''
    try:
        if user.perfil.rol:
            rol_nombre = user.perfil.rol.nombre
    except AttributeError:
        pass
    return Response({
        'token':     token.key,
        'user_id':   user.pk,
        'username':  user.username,
        'full_name': user.get_full_name() or user.username,
        'rol':       rol_nombre,
        'is_superuser': user.is_superuser,
    })


# ── Permisos de proyecto ───────────────────────────────────────────────────

def _proyecto_o_403(user, pk):
    """Devuelve el proyecto si el usuario tiene acceso, o levanta 404/403."""
    proyecto = get_object_or_404(Proyecto, pk=pk)
    if not proyectos_visibles(user).filter(pk=proyecto.pk).exists():
        return None
    return proyecto


# ── Proyectos ──────────────────────────────────────────────────────────────

@api_view(['GET'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def listar_proyectos(request):
    """GET /api/proyectos/ — proyectos visibles del usuario autenticado."""
    qs = proyectos_visibles(request.user).order_by('-id')
    return Response(ProyectoSerializer(qs, many=True).data)


# ── Insumos ────────────────────────────────────────────────────────────────

class InsumoPagination(PageNumberPagination):
    page_size = 25
    page_size_query_param = 'page_size'
    max_page_size = 100


@api_view(['GET'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def listar_insumos(request, proyecto_id):
    """GET /api/proyectos/{pid}/insumos/?q=abraz&page=1 — buscador paginado."""
    proyecto = _proyecto_o_403(request.user, proyecto_id)
    if proyecto is None:
        return Response({'detail': 'Sin acceso a este proyecto.'}, status=403)
    try:
        presupuesto = proyecto.presupuesto
    except Exception:
        return Response({'count': 0, 'next': None, 'previous': None, 'results': []})

    q = (request.GET.get('q') or '').strip()
    qs = presupuesto.insumos.all().order_by('codigo')
    if q:
        from django.db.models import Q
        qs = qs.filter(Q(descripcion__icontains=q) | Q(codigo__icontains=q))

    paginator = InsumoPagination()
    page = paginator.paginate_queryset(qs, request)
    data = InsumoSerializer(page, many=True).data
    return paginator.get_paginated_response(data)


# ── Requerimientos ─────────────────────────────────────────────────────────

@api_view(['GET'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def listar_requerimientos(request, proyecto_id):
    """GET /api/proyectos/{pid}/requerimientos/?mios=1&estado=BORRADOR"""
    proyecto = _proyecto_o_403(request.user, proyecto_id)
    if proyecto is None:
        return Response({'detail': 'Sin acceso a este proyecto.'}, status=403)
    qs = proyecto.requerimientos.filter(es_ajuste=False).prefetch_related('detalles__insumo')
    if request.GET.get('mios') == '1':
        qs = qs.filter(created_by=request.user)
    estado = request.GET.get('estado')
    if estado:
        qs = qs.filter(estado=estado)
    origen = request.GET.get('origen')
    if origen:
        qs = qs.filter(origen=origen)
    qs = qs.order_by('-created_at')[:200]
    return Response(RequerimientoSerializer(qs, many=True).data)


def _crear_requerimiento(user, proyecto, data):
    """Lógica compartida de creación. Devuelve (req, errores)."""
    serializer = RequerimientoSerializer(data=data)
    if not serializer.is_valid():
        return None, serializer.errors

    validated = serializer.validated_data
    detalles  = validated.pop('detalles', []) or []
    accion    = validated.pop('accion', 'borrador')
    validated.pop('client_uuid', None)  # ya lo procesó el view

    # Validar saldo global del presupuesto por insumo (misma lógica del web).
    pares = []
    for d in detalles:
        ins = d.get('insumo')
        cant = d.get('cantidad_requerida') or 0
        if ins and cant:
            pares.append((ins.pk, cant))
    pedido = consolidar_por_insumo(pares)
    errores_saldo = []
    insumos_por_id = {ins.pk: ins for ins in
                      InsumoPresupuesto.objects.filter(pk__in=pedido.keys())}
    for insumo_id, cant in pedido.items():
        ins = insumos_por_id.get(insumo_id)
        if not ins:
            continue
        disp = saldo_disponible_insumo(ins)
        if cant > disp:
            errores_saldo.append(
                f'"{ins.descripcion}": pediste {cant} pero solo quedan {disp} '
                f'{ins.unidad or "und"} disponibles en el presupuesto.'
            )
    if errores_saldo:
        return None, {'saldo': errores_saldo}

    # Determinar origen y estado según el rol del usuario.
    puede_aprobar = tiene(user, 'puede_aprobar_requerimientos')
    origen = 'OBRA' if puede_aprobar else 'ALMACEN'
    if puede_aprobar:
        estado = 'ENVIADO' if accion == 'enviar' else 'BORRADOR'
    else:
        # Almacenero no tiene borrador; va directo a SOLICITADO.
        estado = 'SOLICITADO'

    with transaction.atomic():
        req = Requerimiento(
            proyecto=proyecto,
            numero=_siguiente_numero(proyecto, origen=origen),
            numero_global=_siguiente_numero_global(),
            fecha=validated.get('fecha'),
            tipo=validated.get('tipo', 'MATERIAL'),
            obra=validated.get('obra', ''),
            solicitante=validated.get('solicitante', '') or (user.get_full_name() or user.username),
            cargo_solicitante=validated.get('cargo_solicitante', ''),
            sector_obra=validated.get('sector_obra', ''),
            observaciones=validated.get('observaciones', ''),
            estado=estado,
            origen=origen,
            created_by=user,
        )
        req.save()
        for d in detalles:
            det = DetalleRequerimiento(
                requerimiento=req,
                insumo=d.get('insumo'),
                codigo=d.get('codigo', ''),
                descripcion=d.get('descripcion', ''),
                unidad=d.get('unidad', ''),
                cantidad=d.get('cantidad', 0),
                cantidad_requerida=d.get('cantidad_requerida', 0),
                justificacion=d.get('justificacion', ''),
                observacion=d.get('observacion', ''),
            )
            _sync_snapshot(det)
    return req, None


@api_view(['POST'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def crear_requerimiento(request, proyecto_id):
    """POST /api/proyectos/{pid}/requerimientos/

    body:
      {
        "client_uuid": "<uuid>",        # opcional pero recomendado (idempotencia)
        "accion":      "borrador"|"enviar",
        "fecha":       "YYYY-MM-DD",
        "obra":        "...", "solicitante": "...", "cargo_solicitante": "...",
        "sector_obra": "...", "observaciones": "...",
        "detalles": [
          {"insumo_id": 5, "cantidad_requerida": "10.00", "unidad": "und", ...}
        ]
      }
    """
    proyecto = _proyecto_o_403(request.user, proyecto_id)
    if proyecto is None:
        return Response({'detail': 'Sin acceso a este proyecto.'}, status=403)
    if not tiene(request.user, 'puede_crear_requerimientos'):
        return Response({'detail': 'No tienes permiso para crear requerimientos.'}, status=403)

    # Idempotencia: si el client_uuid ya existe, devolvemos el REQ anterior.
    client_uuid = request.data.get('client_uuid')
    if client_uuid:
        previo = SyncLog.objects.filter(client_uuid=client_uuid).first()
        if previo and previo.requerimiento:
            return Response(
                RequerimientoSerializer(previo.requerimiento).data,
                status=status.HTTP_200_OK,
            )

    req, errores = _crear_requerimiento(request.user, proyecto, request.data)
    if errores:
        return Response(errores, status=status.HTTP_400_BAD_REQUEST)

    if client_uuid:
        SyncLog.objects.create(
            client_uuid=client_uuid, usuario=request.user,
            endpoint='requerimientos:crear', requerimiento=req,
        )
    return Response(RequerimientoSerializer(req).data, status=status.HTTP_201_CREATED)


@api_view(['GET'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def detalle_requerimiento(request, pk):
    """GET /api/requerimientos/{pk}/"""
    req = get_object_or_404(Requerimiento.objects.prefetch_related('detalles__insumo'), pk=pk)
    proyecto = _proyecto_o_403(request.user, req.proyecto_id)
    if proyecto is None:
        return Response({'detail': 'Sin acceso a este proyecto.'}, status=403)
    return Response(RequerimientoSerializer(req).data)
