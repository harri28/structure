import json
import os
from decimal import Decimal, InvalidOperation

from django.http import JsonResponse
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.utils import timezone
from django.views.decorators.http import require_POST, require_GET

from apps.proyectos.models import Proyecto
from .models import (
    Presupuesto, Partida, InsumoPresupuesto, RecursoPartida,
    Modificacion, PartidaModificacion,
    TIPOS_RECURSO, TIPOS_MODIFICACION, ESTADOS_MODIFICACION,
)
from .importador import importar_presupuesto_excel, importar_insumos_excel, importar_automatico, detectar_tipo_excel
from .pdf_parser import importar_pdf, PYMUPDF_OK
from . import ml as ml_engine
from apps.registro.utils import log, notificar

_ESTADOS_VALIDOS = [e[0] for e in ESTADOS_MODIFICACION]


# ── Presupuesto Contractual ───────────────────────────────────────

def lista(request, proyecto_id):
    proyecto = get_object_or_404(Proyecto, pk=proyecto_id)

    try:
        presupuesto = proyecto.presupuesto
    except Presupuesto.DoesNotExist:
        presupuesto = None

    modificaciones = (
        proyecto.modificaciones
        .prefetch_related('partidas')
        .order_by('tipo', 'numero')
    )

    if presupuesto:
        mods_aprobadas    = [m for m in modificaciones if m.estado == 'APROBADO']
        costo_directo     = presupuesto.costo_directo()
        total_contractual = presupuesto.total_presupuesto()
        total_adicional   = sum(m.total_adicional() for m in mods_aprobadas)
        total_deductivo   = sum(m.total_deductivo() for m in mods_aprobadas)
        total_vigente     = total_contractual + total_adicional - total_deductivo
    else:
        costo_directo = total_contractual = total_adicional = total_deductivo = total_vigente = 0

    return render(request, 'presupuesto/lista.html', {
        'proyecto':          proyecto,
        'presupuesto':       presupuesto,
        'modificaciones':    modificaciones,
        'costo_directo':     costo_directo,
        'total_contractual': total_contractual,
        'total_adicional':   total_adicional,
        'total_deductivo':   total_deductivo,
        'total_vigente':     total_vigente,
    })


def detalle(request, pk):
    presupuesto = get_object_or_404(Presupuesto, pk=pk)
    partidas_raiz = (
        presupuesto.partidas
        .filter(padre__isnull=True)
        .prefetch_related('hijos')
    )
    cd = presupuesto.costo_directo()
    insumos_qs = presupuesto.insumos.all()

    return render(request, 'presupuesto/detalle.html', {
        'presupuesto':       presupuesto,
        'proyecto':          presupuesto.proyecto,
        'partidas_raiz':     partidas_raiz,
        'costo_directo':     cd,
        'gastos_generales':  presupuesto.gastos_generales(),
        'utilidad':          presupuesto.utilidad(),
        'sub_total':         presupuesto.sub_total(),
        'igv':               presupuesto.igv(),
        'costo_total_obra':  presupuesto.costo_total_obra(),
        'supervision':       presupuesto.supervision(),
        'total_presupuesto': presupuesto.total_presupuesto(),
        'precio_hints':      {},
        'insumos':           insumos_qs,
        'tipos':             TIPOS_RECURSO,
        'totales': {
            'mano_obra':    presupuesto.insumos.filter(tipo='MANO_OBRA').count(),
            'materiales':   presupuesto.insumos.filter(tipo='MATERIAL').count(),
            'equipos':      presupuesto.insumos.filter(tipo='EQUIPO').count(),
            'subcontratos': presupuesto.insumos.filter(tipo='SUBCONTRATO').count(),
        },
    })


