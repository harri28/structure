"""Servicios de dominio sobre el presupuesto — invariantes globales de saldo.

El contador `InsumoPresupuesto.cantidad` solo se descuenta al emitir la guía
de remisión. Entre la aprobación del REQ y la emisión de la guía existe un
"gap" donde las cantidades aprobadas son compromisos reales contra el
presupuesto pero no están reflejadas en ningún saldo. Este módulo expone
el saldo global de cada insumo descontando esos compromisos vigentes.
"""
from collections import defaultdict
from decimal import Decimal

from django.db.models import Sum


# REQs cuya `cantidad_aprobada` representa un compromiso efectivo contra el
# presupuesto. BORRADOR / SOLICITADO / ENVIADO / EN_REVISION aún no están
# aprobados; ANULADO libera el compromiso.
ESTADOS_REQ_COMPROMETE = ('APROBADO', 'COTIZADO', 'PARCIAL', 'ATENDIDO')


def saldo_disponible_insumo(insumo, excluir_req_pk=None):
    """Saldo global disponible del insumo (Decimal).

    Fórmula:
        disponible = cantidad_total − Σ cantidad_aprobada en DetalleRequerimiento
                     de REQs del mismo proyecto cuyo estado está en
                     ESTADOS_REQ_COMPROMETE.

    No se suman cotizaciones ni guías aparte: toda cotización respeta el
    saldo cotizable por REQ (`_saldo_cotizable` en apps/almacen/views.py), y
    toda guía nace de una cotización aprobada. Validando a nivel de
    aprobación de REQ, los pasos posteriores quedan implícitamente topados.

    `excluir_req_pk` descuenta el propio REQ al re-aprobarlo (para no
    contarse a sí mismo). En el flujo normal el REQ pasa a EN_REVISION
    antes de validar, así que esto rara vez hace falta.
    """
    from apps.requerimientos.models import DetalleRequerimiento

    qs = DetalleRequerimiento.objects.filter(
        insumo=insumo,
        requerimiento__estado__in=ESTADOS_REQ_COMPROMETE,
        requerimiento__proyecto=insumo.presupuesto.proyecto,
    )
    if excluir_req_pk:
        qs = qs.exclude(requerimiento_id=excluir_req_pk)
    comprometido = qs.aggregate(s=Sum('cantidad_aprobada'))['s'] or Decimal('0')
    return (insumo.cantidad_total or Decimal('0')) - comprometido


def consolidar_por_insumo(items):
    """Dado un iterable de (insumo_id, cantidad), devuelve {insumo_id: Σcantidad}.

    Usado para detectar y sumar líneas duplicadas del mismo insumo dentro de
    un mismo REQ antes de validar contra el saldo global.
    """
    acc = defaultdict(lambda: Decimal('0'))
    for insumo_id, cant in items:
        if not insumo_id:
            continue
        if not isinstance(cant, Decimal):
            cant = Decimal(str(cant or 0))
        acc[int(insumo_id)] += cant
    return dict(acc)
