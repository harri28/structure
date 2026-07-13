# Reglas de Negocio — S&S Gestión

Documento de referencia para lógica de dominio, fórmulas y flujos del sistema.
No duplica el esquema de modelos — se enfoca en el **por qué** y el **cómo** de cada decisión.

---

## 1. Módulo Presupuesto

### Campos clave de `InsumoPresupuesto`

| Campo | Descripción | ¿Cambia? |
|-------|-------------|----------|
| `cantidad_total` | Cantidad original importada desde S10. Fuente de verdad permanente. | Nunca |
| `cantidad` | Contador restante. Se descuenta cuando se genera una Guía de Remisión (estado EN_TRANSITO). | Sí |
| `costo_unitario` | Precio unitario del insumo en el presupuesto. | No en operación |
| `total` | `cantidad_total × costo_unitario`. Importe total del insumo. | No en operación |

**Regla:** `cantidad` nunca puede bajar de 0. El sistema aplica `max(0, cantidad - aprobada)`.

**Restaurar contador:** En Superadmin → Proyecto → Restablecer → Logística, se ejecuta `cantidad = cantidad_total` para todos los insumos del proyecto.

### Importación de Presupuesto

- Se importa desde un archivo S10 PDF → XLSX (via `anlisis-pdf/pdf_a_xlsx.py`) o directamente XLSX genérico.
- La importación popula `Partida` (árbol hasta 5 niveles) e `InsumoPresupuesto`.
- `gastos_generales_pct`, `utilidad_pct`, `igv_pct` se guardan en el modelo `Presupuesto`.
- Fórmula de totales: `costo_directo → + GG% → + Utilidad% → sub_total → + IGV% → total_presupuesto`.

### Modificaciones

- Tipos: **Adicional** (aumenta presupuesto), **Deductivo** (reduce), **Vinculante** (reformulación sin cambio de monto).
- Cada modificación tiene sus propias `PartidaModificacion`.
- El monto vigente del proyecto = presupuesto original + suma de adicionales − suma de deductivos.

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
| `ENVIADO` | Enviado, pendiente de revisión. En logística se muestra como **"Nuevo"** |
| `EN_REVISION` | Logística lo abrió y está evaluando |
| `APROBADO` | Todas las cantidades aprobadas por logística |
| `PARCIAL` | Alguna cantidad aprobada fue menor a la requerida |
| `ATENDIDO` | Materiales físicamente entregados |
| `ANULADO` | Cancelado |

### Formulario de Requerimiento — columnas clave

| Columna | Fuente | Descripción |
|---------|--------|-------------|
| **CANTIDAD** | `InsumoPresupuesto.cantidad_total` | Cantidad original del presupuesto. Solo informativa, nunca cambia. No se resta ni suma. |
| **STOCK EN OBRA** | `InsumoPresupuesto.cantidad` | Contador restante disponible. Se descuenta cada vez que logística aprueba un requerimiento. |
| **CANT. REQUERIDA** | Ingresada por el usuario | No puede superar el valor de STOCK EN OBRA. |

**Regla:** La columna CANTIDAD es solo referencia presupuestada. El límite real para pedir es STOCK EN OBRA.

### Insumos duplicados en el formulario

El formulario bloquea seleccionar el mismo insumo más de una vez en el mismo requerimiento. Si el usuario intenta agregar un insumo que ya existe en otra fila, el campo se limpia y muestra "⚠ Insumo ya agregado en otra fila" por 2.5 segundos. La validación es solo del lado del cliente (JS).

### Envío desde la vista de detalle (BORRADOR → ENVIADO)

El botón "Enviar a Logística" en el detalle de un requerimiento BORRADOR usa el endpoint dedicado `POST /requerimientos/<pk>/enviar/`. Este endpoint solo actualiza el estado — no requiere reenviar el formulario completo. Esto evita el bug anterior donde el botón fallaba silenciosamente por validación de formulario incompleto.

---

## 3. Vista: Requerimientos vs Atenciones

Vista informativa (solo lectura) que consolida el estado de cada insumo del presupuesto frente a los requerimientos del proyecto.

### Definición de columnas

| Columna | Fórmula / Fuente | Descripción |
|---------|-----------------|-------------|
| **PRESUPUESTADO** | `InsumoPresupuesto.cantidad_total` | Cantidad original del presupuesto. Solo informativo, nunca cambia. |
| **SOLICITADO** | Suma de `DetalleRequerimiento.cantidad_aprobada` donde `requerimiento.estado IN (APROBADO, PARCIAL, ATENDIDO)` | Lo que logística aprobó. Se activa al hacer clic en "Aprobar requerimiento". |
| **ATENDIDO** | Suma de `DetalleRequerimiento.cantidad_aprobada` donde `requerimiento.estado = ATENDIDO` | Lo que ya fue despachado físicamente (guía generada). Se activa al hacer clic en "Guardar y generar guía". |
| **SALDO** | `PRESUPUESTADO − ATENDIDO` | Cantidad presupuestada aún no despachada. |