def insumos(request, pk):
    presupuesto = get_object_or_404(Presupuesto, pk=pk)
    tipo_sel = request.GET.get('tipo', '')
    qs_all = presupuesto.insumos.all()
    qs = qs_all.filter(tipo=tipo_sel) if tipo_sel else qs_all
    return render(request, 'presupuesto/insumos.html', {
        'presupuesto':   presupuesto,
        'proyecto':      presupuesto.proyecto,
        'insumos':       qs,
        'insumos_total': qs_all.count(),
        'tipos':         TIPOS_RECURSO,
        'tipo_sel':      tipo_sel,
        'totales': {
            'mano_obra':    qs_all.filter(tipo='MANO_OBRA'),
            'materiales':   qs_all.filter(tipo='MATERIAL'),
            'equipos':      qs_all.filter(tipo='EQUIPO'),
            'subcontratos': qs_all.filter(tipo='SUBCONTRATO'),
        }
    })


def crear(request, proyecto_id):
    proyecto = get_object_or_404(Proyecto, pk=proyecto_id)

    if hasattr(proyecto, 'presupuesto'):
        return redirect('presupuesto:importar', pk=proyecto.presupuesto.pk)

    presupuesto = Presupuesto.objects.create(proyecto=proyecto, nombre='Presupuesto Contractual')
    return redirect('presupuesto:importar', pk=presupuesto.pk)


