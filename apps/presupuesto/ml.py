"""
Motor de aprendizaje automático para el módulo de presupuesto.

Tres capacidades:
  1. recursos_sugeridos(partida)   → recursos ACU de partidas similares
  2. precio_historico(nombre, ...)  → estadísticas de precio de proyectos anteriores
  3. buscar_similares(query, ...)   → búsqueda semántica TF-IDF

El índice TF-IDF se construye desde la DB la primera vez y se guarda en caché
(LocMemCache por defecto, TTL 1 hora). Se invalida automáticamente cuando se
guardan o eliminan partidas/recursos.
"""

import re
import logging
from functools import lru_cache

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from django.core.cache import cache

logger = logging.getLogger(__name__)

_CACHE_KEY = 'presupuesto_ml_v1'
_CACHE_TTL = 3600  # 1 hora


# ── Normalización de texto ────────────────────────────────────────

_RE_SPEC    = re.compile(r"f[`']\s*c\s*=?\s*\d+[\d/]*", re.I)   # f'c=210
_RE_ACERO   = re.compile(r"ø\s*\d+|#\s*\d+|\d+\s*mm",   re.I)   # Ø3/8, #4, 12mm
_RE_NUMS    = re.compile(r'\b\d+([.,]\d+)?\b')
_RE_PUNTOS  = re.compile(r'[^\w\s]')
_RE_SPACES  = re.compile(r'\s+')

_STOPWORDS = {
    'de', 'del', 'la', 'el', 'en', 'y', 'a', 'con', 'para', 'por',
    'un', 'una', 'los', 'las', 'al', 'e', 'o', 'inc', 'incl',
    'segun', 'según', 'tipo', 'de', 'incluye', 'incluido',
}


def _normalizar(texto: str) -> str:
    t = texto.upper()
    t = _RE_SPEC.sub('CONCRETO', t)
    t = _RE_ACERO.sub('ACERO', t)
    t = _RE_NUMS.sub('', t)
    t = _RE_PUNTOS.sub(' ', t)
    tokens = [w for w in _RE_SPACES.sub(' ', t).strip().split() if w not in _STOPWORDS]
    return ' '.join(tokens)


# ── Índice TF-IDF ─────────────────────────────────────────────────

class _PartidaIndex:
    """Índice en memoria de todas las partidas hoja."""

    def __init__(self, filas: list):
        self.filas = filas          # lista de dicts con metadatos
        nombres = [_normalizar(f['nombre']) for f in filas]

        self.vec = TfidfVectorizer(
            ngram_range=(1, 2),
            min_df=1,
            sublinear_tf=True,
        )
        if nombres:
            self.mat = self.vec.fit_transform(nombres)
        else:
            self.mat = None

    def similares(self, query: str, n: int = 10,
                  excluir_ids: set = None) -> list:
        """
        Retorna hasta n partidas ordenadas por similitud coseno.
        Cada elemento: {'fila': dict, 'score': float}
        """
        if self.mat is None:
            return []
        q = self.vec.transform([_normalizar(query)])
        sims = cosine_similarity(q, self.mat)[0]
        indices = sims.argsort()[::-1]

        excluir = excluir_ids or set()
        resultado = []
        for i in indices:
            if len(resultado) >= n:
                break
            fila = self.filas[i]
            score = float(sims[i])
            if score < 0.15:
                break
            if fila['id'] in excluir:
                continue
            resultado.append({'fila': fila, 'score': round(score, 3)})
        return resultado


def _construir_indice() -> _PartidaIndex:
    """Lee la DB y construye el índice TF-IDF."""
    from .models import Partida

    qs = (Partida.objects
          .filter(hijos__isnull=True)          # solo partidas hoja
          .prefetch_related('recursos')
          .select_related('presupuesto__proyecto'))

    filas = []
    for p in qs:
        recursos = [
            {
                'tipo':            r.tipo,
                'descripcion':     r.descripcion,
                'unidad':          r.unidad,
                'cantidad':        float(r.cantidad),
                'precio_unitario': float(r.precio_unitario),
            }
            for r in p.recursos.all()
        ]
        filas.append({
            'id':               p.pk,
            'nombre':           p.nombre,
            'codigo':           p.codigo,
            'unidad':           p.unidad,
            'precio_unitario':  float(p.precio_unitario),
            'presupuesto_id':   p.presupuesto_id,
            'proyecto_nombre':  p.presupuesto.proyecto.nombre,
            'recursos':         recursos,
        })

    logger.debug('ML: índice construido con %d partidas hoja', len(filas))
    return _PartidaIndex(filas)