**Regla de color del SALDO:**
- Negativo → rojo (se despachó más de lo presupuestado)
- Cero → verde
- Positivo → normal

### Estados incluidos en el consolidado

Solo se incluyen requerimientos en estados: `ENVIADO`, `EN_REVISION`, `APROBADO`, `PARCIAL`, `ATENDIDO`.
Los `BORRADOR` y `ANULADO` se excluyen.

### Historial por insumo

Cada fila del consolidado con insumo vinculado es clickable. Al hacer clic abre `/vs-atenciones/insumo/<insumo_id>/` donde se listan todos los requerimientos que incluyeron ese insumo, con cantidad solicitada, cantidad aprobada y estado de cada uno. Permite ver cuántas veces se pidió un mismo insumo y cómo fue atendido parcial o completamente.

---

## 4. Módulo Logística

### Visualización de estado en lista

- El estado `ENVIADO` se muestra como **"Nuevo"** en la lista de logística (no "Enviado a logística").
- Los demás estados muestran su nombre normal (`get_estado_display`).

### Auto-transición al abrir un requerimiento

Cuando logística abre un requerimiento (ya sea desde la vista de detalle o desde la vista de revisión), si el estado es `ENVIADO`, el sistema lo cambia automáticamente a `EN_REVISION`. Esto ocurre en:
- `req_detalle_log` — vista de solo lectura
- `req_revisar_log` — vista de aprobación

### Flujo de aprobación de requerimientos

1. Jefe de Obra crea y envía requerimiento (estado → `ENVIADO`)
2. Logística abre el requerimiento (estado → `EN_REVISION` automáticamente)
3. Logística revisa los ítems. Puede:
   - Ajustar la cantidad a aprobar por ítem (entre 0 y la requerida)
   - **Eliminar** un ítem con justificación obligatoria (botón papelera → modal)
   - **Agregar** un insumo nuevo o sustituto (sección "Agregar / Cambiar insumo" al pie)
4. Pulsa "Aprobar requerimiento". El sistema ejecuta:
   - Guarda `cantidad_aprobada` por ítem; ítems eliminados quedan con `cantidad_aprobada = 0`
   - Registra en `HistorialRevisionReq` cada eliminación (acción `ELIMINAR`) y cada ítem nuevo (acción `AGREGAR`)
   - Crea los nuevos `DetalleRequerimiento` con `cantidad_aprobada = cantidad_requerida`
   - Determina estado: `APROBADO` si todas las aprobadas igualan las requeridas, `PARCIAL` si alguna es menor o hay eliminaciones
   - Elimina guías `PENDIENTE` previas del req (para evitar duplicados al re-aprobar)
   - Auto-genera una nueva **Guía de Remisión** en estado `PENDIENTE` con todos los ítems con `cantidad_aprobada > 0`
   - La guía queda vinculada al requerimiento vía FK `GuiaRemision.requerimiento`
   - Actualiza la columna **SOLICITADO** en Req vs Atenciones
5. **NO** se descuenta el contador de insumos en este momento

**No se requiere cotización** para aprobar un requerimiento.

### Historial de revisión logística

Modelo `HistorialRevisionReq` en `apps/requerimientos/models.py`. Registra cada vez que logística elimina o agrega un ítem durante la revisión.

| Campo | Descripción |
|-------|-------------|
| `requerimiento` | FK al requerimiento revisado |
| `accion` | `ELIMINAR` o `AGREGAR` |
| `insumo` | FK al insumo (nullable) |
| `descripcion` | Snapshot del nombre del insumo al momento del cambio |
| `cantidad` | Cantidad involucrada |
| `justificacion` | Texto libre obligatorio para ELIMINAR, opcional para AGREGAR |
| `usuario` | Quién hizo el cambio |
| `fecha` | Timestamp automático |

El historial es visible en:
- Vista de revisión de logística (`req_revisar.html`) — sección al pie del formulario
- Vista de detalle logística (`req_detalle.html`)
- Vista de detalle del jefe de obra (`requerimientos/detalle.html`)

### Flujo de generación de Guía de Remisión