def importar(request, pk):
    presupuesto = get_object_or_404(Presupuesto, pk=pk)
    if request.method == 'POST' and request.FILES.get('archivo'):
        archivo = request.FILES['archivo']
        tipo    = request.POST.get('tipo_importacion', 'presupuesto')
        try:
            if tipo == 'auto':
                tipo_det, total, info = importar_automatico(archivo, presupuesto)
                presupuesto.nombre            = os.path.splitext(archivo.name)[0]
                presupuesto.archivo_origen    = archivo.name
                presupuesto.fecha_importacion = timezone.now()
                presupuesto.save()
                if tipo_det == 'insumos':
                    messages.success(request,
                        f'Detectado: Lista de Insumos. {total} recursos importados '
                        f'(Mano de Obra, Materiales, Equipos, Sub-contratos).')
                    return redirect('presupuesto:insumos', pk=presupuesto.pk)
                else:
                    if info['sin_precio'] == total:
                        messages.warning(request,
                            f'Detectado: Presupuesto. {total} partidas importadas, '
                            f'pero ninguna tiene precio unitario. '
                            f'Verifica que tu Excel tenga columna P.U. o PRECIO UNITARIO.')
                    else:
                        messages.success(request,
                            f'Detectado: Presupuesto. {total} partidas importadas correctamente.')
                    return redirect('presupuesto:detalle', pk=presupuesto.pk)

            elif tipo == 'insumos':
                # Bloquear si ya existen insumos
                if presupuesto.insumos.exists():
                    messages.error(request,
                        'Ya hay insumos importados. Elimínalos primero antes de volver a importar.')
                    return redirect('presupuesto:importar', pk=pk)

                # Advertencia si el archivo parece ser un presupuesto (no bloquea)
                tipo_detectado = detectar_tipo_excel(archivo)
                if tipo_detectado != 'insumos':
                    messages.warning(request,
                        f'Aviso: el archivo "{archivo.name}" no fue reconocido como Lista de Insumos '
                        f'(no se detectaron categorías MANO DE OBRA / MATERIALES / EQUIPO). '
                        f'Se importó de todas formas — revisa que los datos sean correctos.')

                total, unidades_desc = importar_insumos_excel(archivo, presupuesto)
                presupuesto.nombre            = os.path.splitext(archivo.name)[0]
                presupuesto.archivo_origen    = archivo.name
                presupuesto.fecha_importacion = timezone.now()
                presupuesto.save()
                log(request, 'IMPORTAR', 'Presupuesto',
                    f'{total} insumos importados en {presupuesto.proyecto.codigo} desde {archivo.name}')
                messages.success(request, f'{total} insumos importados correctamente.')
                if unidades_desc:
                    lista = ', '.join(f'"{u}"' for u in unidades_desc)
                    messages.warning(request,
                        f'Se encontraron {len(unidades_desc)} abreviatura(s) de unidad no reconocidas: {lista}. '
                        f'Agrégalas en Configuración → Unidades de Medida para normalizarlas en futuros imports.')
                return redirect('presupuesto:insumos', pk=presupuesto.pk)

            elif tipo == 'pdf':
                total, avisos = importar_pdf(archivo, presupuesto)
                presupuesto.nombre            = os.path.splitext(archivo.name)[0]
                presupuesto.archivo_origen    = archivo.name
                presupuesto.fecha_importacion = timezone.now()
                presupuesto.save()
                log(request, 'IMPORTAR', 'Presupuesto',
                    f'{total} partidas importadas desde PDF en {presupuesto.proyecto.codigo}')
                messages.success(request, f'{total} partidas importadas desde PDF.')
                return render(request, 'presupuesto/importar_pdf_resultado.html', {
                    'presupuesto': presupuesto,
                    'proyecto':    presupuesto.proyecto,
                    'total':       total,
                    'avisos':      avisos,
                })

            else:  # presupuesto
                # Bloquear si ya existen partidas
                if presupuesto.partidas.exists():
                    messages.error(request,
                        'Ya hay partidas importadas. Elimínalas primero antes de volver a importar.')
                    return redirect('presupuesto:importar', pk=pk)

                # Advertencia si el archivo parece ser insumos (no bloquea)
                tipo_detectado = detectar_tipo_excel(archivo)
                if tipo_detectado != 'presupuesto':
                    messages.warning(request,
                        f'Aviso: el archivo "{archivo.name}" fue reconocido como Lista de Insumos, '
                        f'no como Presupuesto. Se importó de todas formas — revisa que los datos sean correctos.')

                total, info = importar_presupuesto_excel(archivo, presupuesto)
                presupuesto.nombre            = os.path.splitext(archivo.name)[0]
                presupuesto.archivo_origen    = archivo.name
                presupuesto.fecha_importacion = timezone.now()
                presupuesto.save()
                log(request, 'IMPORTAR', 'Presupuesto',
                    f'{total} partidas importadas en {presupuesto.proyecto.codigo} desde {archivo.name}')
                notificar(
                    f'Presupuesto importado — {total} partidas',
                    mensaje=f'{presupuesto.proyecto.codigo}: {archivo.name}',
                    tipo='success',
                )
                if info['sin_precio'] == total:
                    messages.warning(request,
                        f'{total} partidas importadas, pero ninguna tiene precio unitario. '
                        f'Verifica que tu Excel tenga columna P.U. o PRECIO UNITARIO.')
                elif info['sin_precio'] > 0:
                    messages.warning(request,
                        f'{total} partidas importadas. {info["sin_precio"]} sin precio unitario.')
                else:
                    messages.success(request, f'{total} partidas importadas correctamente.')
                return redirect('presupuesto:detalle', pk=presupuesto.pk)

        except (ValueError, ImportError) as e:
            messages.error(request, str(e))
        except Exception as e:
            messages.error(request, f'Error al importar: {str(e)}')
        return redirect('presupuesto:importar', pk=pk)

    return render(request, 'presupuesto/importar.html', {
        'presupuesto':    presupuesto,
        'proyecto':       presupuesto.proyecto,
        'pymupdf_ok':     PYMUPDF_OK,
        'tiene_partidas': presupuesto.partidas.exists(),
        'tiene_insumos':  presupuesto.insumos.exists(),
        'n_partidas':     presupuesto.partidas.count(),
        'n_insumos':      presupuesto.insumos.count(),
    })


@require_POST
def partidas_limpiar(request, pk):
    presupuesto = get_object_or_404(Presupuesto, pk=pk)
    presupuesto.partidas.all().delete()
    if not presupuesto.insumos.exists():
        presupuesto.nombre = 'Presupuesto Contractual'
        presupuesto.archivo_origen = ''
        presupuesto.fecha_importacion = None
        presupuesto.save()
    messages.success(request, 'Partidas eliminadas. Ya puedes importar un nuevo archivo.')
    return redirect('presupuesto:importar', pk=pk)