def _get_indice() -> _PartidaIndex:
    idx = cache.get(_CACHE_KEY)
    if idx is None:
        idx = _construir_indice()
        cache.set(_CACHE_KEY, idx, _CACHE_TTL)
    return idx


def invalidar_cache():
    """Llamar cuando se crean/editan/eliminan partidas o recursos."""
    cache.delete(_CACHE_KEY)


# ── API pública ───────────────────────────────────────────────────

def recursos_sugeridos(partida, max_partidas: int = 8):
    """
    Retorna lista de recursos sugeridos para una partida basándose en
    partidas similares que ya tienen recursos ACU configurados.

    Salida: lista de dicts con keys:
      tipo, descripcion, unidad, cantidad, precio_unitario,
      score, fuente_nombre, votos
    """
    idx = _get_indice()
    candidatos = idx.similares(
        partida.nombre, n=max_partidas, excluir_ids={partida.pk}
    )

    # Solo usar partidas que tengan recursos ACU
    candidatos = [c for c in candidatos if c['fila']['recursos']]

    # Agregar recursos: clave = descripción normalizada
    pool: dict[str, dict] = {}
    for item in candidatos:
        fila  = item['fila']
        score = item['score']
        for r in fila['recursos']:
            key = _normalizar(r['descripcion'])
            if key not in pool:
                pool[key] = {
                    **r,
                    'score':         score,
                    'fuente_nombre': fila['proyecto_nombre'],
                    'votos':         1,
                    '_w_cant':       r['cantidad'] * score,
                    '_w_pu':         r['precio_unitario'] * score,
                    '_w_total':      score,
                }
            else:
                prev = pool[key]
                prev['votos']    += 1
                prev['_w_cant']  += r['cantidad'] * score
                prev['_w_pu']    += r['precio_unitario'] * score
                prev['_w_total'] += score

    # Promediar ponderado
    resultado = []
    for r in pool.values():
        w = r['_w_total']
        resultado.append({
            'tipo':            r['tipo'],
            'descripcion':     r['descripcion'],
            'unidad':          r['unidad'],
            'cantidad':        round(r['_w_cant'] / w, 4),
            'precio_unitario': round(r['_w_pu']   / w, 2),
            'score':           r['score'],
            'fuente_nombre':   r['fuente_nombre'],
            'votos':           r['votos'],
        })

    # Ordenar: más votos primero, luego score
    resultado.sort(key=lambda x: (-x['votos'], -x['score']))
    return resultado


def precio_historico(nombre: str, excluir_presupuesto_id: int = None):
    """
    Retorna dict con estadísticas de precio histórico para un nombre de partida,
    excluyendo el presupuesto actual (para no comparar con sí mismo).

    Retorna None si no hay datos suficientes (n < 2).
    Retorna: {'media': X, 'std': Y, 'min': A, 'max': B, 'n': N}
    """
    idx = _get_indice()
    candidatos = idx.similares(nombre, n=20)

    precios = [
        c['fila']['precio_unitario']
        for c in candidatos
        if (c['score'] >= 0.45
            and c['fila']['precio_unitario'] > 0
            and (excluir_presupuesto_id is None
                 or c['fila']['presupuesto_id'] != excluir_presupuesto_id))
    ]

    if len(precios) < 2:
        return None

    arr = np.array(precios)
    return {
        'media': round(float(arr.mean()), 2),
        'std':   round(float(arr.std()),  2),
        'min':   round(float(arr.min()),  2),
        'max':   round(float(arr.max()),  2),
        'n':     len(precios),
    }


def buscar_similares(query: str, presupuesto_id: int = None, n: int = 12):
    """
    Búsqueda semántica de partidas por nombre.
    Si se pasa presupuesto_id, restringe la búsqueda a ese presupuesto.

    Retorna lista de dicts: {fila, score}
    """
    if not query or not query.strip():
        return []
    idx = _get_indice()
    resultados = idx.similares(query, n=n * 3)

    if presupuesto_id is not None:
        resultados = [r for r in resultados
                      if r['fila']['presupuesto_id'] == presupuesto_id]

    return resultados[:n]