1. Logística va a "Nueva Guía"
2. En el campo N° Guía aparece un dropdown con las guías en estado `PENDIENTE`
3. Al seleccionar una, sus bienes se cargan automáticamente debajo de "Datos del Transporte"
4. Logística completa los datos de transporte (transportista, placa, conductor, etc.)
5. Pulsa **"Guardar y generar guía"**
6. El sistema ejecuta:
   - Actualiza la guía `PENDIENTE` existente con los datos de transporte ingresados
   - Cambia estado: `PENDIENTE → EN_TRANSITO`
   - Descuenta del contador: `insumo.cantidad = max(0, insumo.cantidad - cantidad_aprobada)` por cada ítem
   - Cambia estado del requerimiento vinculado: → `ATENDIDO`
   - Actualiza la columna **ATENDIDO** en Req vs Atenciones
   - Crea un registro de **Entrada** en Almacén

### Numeración de Guías de Remisión auto-generadas

Formato: `GR-{año}-{correlativo 3 dígitos}`. Ejemplo: `GR-2025-001`.
El correlativo es por proyecto y por año; se incrementa sobre el último número existente con ese prefijo.

### Guías de Remisión — flujo en lista

- Columnas **Origen** y **Destino** separadas.
- Cada fila es clickable y abre la vista de impresión A4 en pestaña nueva (`/logistica/guia/<pk>/imprimir/`).
- Estados: `PENDIENTE` (amarillo) → `EN_TRANSITO` (azul) → `ENTREGADO` (verde) / `ANULADO` (rojo).

### Guías de Remisión — vista de impresión A4

Disponible en `/logistica/guia/<pk>/imprimir/`. Se abre en pestaña nueva. Contiene:
- **Cabecera**: logo de la empresa, razón social, RUC / título "Guía de Remisión" / N° guía y fechas.
- **Datos del Traslado**: origen, destino, observaciones.
- **Datos del Transporte**: transportista, placa, conductor, licencia, peso.
- **Bienes Trasladados**: tabla con descripción, unidad, cantidad.
- **Firmas**: Despachado por / Transportista / Recibido por.
- Botón "Imprimir / Guardar PDF" visible solo en pantalla (oculto al imprimir).
- También accesible desde el detalle de la guía con el botón **"Impresión"**.

### Regla de protección del contador

```python
insumo.cantidad = max(Decimal('0'), insumo.cantidad - cantidad_aprobada)
```

El contador nunca puede volverse negativo. El descuento ocurre al generar la guía (EN_TRANSITO), no al aprobar el requerimiento.

---

## 5. Módulo Configuración

### Datos del Consorcio

El formulario de configuración de empresa se llama **"Datos del Consorcio"** (no "Datos de la Empresa").

Campos activos del formulario:

| Campo | Descripción |
|-------|-------------|
| `razon_social` | Nombre legal del consorcio |
| `ruc` | RUC |
| `direccion` | Dirección fiscal |
| `telefono` | Teléfono de contacto |
| `email` | Correo de contacto |
| `logo` | Logo (PNG/JPG, máx. 2 MB) |

Campos eliminados del formulario (no aplican al flujo del consorcio): IGV, Sitio Web, Parámetros Financieros (moneda). Los precios vienen grabados con o sin IGV directamente desde los proveedores.

---

## 6. Roles y Acceso

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

## 7. Notificaciones

El icono de campana en el topbar muestra notificaciones del sistema. Al hacer clic, carga la lista via fetch (JSON). Cada notificación puede tener tipo: `info`, `success`, `warning`, `danger`.

**Estado actual:** El panel y el badge funcionan. Las notificaciones aún no están conectadas a eventos del sistema (no hay llamadas a `Notificacion.objects.create()` en el flujo operativo). Se habilitará cuando el sistema esté más maduro.

**SSE desactivado:** La actualización en tiempo real del badge (EventSource) está desactivada temporalmente por causar lentitud — cada pestaña abierta mantenía una conexión persistente consultando la DB cada 10s.

---

## 8. Servidor

- **Local (Windows):** Uvicorn ASGI (`servidor_asgi.py`), `workers=1` para evitar procesos zombie en Windows con Microsoft Store Python (`python3.12.exe`).
- **Producción (VPS):** Apache como reverse proxy en puerto 80 → Uvicorn en puerto 8000.
- **Comando para matar procesos en local:** `taskkill /IM python3.12.exe /F /T`

---

## 9. Pendientes / Decisiones futuras

- [ ] `DetalleGuia` debe recibir FK a `InsumoPresupuesto` para vincular guías con insumos (necesario para que la columna ATENDIDO en Req vs Atenciones se calcule correctamente)
- [ ] Revisar si el estado `ATENDIDO` del requerimiento debe dispararse automáticamente al generar la guía o manualmente
- [ ] Conectar `Notificacion.objects.create()` en eventos clave: aprobación de requerimiento, envío de requerimiento a logística
- [ ] Reactivar SSE de notificaciones una vez conectados los eventos