@require_POST
def insumos_limpiar(request, pk):
    presupuesto = get_object_or_404(Presupuesto, pk=pk)
    presupuesto.insumos.all().delete()
    messages.success(request, 'Insumos eliminados. Ya puedes importar un nuevo archivo.')
    return redirect('presupuesto:importar', pk=pk)


def eliminar(request, pk):
    presupuesto = get_object_or_404(Presupuesto, pk=pk)
    proyecto = presupuesto.proyecto
    if request.method == 'POST':
        presupuesto.delete()
        messages.success(request, 'Presupuesto eliminado.')
        return redirect('presupuesto:lista', proyecto_id=proyecto.pk)
    return render(request, 'presupuesto/confirmar_eliminar.html', {
        'presupuesto': presupuesto,
        'proyecto':    proyecto,
    })


# ── Modificaciones ────────────────────────────────────────────────

def modificacion_crear(request, proyecto_id):
    proyecto = get_object_or_404(Proyecto, pk=proyecto_id)

    try:
        contractual = proyecto.presupuesto
    except Presupuesto.DoesNotExist:
        messages.error(request, 'El proyecto no tiene presupuesto contractual.')
        return redirect('presupuesto:lista', proyecto_id=proyecto_id)

    tipo = request.GET.get('tipo', 'ADICIONAL').upper()
    if tipo not in ('ADICIONAL', 'DEDUCTIVO', 'VINCULANTE'):
        tipo = 'ADICIONAL'

    # Leaf partidas of contractual (needed for DEDUCTIVO/VINCULANTE)
    partidas_hoja = []
    if tipo in ('DEDUCTIVO', 'VINCULANTE'):
        partidas_hoja = list(
            contractual.partidas
            .filter(hijos__isnull=True)
            .select_related('padre', 'padre__padre', 'padre__padre__padre')
            .order_by('orden')
        )

    num = proyecto.modificaciones.filter(tipo=tipo).count() + 1
    if tipo == 'ADICIONAL':
        nombre_sugerido = f'Adicional de Obra N°{num}'
    elif tipo == 'DEDUCTIVO':
        nombre_sugerido = f'Deductivo de Obra N°{num}'
    else:
        num_ad = proyecto.modificaciones.filter(tipo='ADICIONAL').count() + 1
        nombre_sugerido = f'Adicional N°{num_ad} con Deductivo Vinculante'

    if request.method == 'POST':
        tipo_post = request.POST.get('tipo', tipo).upper()
        nombre = request.POST.get('nombre', '').strip() or nombre_sugerido
        estado_inicial = request.POST.get('estado', 'PENDIENTE')
        if estado_inicial not in _ESTADOS_VALIDOS:
            estado_inicial = 'PENDIENTE'

        num_final = proyecto.modificaciones.filter(tipo=tipo_post).count() + 1
        mod = Modificacion.objects.create(
            proyecto=proyecto,
            tipo=tipo_post,
            numero=num_final,
            nombre=nombre,
            estado=estado_inicial,
        )

        creadas = 0

        if tipo_post in ('ADICIONAL', 'VINCULANTE'):
            codigos   = request.POST.getlist('ad_codigo[]')
            nombres   = request.POST.getlist('ad_nombre[]')
            unidades  = request.POST.getlist('ad_unidad[]')
            cantidades = request.POST.getlist('ad_cantidad[]')
            precios   = request.POST.getlist('ad_pu[]')
            origenes  = request.POST.getlist('ad_origen[]')

            for i, nom in enumerate(nombres):
                nom = nom.strip()
                if not nom:
                    continue
                try:
                    cantidad = Decimal(
                        cantidades[i].replace(',', '.') if i < len(cantidades) else '0'
                    )
                    pu = Decimal(
                        precios[i].replace(',', '.') if i < len(precios) else '0'
                    )
                except (InvalidOperation, ValueError):
                    continue
                origen_id = None
                if i < len(origenes) and origenes[i]:
                    try:
                        origen_id = int(origenes[i])
                    except (ValueError, TypeError):
                        pass
                PartidaModificacion.objects.create(
                    modificacion=mod,
                    subtipo='ADICIONAL',
                    partida_origen_id=origen_id,
                    codigo=codigos[i] if i < len(codigos) else '',
                    nombre=nom,
                    unidad=unidades[i] if i < len(unidades) else '',
                    cantidad=cantidad,
                    precio_unitario=pu,
                    orden=i,
                )
                creadas += 1

        if tipo_post in ('DEDUCTIVO', 'VINCULANTE'):
            leaf_partidas = list(contractual.partidas.filter(hijos__isnull=True).order_by('orden'))
            for partida in leaf_partidas:
                val = request.POST.get(f'ded_cantidad_{partida.pk}', '').strip()
                if not val:
                    continue
                try:
                    cantidad = Decimal(val.replace(',', '.'))
                except (InvalidOperation, ValueError):
                    continue
                if cantidad <= 0:
                    continue
                PartidaModificacion.objects.create(
                    modificacion=mod,
                    subtipo='DEDUCTIVO',
                    partida_origen=partida,
                    codigo=partida.codigo,
                    nombre=partida.nombre,
                    unidad=partida.unidad,
                    cantidad=cantidad,
                    precio_unitario=partida.precio_unitario,
                    orden=partida.orden,
                )
                creadas += 1

        messages.success(request, f'"{mod}" creada con {creadas} partidas.')
        return redirect('presupuesto:modificacion_detalle', pk=mod.pk)

    return render(request, 'presupuesto/modificacion_form.html', {
        'proyecto':          proyecto,
        'contractual':       contractual,
        'tipo':              tipo,
        'partidas_hoja':     partidas_hoja,
        'nombre_sugerido':   nombre_sugerido,
        'tipos_modificacion': TIPOS_MODIFICACION,
        'estados':           ESTADOS_MODIFICACION,
    })


