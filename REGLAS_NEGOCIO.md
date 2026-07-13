# Reglas de Negocio — S&S Gestión

Documento de referencia para lógica de dominio, fórmulas y flujos del sistema.
No duplica el esquema de modelos — se enfoca en el **por qué** y el **cómo** de cada decisión.

---

## 1. Módulo Presupuesto

### Campos clave de `InsumoPresupuesto`

| Campo | Descripción | ¿Cambia? |
|-------|-------------|----------|
| `cantidad_total` | Cantidad original importada desde S10. Fuente de verdad permanente. | Nunca |
| `cantidad` | Contador restante. Se descuenta cada vez que logística aprueba un requerimiento. | Sí |
| `costo_unitario` | Precio unitario del insumo en el presupuesto. | No en operación |
| `total` | `cantidad_total × costo_unitario`. Importe total del insumo. | No en operación |

**Regla:** `cantidad` nunca puede bajar de 0. El sistema aplica `max(0, cantidad - aprobada)`.

**Restaurar contador:** En Superadmin → Proyecto → Restablecer → Logística, se ejecuta `cantidad = cantidad_total` para todos los insumos del proyecto.

---

## 2. Módulo Requerimientos

### Estados del Requerimiento

```
BORRADOR → ENVIADO → EN_REVISION → APROBADO / PARCIAL → ATENDIDO
                                 → ANULADO
```

| Estado | Descripción |
|--------|-------------|
| `BORRADOR` | Creado pero no enviado a logística |
| `ENVIADO` | Enviado, pendiente de revisión |
| `EN_REVISION` | Logística lo abrió y está evaluando |
| `APROBADO` | Todas las cantidades aprobadas por logística |
| `PARCIAL` | Algunas cantidades aprobadas, otras no |
| `ATENDIDO` | Materiales físicamente entregados |
| `ANULADO` | Cancelado |

### Formulario de Requerimiento — columna CANTIDAD

La columna **CANTIDAD** (readonly) muestra `InsumoPresupuesto.cantidad` (el contador restante), no la original. Esto permite al solicitante saber cuánto queda disponible para pedir.

La columna **CANT. REQUERIDA** no puede superar el valor de CANTIDAD.

---

## 3. Vista: Requerimientos vs Atenciones

Vista informativa (solo lectura) que consolida el estado de cada insumo del presupuesto frente a los requerimientos del proyecto.

### Definición de columnas

| Columna | Fórmula / Fuente | Descripción |
|---------|-----------------|-------------|
| **PRESUPUESTADO** | `InsumoPresupuesto.cantidad_total` | Cantidad original del presupuesto. Solo informativo, nunca cambia. |
| **SOLICITADO** | Suma de `DetalleRequerimiento.cantidad_aprobada` donde `requerimiento.estado IN (APROBADO, PARCIAL, ATENDIDO)` | Lo que logística ha aprobado. Se activa al aprobar un requerimiento. |
| **ATENDIDO** | Suma de `DetalleGuia.cantidad` vinculadas al insumo | Lo que físicamente salió según las Guías de Remisión generadas. Se activa al generar una guía. |
| **SALDO** | `PRESUPUESTADO − ATENDIDO` | Cantidad presupuestada aún no despachada físicamente. |

**Regla de color del SALDO:**
- Negativo → rojo (se despachó más de lo presupuestado)
- Cero → verde
- Positivo → normal

### Estados incluidos en el consolidado

Solo se incluyen requerimientos en estados: `ENVIADO`, `EN_REVISION`, `APROBADO`, `PARCIAL`, `ATENDIDO`.
Los `BORRADOR` y `ANULADO` se excluyen.

---

## 4. Módulo Logística

### Flujo de aprobación de requerimientos

1. Jefe de Obra crea y envía requerimiento (estado → `ENVIADO`)
2. Logística abre el requerimiento (estado → `EN_REVISION`)
3. Logística ingresa cantidades aprobadas por ítem y guarda
4. Sistema ejecuta:
   - Revierte aprobación anterior si existía: `insumo.cantidad += cantidad_aprobada_anterior`
   - Guarda nuevas cantidades aprobadas: `det.cantidad_aprobada = aprobada`
   - Descuenta del contador: `insumo.cantidad = max(0, insumo.cantidad - aprobada)`
   - Cambia estado a `APROBADO` o `PARCIAL`
   - Auto-genera una **Guía de Remisión** con los ítems aprobados
5. La Guía de Remisión generada activa la columna **ATENDIDO** en Req vs Atenciones

### Regla de protección del contador

```python
insumo.cantidad = max(Decimal('0'), insumo.cantidad - aprobada)
```

El contador nunca puede volverse negativo, independientemente de cuántas veces se apruebe.

---

## 5. Roles y Acceso

### Visibilidad del sidebar por permiso

| Sección sidebar | Permiso requerido |
|----------------|-------------------|
| Presupuesto | `puede_ver_presupuesto` o `puede_editar_presupuesto` |
| Requerimientos | `puede_crear_requerimientos` o `puede_aprobar_requerimientos` |
| Almacén | `puede_ver_almacen` o `puede_gestionar_entradas` o `puede_gestionar_salidas` |
| Maquinaria / Cuadrilla | `puede_ver_maquinaria` o `puede_gestionar_maquinaria` |
| Logística (sección completa) | `puede_ver_logistica` |
| Administración | Al menos un permiso de administración |

### Superadmin

El rol `es_superadmin = True` bypasea todos los permisos. El usuario `is_superuser` de Django también tiene acceso total.

---

## 6. Pendientes / Decisiones futuras

- [ ] `DetalleGuia` debe recibir FK a `InsumoPresupuesto` para vincular guías con insumos (necesario para columna ATENDIDO en Req vs Atenciones)
- [ ] Revisar si `ATENDIDO` en el estado del requerimiento debe dispararse automáticamente al generar la guía o manualmente