def modificacion_detalle(request, pk):
    mod = get_object_or_404(Modificacion, pk=pk)
    partidas_ad  = mod.partidas.filter(subtipo='ADICIONAL')
    partidas_ded = mod.partidas.filter(subtipo='DEDUCTIVO')
    return render(request, 'presupuesto/modificacion_detalle.html', {
        'mod':         mod,
        'proyecto':    mod.proyecto,
        'partidas_ad': partidas_ad,
        'partidas_ded': partidas_ded,
        'estados':     ESTADOS_MODIFICACION,
    })


def modificacion_editar(request, pk):
    mod = get_object_or_404(Modificacion, pk=pk)
    proyecto = mod.proyecto

    try:
        contractual = proyecto.presupuesto
    except Presupuesto.DoesNotExist:
        contractual = None

    # Pre-load existing deductivo quantities indexed by partida_origen_id
    existing_ded = {}
    if mod.tipo in ('DEDUCTIVO', 'VINCULANTE'):
        for pm in mod.partidas.filter(subtipo='DEDUCTIVO').select_related('partida_origen'):
            if pm.partida_origen_id:
                existing_ded[pm.partida_origen_id] = pm.cantidad

    partidas_hoja = []
    if contractual and mod.tipo in ('DEDUCTIVO', 'VINCULANTE'):
        partidas_hoja = list(
            contractual.partidas.filter(hijos__isnull=True)
            .select_related('padre', 'padre__padre', 'padre__padre__padre')
            .order_by('orden')
        )

    if request.method == 'POST':
        mod.nombre = request.POST.get('nombre', mod.nombre).strip() or mod.nombre
        nuevo_estado = request.POST.get('estado', mod.estado)
        if nuevo_estado in _ESTADOS_VALIDOS:
            mod.estado = nuevo_estado
        mod.save()

        if contractual and mod.tipo in ('DEDUCTIVO', 'VINCULANTE'):
            mod.partidas.filter(subtipo='DEDUCTIVO').delete()
            leaf_partidas = list(contractual.partidas.filter(hijos__isnull=True).order_by('orden'))
            for partida in leaf_partidas:
                val = request.POST.get(f'ded_cantidad_{partida.pk}', '').strip()
                if not val:
                    continue
                try:
                    cantidad = Decimal(val.replace(',', '.'))
                except (InvalidOperation, ValueError):
                    continue
                if cantidad <= 0:
                    continue
                PartidaModificacion.objects.create(
                    modificacion=mod,
                    subtipo='DEDUCTIVO',
                    partida_origen=partida,
                    codigo=partida.codigo,
                    nombre=partida.nombre,
                    unidad=partida.unidad,
                    cantidad=cantidad,
                    precio_unitario=partida.precio_unitario,
                    orden=partida.orden,
                )

        messages.success(request, 'Modificación actualizada.')
        return redirect('presupuesto:modificacion_detalle', pk=pk)

    partidas_hoja_data = [
        {'partida': p, 'ded_qty': existing_ded.get(p.pk, '')}
        for p in partidas_hoja
    ]

    return render(request, 'presupuesto/modificacion_editar.html', {
        'mod':               mod,
        'proyecto':          proyecto,
        'contractual':       contractual,
        'partidas_hoja_data': partidas_hoja_data,
        'estados':           ESTADOS_MODIFICACION,
    })


def modificacion_estado(request, pk):
    if request.method == 'POST':
        mod = get_object_or_404(Modificacion, pk=pk)
        nuevo = request.POST.get('estado', '')
        if nuevo in _ESTADOS_VALIDOS:
            mod.estado = nuevo
            mod.save()
            messages.success(request, f'Estado: {mod.get_estado_display()}')
    return redirect('presupuesto:modificacion_detalle', pk=pk)


def modificacion_eliminar(request, pk):
    mod = get_object_or_404(Modificacion, pk=pk)
    proyecto = mod.proyecto
    if request.method == 'POST':
        mod.delete()
        messages.success(request, 'Modificación eliminada.')
        return redirect('presupuesto:lista', proyecto_id=proyecto.pk)
    return render(request, 'presupuesto/modificacion_confirmar_eliminar.html', {
        'mod':     mod,
        'proyecto': proyecto,
    })


# ── ACU — Análisis de Costos Unitarios ───────────────────────────

_TIPO_META = {
    'MATERIAL':    {'label': 'Materiales',        'color': '#3b82f6', 'bg': '#eff6ff'},
    'MANO_OBRA':   {'label': 'Mano de Obra',      'color': '#10b981', 'bg': '#f0fdf4'},
    'EQUIPO':      {'label': 'Equipo/Maquinaria', 'color': '#f59e0b', 'bg': '#fffbeb'},
    'SUBCONTRATO': {'label': 'Subcontratos',      'color': '#8b5cf6', 'bg': '#f5f3ff'},
    'OTRO':        {'label': 'Otros',             'color': '#6b7280', 'bg': '#f9fafb'},
}


def acu_partida(request, pk):
    partida = get_object_or_404(Partida, pk=pk)
    presupuesto = partida.presupuesto
    proyecto = presupuesto.proyecto

    if request.method == 'POST':
        tipo = request.POST.get('tipo', 'MATERIAL')
        if tipo not in _TIPO_META:
            tipo = 'MATERIAL'
        descripcion = request.POST.get('descripcion', '').strip()
        if descripcion:
            try:
                cantidad = Decimal(request.POST.get('cantidad', '0').replace(',', '.'))
                precio_unitario = Decimal(request.POST.get('precio_unitario', '0').replace(',', '.'))
            except (InvalidOperation, ValueError):
                cantidad = precio_unitario = Decimal('0')
            RecursoPartida.objects.create(
                partida=partida,
                tipo=tipo,
                codigo=request.POST.get('codigo', '').strip(),
                descripcion=descripcion,
                unidad=request.POST.get('unidad', '').strip(),
                cantidad=cantidad,
                precio_unitario=precio_unitario,
            )
            ml_engine.invalidar_cache()
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'ok': True})
            messages.success(request, 'Recurso agregado.')
        else:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'ok': False, 'error': 'La descripción es requerida.'}, status=400)
            messages.warning(request, 'La descripción es requerida.')
        return redirect('presupuesto:acu_partida', pk=pk)

    recursos = list(partida.recursos.order_by('tipo', 'pk'))

    grupos = []
    for tipo_key, meta in _TIPO_META.items():
        rs = [r for r in recursos if r.tipo == tipo_key]
        if rs:
            subtotal = sum(r.total() for r in rs)
            grupos.append({
                'tipo':     tipo_key,
                'label':    meta['label'],
                'color':    meta['color'],
                'bg':       meta['bg'],
                'recursos': rs,
                'subtotal': subtotal,
            })

    total_acu = sum(r.total() for r in recursos)
    diferencia = total_acu - partida.precio_unitario

    precio_hist = ml_engine.precio_historico(
        partida.nombre, excluir_presupuesto_id=presupuesto.pk
    )

    return render(request, 'presupuesto/acu.html', {
        'partida':      partida,
        'presupuesto':  presupuesto,
        'proyecto':     proyecto,
        'grupos':       grupos,
        'total_acu':    total_acu,
        'diferencia':   diferencia,
        'diferencia_abs': abs(diferencia),
        'tipos':        TIPOS_RECURSO,
        'precio_hist':  precio_hist,
    })


def acu_recurso_editar(request, pk):
    recurso = get_object_or_404(RecursoPartida, pk=pk)
    partida = recurso.partida

    if request.method == 'POST':
        nuevo_tipo = request.POST.get('tipo', recurso.tipo)
        if nuevo_tipo in _TIPO_META:
            recurso.tipo = nuevo_tipo
        recurso.codigo = request.POST.get('codigo', '').strip()
        desc = request.POST.get('descripcion', '').strip()
        if desc:
            recurso.descripcion = desc
        recurso.unidad = request.POST.get('unidad', '').strip()
        try:
            recurso.cantidad = Decimal(request.POST.get('cantidad', '0').replace(',', '.'))
            recurso.precio_unitario = Decimal(
                request.POST.get('precio_unitario', '0').replace(',', '.')
            )
        except (InvalidOperation, ValueError):
            pass
        recurso.save()
        messages.success(request, 'Recurso actualizado.')
        return redirect('presupuesto:acu_partida', pk=partida.pk)

    return render(request, 'presupuesto/acu_recurso_editar.html', {
        'recurso':     recurso,
        'partida':     partida,
        'presupuesto': partida.presupuesto,
        'proyecto':    partida.presupuesto.proyecto,
        'tipos':       TIPOS_RECURSO,
    })


def acu_recurso_eliminar(request, pk):
    recurso = get_object_or_404(RecursoPartida, pk=pk)
    partida_pk = recurso.partida_id
    if request.method == 'POST':
        recurso.delete()
        ml_engine.invalidar_cache()
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'ok': True})
        messages.success(request, 'Recurso eliminado.')
    return redirect('presupuesto:acu_partida', pk=partida_pk)


# ── ML — Aprendizaje automático ───────────────────────────────────

@require_GET
def ml_sugeridos(request, pk):
    """AJAX: retorna recursos sugeridos para una partida (JSON)."""
    partida = get_object_or_404(Partida, pk=pk)
    sugeridos = ml_engine.recursos_sugeridos(partida)
    return JsonResponse({'sugeridos': sugeridos, 'partida_nombre': partida.nombre})


@require_POST
def ml_importar(request, pk):
    """Importa recursos sugeridos seleccionados a una partida."""
    partida = get_object_or_404(Partida, pk=pk)
    try:
        body    = json.loads(request.body)
        items   = body.get('recursos', [])
    except (json.JSONDecodeError, AttributeError):
        return JsonResponse({'error': 'JSON inválido'}, status=400)

    creados = 0
    for item in items:
        desc = str(item.get('descripcion', '')).strip()
        tipo = item.get('tipo', 'MATERIAL')
        if not desc or tipo not in dict(_TIPO_META):
            continue
        try:
            cant = Decimal(str(item.get('cantidad', 0)))
            pu   = Decimal(str(item.get('precio_unitario', 0)))
        except InvalidOperation:
            cant = pu = Decimal('0')
        RecursoPartida.objects.create(
            partida         = partida,
            tipo            = tipo,
            descripcion     = desc[:400],
            unidad          = str(item.get('unidad', '')).strip()[:20],
            cantidad        = cant,
            precio_unitario = pu,
        )
        creados += 1

    if creados:
        ml_engine.invalidar_cache()
    return JsonResponse({'creados': creados})


@require_GET
def partida_hijos(request, pk):
    """AJAX: retorna las filas hijas directas de una partida (lazy tree expand)."""
    partida = get_object_or_404(Partida, pk=pk)
    hijos = partida.hijos.prefetch_related('hijos').order_by('orden')
    return render(request, 'presupuesto/_partida_rows.html', {'partidas': hijos})


@require_GET
def partida_panel(request, pk):
    """AJAX: fragmento HTML del panel lateral de detalle de una partida."""
    partida = get_object_or_404(Partida.objects.prefetch_related('hijos', 'recursos'), pk=pk)
    es_hoja = not partida.hijos.exists()
    recursos = list(partida.recursos.order_by('tipo', 'descripcion'))

    TIPO_LABELS = {
        'MANO_OBRA':   'Mano de Obra',
        'MATERIAL':    'Materiales',
        'EQUIPO':      'Equipo / Maquinaria',
        'SUBCONTRATO': 'Sub-Contratos',
        'OTRO':        'Otros',
    }
    grupos = {}   # label → {'recursos': [...], 'subtotal': Decimal}
    for r in recursos:
        label = TIPO_LABELS.get(r.tipo, r.tipo)
        if label not in grupos:
            grupos[label] = {'recursos': [], 'subtotal': Decimal('0')}
        grupos[label]['recursos'].append(r)
        grupos[label]['subtotal'] += r.total()

    hijos = list(partida.hijos.order_by('orden')[:30]) if not es_hoja else []
    total_acu = sum(g['subtotal'] for g in grupos.values()) if grupos else Decimal('0')

    return render(request, 'presupuesto/_panel_partida.html', {
        'partida':   partida,
        'es_hoja':   es_hoja,
        'grupos':    grupos,
        'hijos':     hijos,
        'tipos':     TIPOS_RECURSO,
        'total_acu': total_acu,
    })


@require_GET
def ml_buscar(request, pk):
    """AJAX: búsqueda semántica de partidas dentro de un presupuesto."""
    presupuesto = get_object_or_404(Presupuesto, pk=pk)
    query = request.GET.get('q', '').strip()
    if not query:
        return JsonResponse({'resultados': []})

    resultados = ml_engine.buscar_similares(query, presupuesto_id=presupuesto.pk)
    data = [
        {
            'id':              r['fila']['id'],
            'codigo':          r['fila']['codigo'],
            'nombre':          r['fila']['nombre'],
            'unidad':          r['fila']['unidad'],
            'precio_unitario': r['fila']['precio_unitario'],
            'score':           r['score'],
            'acu_url': f"/presupuesto/partida/{r['fila']['id']}/acu/",
        }
        for r in resultados
    ]
    return JsonResponse({'resultados': data})
