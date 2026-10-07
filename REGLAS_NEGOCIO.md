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
BORRADOR → ENVIADO → EN_REVISION → APROBADO → COTIZADO → ATENDIDO
                                 → PARCIAL              → PARCIAL
                                 → ANULADO
```

| Estado | Descripción |
|--------|-------------|
| `BORRADOR` | Creado pero no enviado a logística |
| `SOLICITADO` | Reservado para el flujo Opción B (Almacenero → Admin de Obra, §10). No usado hoy. |
| `ENVIADO` | Enviado, pendiente de revisión. En logística se muestra como **"Nuevo"** |
| `EN_REVISION` | Logística lo abrió y está evaluando |
| `APROBADO` | Todas las cantidades aprobadas por logística |
| `COTIZADO` | Todas las cotizaciones APROBADAS cubren lo aprobado por ítem; aún no se emitió(aron) guía(s). Marcador intermedio entre APROBADO y ATENDIDO. Badge púrpura (`.bg-cotizado` en `main.css`). |
| `PARCIAL` | Dos semánticas convivientes: alguna cantidad aprobada fue menor a la requerida, O algo salió en guías pero no todo. |
| `ATENDIDO` | Materiales físicamente despachados (hay guías EN_TRANSITO/ENTREGADO que cubren todo lo aprobado por ítem) |
| `ANULADO` | Cancelado |

El estado se recalcula automáticamente (helper `_recalcular_estado_req` en `apps/logistica/views.py`) al: aprobar cotización, eliminar cotización APROBADA, rechazar cotización, emitir guía, anular guía. Prioridad: `ATENDIDO` > `PARCIAL` > `COTIZADO` > `APROBADO`.

### Formulario de Requerimiento — columnas clave

| Columna | Fuente | Descripción |
|---------|--------|-------------|
| **CANTIDAD** | `InsumoPresupuesto.cantidad_total` | Cantidad original del presupuesto. Solo informativa, nunca cambia. No se resta ni suma. |
| **STOCK EN OBRA** | `InsumoPresupuesto.cantidad` | **Cupo restante del presupuesto**, no stock físico. Se descuenta al generar la Guía de Remisión (EN_TRANSITO), no al aprobar el requerimiento. Ver §11 para la distinción con el stock físico del almacén. |
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
| **SOLICITADO** | Suma de `DetalleRequerimiento.cantidad_aprobada` donde `requerimiento.estado IN (APROBADO, COTIZADO, PARCIAL, ATENDIDO)` | Lo que logística aprobó. Se activa al hacer clic en "Aprobar requerimiento". |
| **ATENDIDO** | Suma de `DetalleRequerimiento.cantidad_aprobada` donde `requerimiento.estado = ATENDIDO` | Lo que ya fue despachado físicamente (guía generada). Se activa al hacer clic en "Guardar y generar guía". |
| **SALDO** | `PRESUPUESTADO − ATENDIDO` | Cantidad presupuestada aún no despachada. |

**Regla de color del SALDO:**
- Negativo → rojo (se despachó más de lo presupuestado)
- Cero → verde
- Positivo → normal

### Estados incluidos en el consolidado

Solo se incluyen requerimientos en estados: `ENVIADO`, `EN_REVISION`, `APROBADO`, `COTIZADO`, `PARCIAL`, `ATENDIDO`.
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
   - Elimina guías `PENDIENTE` heredadas del req (flujo anterior; ya **no** se genera ninguna guía al aprobar)
   - Actualiza la columna **SOLICITADO** en Req vs Atenciones
5. **NO** se descuenta el contador de insumos en este momento

**No se requiere cotización** para aprobar un requerimiento.

### Columna "Aprobado" por ítem (vista Revisión del REQ)

En la tabla "Cantidades a aprobar" de `req_revisar.html`, además de `Cant. requerida` y `Cant. a aprobar`, aparece una columna informativa **"Aprobado"** por ítem. Es la suma de `DetalleCotizacion.cantidad` sobre cotizaciones APROBADAS del REQ para ese insumo (helper `_clave_item_cot` del almacén). Colores:
- Verde con ícono `✓` → cubre o supera el objetivo (`cantidad_aprobada` o `cantidad_requerida`).
- Naranja → cubierto parcialmente.
- "—" en gris → sin cotizaciones aprobadas.

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

### Flujo completo de cotizaciones (crear / editar / aprobar / rechazar)

Las cotizaciones viven en `apps/almacen` pero su flujo operativo lo maneja Logística.

#### Crear cotización desde el REQ (modal "Crear Cotizaciones" / "Generar cotización")

Desde la vista de Revisión del REQ (`req_revisar.html`), el botón "Crear Cotizaciones" (si ya hay otras) o "Generar cotización" (si es la primera) abre el modal `#modal-cotizar`. Características:

- **Título del modal** con badge del próximo N° COT (previsualización, no editable).
- **Datos del proveedor** (opcionales): razón social, RUC/DNI, dirección, teléfono.
- **Buscador SUNAT/RENIEC** al lado del input RUC/DNI (lupa azul) → reusa el endpoint `maquinaria:consulta_doc` (Factiliza). Autocompleta razón social + dirección.
- **Tabla de ítems** del REQ con saldo cotizable restante > 0 cada uno:
  - Columna "Cantidad" editable, tope en el saldo cotizable (`min(cantidad_aprobada, saldo)`).
  - Columna "Saldo" informativa.
  - Botón "Quitar" por fila (JS); el reset del modal (`show.bs.modal`) restaura la tabla al estado inicial.
- Al confirmar, `cot_desde_req` crea la cotización en `PENDIENTE` y **redirige al REQ** (no al detalle de la COT). La COT aparece en el bloque "Cotizaciones generadas" del REQ.

#### Aprobación de la cotización — edición inline en el detalle

En `cot_detalle.html`, cuando la cotización está en `PENDIENTE`:

- La tabla "Materiales Cotizados" es **editable inline**: cantidad (`≤ solicitada`, no se puede subir) + **precio unitario obligatorio**.
- Subtotales y total se recalculan en vivo con JS.
- Botón **papelera** por fila → marca el ítem para eliminar al confirmar (`eliminar_<pk>=1`).
- Botón **"Aprobar cotización"** (verde) = submit del form que persiste cantidades y precios, elimina los marcados y pasa la COT a `APROBADA`.
- Botón **"Rechazar cotización"** (rojo) abre un modal de confirmación que llama a `cot_rechazar`.
- Botón experimental **"Ver cotización"** (ícono ojo) abre un offcanvas lateral derecho con los datos del proveedor y las cantidades cotizadas tal como están persistidas — sirve de referencia mientras aprobás. Bloque marcado con `{% comment %}EXPERIMENTAL{% endcomment %}` para que se pueda remover fácil.

Reglas del `cot_aprobar`:
- `cantidad > 0`, `cantidad ≤ cantidad_actual_del_detalle` (no se puede subir).
- `precio_unitario > 0` obligatorio.
- Si quedan 0 ítems → bloquea con mensaje pidiendo usar Rechazar.
- **Validación cruzada de saldo**: `Σ cantidades por aprobar en ESTA COT + Σ ya aprobadas en OTRAS COT del mismo REQ ≤ cantidad_aprobada del detalle del REQ`. Si falla, bloquea con mensaje tipo *"<ítem>: cantidad X supera el saldo cotizable (Y)."*.
- Tras aprobar, llama a `_recalcular_estado_req` → el REQ puede pasar a `COTIZADO` si todas las cotizaciones aprobadas cubren todo lo aprobado por ítem.

`cot_rechazar` (nuevo): pasa la COT a `RECHAZADA` y recalcula el REQ. Como las RECHAZADAS no cuentan en el saldo cotizable, todo el saldo vuelve al REQ.

En `APROBADA`/`RECHAZADA` la tabla se muestra como **texto fijo** (sin inputs).

#### Numeración de cotizaciones

Formato: espeja el N° del REQ. Primera COT del REQ001 → `COT001`. Segunda → `COT001-2`. Tercera → `COT001-3`. Etc. (Ver `cot_desde_req` en `apps/almacen/views.py`.) Lógica implementada hace tiempo (commits `881b1ed`, `5916573`) — se mantiene vigente. La vista `_siguiente_numero_cot` también existe para cotizaciones libres sin REQ (correlativo global del proyecto), usada por `cot_crear` y `cot_rapida`.

#### Validación de saldo cotizable (en 4 puntos)

El saldo cotizable por ítem del REQ es:

```
saldo = DetalleRequerimiento.cantidad_aprobada
      − Σ DetalleCotizacion.cantidad en cotizaciones APROBADAS del mismo REQ
```

Las COT `PENDIENTE` y `RECHAZADA` **no** se cuentan (así se pueden tener varias cotizaciones en PENDIENTE de distintos proveedores por el mismo saldo, para elegir cuál aprobás).

Helpers: `_saldo_cotizable(req, excluir_cot_pk)` y `_errores_contra_saldo(req, items, excluir_cot_pk)` en `apps/almacen/views.py`.

Validación aplicada en:

| Vista | Qué valida |
|---|---|
| `cot_desde_req` | Al crear la cotización, cada ítem no supera el saldo del REQ. |
| `cot_crear` | Idem si tiene `requerimiento_origen`. |
| `cot_editar` | Idem (excluyendo esta misma COT del cálculo). |
| `cot_aprobar` | Validación cruzada al aprobar (ver arriba). |

**Nota**: la validación es **por REQ**, no global por insumo. Un insumo puede estar en 2 REQs distintos y cada REQ tiene su cuenta independiente de cotizaciones. El control global del insumo se hace recién al emitir guía (ver sección siguiente).

#### Lista de cotizaciones (`cot_lista`)

- Agrupada por REQ de origen (plegable) + grupo "Sin requerimiento".
- Columnas: `N° COT · Fecha · Proveedor · Insumos (badge con count) · Estado (text-end) · Total · acciones`.
- Buscador live por N° COT, proveedor, REQ, códigos y descripciones de insumos.
- El botón "Registrar Cotización" fue removido del header (el modal `#modalCotRapida` queda en el HTML por si se reactiva).

### Flujo de generación de Guía de Remisión (por cotizaciones aprobadas)

La guía ya **no** nace del requerimiento: sale de una o varias **cotizaciones aprobadas**.

1. Una cotización pasa a `APROBADA` con el botón **Aprobar cotización** (detalle o lista de cotizaciones).
2. Logística va a "Nueva Guía". El **N° de guía** (`GR-{año}-{correlativo 3 dígitos}`, por proyecto y año) y la **fecha de emisión** (hoy) son automáticos: se muestran como texto y el servidor los fuerza al guardar.
3. En **N° de Cotización Aprobada** busca y agrega **una o varias** cotizaciones del proyecto. Solo aparecen las `APROBADA` que no viajan ya en una guía activa (`PENDIENTE`/`EN_TRANSITO`/`ENTREGADO`). Sus ítems se cargan en "Bienes a trasladar" (solo lectura).
4. Completa los datos de transporte y la fecha de traslado, y pulsa **"Guardar y generar guía"**.
5. El sistema ejecuta, en una sola transacción:
   - Crea la guía directamente en `EN_TRANSITO` y la liga a las cotizaciones (`GuiaRemision.cotizaciones`, M2M).
   - Copia los ítems de las cotizaciones a `DetalleGuia`.
   - Descuenta del contador, **solo para los ítems ligados a un insumo del presupuesto**: `insumo.cantidad = max(0, insumo.cantidad - cantidad_del_ítem_en_la_cotización)`. Los ítems sin insumo no descuentan.
   - Recalcula el estado de cada requerimiento de origen (ver abajo).
6. La Entrada en Almacén **no** se crea automáticamente: la registra el Almacenero desde Almacén → Guías.

**Una cotización solo puede despacharse una vez.** Si la guía se **anula** (desde el detalle) o se **elimina**, el stock descontado se devuelve (sin pasar de `cantidad_total`), la cotización vuelve a estar disponible y se recalcula el requerimiento. Una guía anulada con cotizaciones **no se puede reactivar**: se genera una nueva.

#### Estado del requerimiento según cotizaciones y despachos

Se compara, por insumo (o por descripción si el ítem no tiene insumo), la `cantidad_aprobada` del requerimiento contra:
- `despachado` = suma de `DetalleCotizacion.cantidad` cuya cotización está `APROBADA` **y** en una guía `EN_TRANSITO`/`ENTREGADO`.
- `cotizado` = suma de `DetalleCotizacion.cantidad` cuya cotización está `APROBADA` (sin importar si tiene guía).

Reglas (helper `_recalcular_estado_req`):

| Situación | Estado |
|-----------|--------|
| `despachado` cubre todo lo aprobado | `ATENDIDO` |
| `despachado > 0` pero falta | `PARCIAL` (Atendido Parcial) |
| `cotizado` cubre todo pero aún no hay guías | `COTIZADO` |
| Nada cotizado o parcial sin despacho | `APROBADO` (o `PARCIAL` si se aprobó menos de lo requerido) |

Por eso `PARCIAL` significa dos cosas: aprobado con menos cantidad, o despachado a medias. La pestaña **Por atender** (Logística → Ingreso de Requerimientos) lista los requerimientos en `PARCIAL`.

La anulación de un requerimiento también se bloquea si alguna de sus cotizaciones viaja en una guía `EN_TRANSITO`/`ENTREGADO`.

### Numeración de Guías de Remisión

Formato: `GR-{año}-{correlativo 3 dígitos}`. Ejemplo: `GR-2026-001`.
El correlativo es por proyecto y por año; se toma el mayor número existente con ese prefijo y se suma 1.

### Guías de Remisión — flujo en lista

- **Lista unificada** (una sola tabla, sin pestañas). Se removieron las chips "En cola / Enviados" — todas las guías del proyecto aparecen juntas, el estado se distingue por el badge de la columna "Estado".
- Columnas **Origen** y **Destino** separadas.
- Cada fila es clickable y abre la vista de impresión A4 en pestaña nueva (`/logistica/guia/<pk>/imprimir/`).
- Estados: `PENDIENTE` (amarillo) → `EN_TRANSITO` (azul) → `ENTREGADO` (verde) / `ANULADO` (rojo).

### Botón "← Ingreso de Requerimientos" removido en sub-pestañas

En las vistas de Logística → Ingreso de Requerimientos, las sub-pestañas (`Por atender`, `R. Consolidados`, `Anulados`, `Historial`) ya no muestran el botón "← Ingreso de Requerimientos" al tope. La navegación hacia la pantalla principal se cubre con el breadcrumb y las chips de pestañas.

El banner `alert-info` ("Este requerimiento ya fue aprobado/atendido/anulado...") en la vista de Revisión también fue removido. El estado se refleja en el badge del título.

### Vista de impresión de cotización (`cot_imprimir`)

- Datos del proveedor pre-populados con los que se cargaron al generar la cotización (razón social, RUC/DNI, dirección, teléfono).
- Columna "Cantidad" en texto fijo (ya no es input editable). El valor viene de `DetalleCotizacion.cantidad` persistido.
- Se removieron del header del detalle de cotización los botones "Imprimir A4", "Editar", "Eliminar" (ya no se usan en el flujo nuevo).

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

Ver `arquitectura_structure.md` para el detalle completo del modelo RBAC (mapeo
de permisos, dashboards por rol, enforcement con `@requiere`). Esta sección
resume solo las reglas de dominio.

### Los cuatro roles del sistema

**Aclaración semántica clave:** "Administrador de Obra" ≠ "Administrador del sistema".
En términos de ingeniería civil, el Admin de Obra es el **residente**: puede
haber varios en el sistema, cada uno en su propio proyecto. El "admin del
sistema" es el Superadmin.

Otra distinción a no confundir: **Personal ≠ Usuarios**. "Personal" son los
obreros y cuadrillas del proyecto (no ingresan al sistema). "Usuarios" son
las cuentas que sí ingresan (hoy 3: Admin de Obra, Logística, Almacenero).

| Rol | Rol en la vida real | Alcance |
|---|---|---|
| Superadmin | Programador / dueño del sistema | Todo el consorcio, todos los proyectos |
| Administrador de Obra | Residente de obra | Un proyecto (puede haber varios residentes en distintos proyectos) |
| Logística | Área de logística del consorcio | Atraviesa proyectos |
| Almacenero | Operador de almacén de un proyecto | Un proyecto |

### Visibilidad del sidebar por permiso

| Sección sidebar | Permiso requerido |
|----------------|-------------------|
| Presupuesto | `puede_ver_presupuesto` o `puede_editar_presupuesto` |
| Requerimientos | `puede_crear_requerimientos` o `puede_aprobar_requerimientos` |
| Almacén | `puede_ver_almacen` o `puede_gestionar_entradas` o `puede_gestionar_salidas` |
| Maquinaria / Cuadrilla | `puede_ver_maquinaria` o `puede_gestionar_maquinaria` |
| Personal | `puede_gestionar_personal` *(por crear — hoy usa `puede_crear_proyectos or puede_administrar_usuarios`)* |
| Actividad | `puede_ver_actividad` *(por crear — hoy usa `puede_administrar_usuarios`)* |
| Logística (sección completa) | `puede_ver_logistica` |
| Administración | Al menos un permiso de administración |

### Superadmin

El rol `es_superadmin = True` bypasea todos los permisos. El usuario
`is_superuser` de Django también tiene acceso total.

---

## 7. Notificaciones

El icono de campana en el topbar muestra notificaciones del sistema. Al hacer clic, carga la lista via fetch (JSON). Cada notificación puede tener tipo: `info`, `success`, `warning`, `danger`.

**Estado actual (2026-08-02):** El panel y el badge funcionan. Las notificaciones **sí están conectadas** a eventos del sistema — hay ~13 llamadas a `notificar()` en `requerimientos`, `logistica`, `almacen` y `presupuesto` (verificar con `grep -rn "notificar(" apps/`).

**SSE desactivado (huérfano):** El endpoint `registro:notif_stream` existe pero no hay ningún `EventSource` en los templates. La campana carga con `fetch` a `notif_json` al hacer clic, no en tiempo real. Se desactivó por lentitud — cada pestaña abierta mantenía una conexión persistente consultando la DB cada 10 s. **No reactivar** sin motivo explícito.

---

## 8. Servidor

- **Local (Windows):** Uvicorn ASGI (`servidor_asgi.py`), `workers=1` para evitar procesos zombie en Windows con Microsoft Store Python (`python3.12.exe`).
- **Producción (VPS):** Apache como reverse proxy en puerto 80 → Uvicorn en puerto 8000.
- **Comando para matar procesos en local:** `taskkill /IM python3.12.exe /F /T`

---

## 9. Pendientes / Decisiones futuras

**Pendientes originales:**
- [ ] `DetalleGuia` debe recibir FK a `InsumoPresupuesto` para vincular guías con insumos (necesario para que la columna ATENDIDO en Req vs Atenciones se calcule correctamente)
- [ ] Revisar si el estado `ATENDIDO` del requerimiento debe dispararse automáticamente al generar la guía o manualmente
- [x] ~~Conectar `Notificacion.objects.create()` en eventos clave~~ — hecho (ver §7)
- [ ] Reactivar SSE de notificaciones — desestimado por ahora (ver §7)

**Pendientes de RBAC (2026-08-02, ver `arquitectura_structure.md` para detalle):**
- [ ] Migración: agregar `puede_gestionar_personal` y `puede_ver_actividad` al modelo `Rol`
- [ ] Decidir qué hacer con el link "Configuración" en el sidebar del Admin de Obra (opción a/b/c)
- [ ] Crear los 3 roles en la BD con el mapeo definido
- [ ] Implementar la Opción B para requerimientos (Almacenero → Admin de Obra) — ver §10
- [ ] Decorar los módulos restantes con `@requiere`: `almacen`, `maquinaria`, `proyectos`, `catalogo`, `registro`
- [ ] Cablear `proyectos_visibles()` en las vistas que reciben `proyecto_id` (aislamiento entre proyectos)

**Decisiones de flujo confirmadas (2026-08-02):**
- [x] Nombre del estado: `SOLICITADO` (label "Solicitado por Almacén")
- [x] Formulario del Almacenero: opción A — ve el cupo restante del presupuesto (`InsumoPresupuesto.cantidad`), con validación estricta (no puede pedir más que el cupo)

**Decisiones confirmadas (2026-08-02, continuación):**
- [x] Link "Configuración" del sidebar del Admin de Obra: **opción B** — crear
  un módulo nuevo `configuracion:proyecto` para editar el proyecto activo
  (nombre, fechas, presupuesto, etc.). Ver §13.
- [x] Sobre-solicitud (excedente): NO genera `Modificacion` automática, sí
  requiere justificación, se muestra en rojo en pantalla separada. Ver §12.
- [x] Creación de los 3 roles en la BD: por migración (data migration Django),
  no manual desde el UI. Motivo: el usuario aún no tiene usuario Almacenero
  y necesita los roles ya sembrados para pruebas.

**Campo nuevo `stock_almacen` en `InsumoPresupuesto`:**

*Fase 1 — el campo (a agregar ya, junto con el ciclo actual):*
- [ ] Agregar `stock_almacen = DecimalField(max_digits=18, decimal_places=4, default=0)`
  al modelo `InsumoPresupuesto`
- [ ] Migración: los insumos existentes quedan con `stock_almacen=0`
  (comportamiento correcto — el almacén parte vacío)
- [ ] Verificar que el importador (`apps/presupuesto/importador.py`) no
  necesita cambios (el default 0 alcanza)

*Fase 2 — lógica de actualización (pendiente, se decide cuando se necesite):*
- [ ] Definir cuándo/cómo se actualiza el contador (probablemente al aprobar
  Entradas y al registrar Salidas, pero pendiente de confirmar)
- [ ] Función utilitaria de recálculo si se necesita
- [ ] Uso en vistas (Req vs Atenciones, dashboards, etc.)

Motivo: el usuario necesita el campo persistido ahora para poder usarlo más
adelante en varias vistas. La lógica de actualización se define cuando se toque
cada uno de esos usos, sin bloquear la creación del campo.

Ver §11 para la distinción con `cantidad` (cupo del presupuesto).

**Sistema de trazabilidad de materiales (pendiente — no en este ciclo):**
- [ ] Diseñar e implementar un sistema tipo "blockchain" (append-only, no reescribir)
  para seguir un material desde que se solicita (por Admin de Obra o Almacenero)
  hasta que llega físicamente al almacén.
- Consideraciones:
  - Un mismo material puede tener varios requerimientos activos en distintos momentos.
  - La traza debe unir: origen del pedido (rol + usuario + fecha) → aprobaciones
    intermedias → guía de remisión → llegada al almacén.
  - Reutilizar `HistorialRevisionReq` (ya existente) donde sea posible; extender
    con eventos nuevos si hace falta.
- Decisión: NO se aborda en el ciclo actual de RBAC. Se levantará como bloque
  aparte cuando se estabilice el enforcement y los 3 roles estén en producción.

---

## 10. Flujo Almacenero → Admin de Obra → Logística (Opción B — pendiente de implementar)

Ver `arquitectura_structure.md §3` para el fundamento del diseño. Esta sección
documenta las reglas de dominio del flujo cuando se implemente.

### Ciclo completo del material

```
Almacenero pide (su bandeja)
    │ Envía (sin borrador, un solo acto)
    ▼
Estado nuevo: SOLICITADO (label "Solicitado por Almacén")
    │
    ▼
Admin de Obra (bandeja de entrada — vista nueva)
    │ Aprueba (puede editar cantidades, insumos, agregar/quitar)
    ▼
Estado: ENVIADO (idéntico al flujo actual del Admin de Obra)
    │
    ▼
Logística (bandeja actual, sin cambios)
    │ Revisa, aprueba, genera Guía de Remisión
    ▼
Guía en EN_TRANSITO → descuenta contadores, crea Entrada en almacén
    │
    ▼
Almacenero recibe (bandeja de Entradas) → aprueba la llegada ✓ ciclo cerrado
```

### Reglas del formulario del Almacenero

- Formulario **atómico**: se envía o se cancela. No existe "guardar como borrador".
- La palabra "borrador" no aparece en la UI del Almacenero.
- Muestra la lista de `InsumoPresupuesto` del proyecto (mismo autocompletado que
  el Admin de Obra hoy).
- Stock visible: **pendiente de decidir** (ver §11 y §9).

### Reglas de la bandeja del Admin de Obra

- Vista nueva "Bandeja de Entrada" — lista los requerimientos con estado
  `SOLICITADO` del proyecto activo.
- El Admin de Obra tiene **poder total** sobre el requerimiento recibido:
  puede cambiar cantidades, agregar insumos, quitar insumos, cambiar materiales.
  Es el residente y tiene el mayor peso sobre el proyecto.
- Al aprobar → `SOLICITADO → ENVIADO` (se une al flujo normal a Logística).
- **No existe "rechazar":** si el Admin de Obra decide no aprobar, el
  requerimiento simplemente se queda en `SOLICITADO`. No hay devolución
  con motivo.

### Independencia con el flujo del Admin de Obra

Los propios requerimientos del Admin de Obra (creados por él, no por el
Almacenero) siguen su flujo actual sin cambios: `BORRADOR → ENVIADO → …`.
La Opción B solo agrega el camino paralelo desde el Almacenero.

---

## 11. Dos contadores distintos: cupo del presupuesto vs stock físico

Uno de los errores más frecuentes al leer este sistema es confundir estos dos
conceptos. Son distintos y ambos válidos.

| Concepto | Qué representa | Dónde vive | Empieza en | Cuándo cambia |
|---|---|---|---|---|
| **Cupo restante del presupuesto** | Cuánto se puede aún **pedir** a Logística de un insumo dado | `InsumoPresupuesto.cantidad` | `cantidad_total` (lo que trajo el S10) | Baja al pasar guía a EN_TRANSITO |
| **Stock físico del almacén** | Cuánto material **realmente está** en el galpón ahora mismo | Calculado: `sum(Entrada.cantidad) - sum(Salida.cantidad)` por insumo | 0 | Sube con Entradas aprobadas, baja con Salidas |

**Ejemplo con 10 abrazaderas:**

| Paso | `cantidad_total` | `cantidad` (cupo) | Stock físico |
|---|---|---|---|
| Importación S10 | 10 | 10 | 0 |
| Admin pide 10, Logística aprueba 5, genera guía | 10 | 5 | 0 |
| Almacenero aprueba la Entrada | 10 | 5 | **5** |
| Salida de 3 a una cuadrilla | 10 | 5 | 2 |

**Consecuencia crítica:** al importar el presupuesto NO pasan automáticamente
10 abrazaderas al almacén. El almacén empieza vacío y solo aparece material
cuando físicamente llega (vía guía de remisión aprobada).

**Regla de protección:** `cantidad` nunca puede volverse negativo. El descuento
al despachar usa `max(Decimal('0'), cantidad - cantidad_aprobada)`.

---

## 12. Sobre-solicitud (excedente del presupuesto) — solo Admin de Obra

**Regla base (aplica al Almacenero y al Admin de Obra por defecto):** en el
formulario normal de requerimiento, la cantidad pedida por insumo no puede
superar `InsumoPresupuesto.cantidad` (el cupo restante del presupuesto).

**Excepción — Admin de Obra puede exceder:** el Admin de Obra tiene una vía
especial para solicitar por encima del presupuesto. Ejemplo: presupuesto de
10 abrazaderas ya despachadas, pero necesita 2 más → puede pedirlas.

**IMPORTANTE — No confundir con `Modificacion` tipo Adicional.** El sistema
tiene `Modificacion` (Adicionales / Deductivos / Vinculantes) pero eso aplica
a **partidas** del presupuesto, no a insumos. Aunque comparte el nombre
"Adicional", la sobre-solicitud de insumos es una cosa distinta y **NO** debe
generar automáticamente un `Modificacion` en la BD.

**Reglas de dominio confirmadas (a implementar en un ciclo futuro):**
- La sobre-solicitud vive en **una pantalla distinta** del formulario normal
  (no se mezcla con el pedido regular).
- Es una vía **exclusiva del Admin de Obra**. Almacenero y otros no la ven.
- El formulario **exige un campo de justificación** al solicitar el excedente
  (obligatorio, no opcional).
- La cantidad excedente debe mostrarse **en rojo** para señalar visualmente
  que rebasa el presupuesto.
- Debe haber una **pantalla / vista aparte** que liste los excedentes por
  proyecto e insumo, para consultarlos después.
- **NO** se crea `Modificacion` automáticamente. El excedente es un registro
  informativo asociado al requerimiento; el ajuste formal del presupuesto
  (si se decide hacer) es un acto separado del Admin de Obra.

**Preguntas de diseño abiertas (por decidir cuando se implemente):**
- ¿Requiere aprobación adicional del Superadmin, o el Admin de Obra decide
  por su cuenta con la justificación registrada?
- ¿Cómo se estructura el reporte de excedentes: por insumo, por proyecto,
  por período, todo lo anterior?

**No en este ciclo.** El excedente se implementa después del flujo base
Almacenero → Admin de Obra → Logística.

---

## 13. Módulo "Configuración del Proyecto" (por crear)

Módulo nuevo dedicado al Administrador de Obra para configurar los datos de
**su proyecto activo**. No confundir con `configuracion:hub` (que es la
configuración GLOBAL del consorcio: Empresa, SUNAT, Unidades, Usuarios,
Roles — exclusivo del Superadmin).

**Ámbito de este módulo (según lo definido):**
- Nombre del proyecto
- Fechas del proyecto
- Presupuesto (parámetros — GG%, Utilidad%, IGV%, etc.)
- Otros parámetros propios del proyecto (por definir a medida que aparezcan)

**Reglas:**
- Solo visible/accesible al **Admin de Obra** del proyecto activo.
- Opera sobre `Proyecto` (y posiblemente `Presupuesto`) del proyecto activo
  en sesión (`request.session['proyecto_id']`).
- Requiere un permiso nuevo, propuesta: `puede_configurar_proyecto`.
- URL propuesta: `/proyecto/<pk>/configuracion/` o namespace nuevo
  `configuracion_proyecto:*`.

**Preguntas de diseño abiertas (a resolver cuando se implemente):**
- ¿Qué campos exactos van en cada sección (datos generales, presupuesto,
  fechas, personal responsable)?
- ¿Editar el `Presupuesto` desde aquí implica poder cambiar `gastos_generales_pct`,
  `utilidad_pct`, `igv_pct`? ¿Solo esos o hay otros?
- ¿El Admin de Obra puede editar el `codigo` del proyecto o solo el `nombre`?
- ¿El link "Configuración" del sidebar apunta directo a esta pantalla nueva,
  o hay un sub-menú?

**No en este ciclo.** Este módulo se diseña e implementa después del flujo
base de RBAC y del flujo Opción B.

---

## 14. Ajustes / Adicionales de Requerimiento (implementado parcialmente)

**Implementado (2026-08-04):**
- Nuevo chip **"Ajustes"** en la vista `requerimientos:lista` (Admin de Obra).
- Vista `requerimientos:ajustes` — lista requerimientos con `es_ajuste=True`
  filtrados aparte de los regulares.
- Vista `requerimientos:crear?ajuste=1` — form de creación en modo Ajuste:
  - Bandera roja en el título, banner de advertencia.
  - `DetalleRequerimientoForm` recibe `modo_ajuste=True` vía `form_kwargs` del
    formset, y en `clean()` **NO** valida `cant_requerida > cantidad_presupuestada`.
  - Al guardar, `Requerimiento.es_ajuste = True`.
- Campo nuevo `Requerimiento.es_ajuste = BooleanField(default=False)`
  (migración `0013_requerimiento_es_ajuste`).
- Filtro: `requerimientos:lista` excluye `es_ajuste=True` para no mezclarlos.
- Bloqueo del botón "Enviar a Logística" en el flujo NORMAL cuando algún ítem
  excede lo presupuestado (JS detecta `.cant-req-error` visible → deshabilita
  botón con tooltip: "Uno o más ítems exceden el presupuesto. Usá el chip
  Ajustes para adicionales.").

**NO implementado — pendiente contable / presupuestal:**
- No se crea automáticamente una `Modificacion` de tipo Adicional en el
  presupuesto cuando se registra un Ajuste. El impacto formal en el `Presupuesto`
  (subir `cantidad_total` del insumo, generar registro contable de pérdida,
  aumentar `costo_directo`) queda como **decisión gerencial separada**.
- El Ajuste actual es un registro **informativo** que documenta la sobre-solicitud
  y permite operativamente pedir el material a Logística. No modifica el
  contrato ni el presupuesto vinculante.
- Cuando se implemente el flujo contable, el enlace natural sería:
  `Requerimiento(es_ajuste=True)` → `Modificacion` (tipo Adicional) →
  `PartidaModificacion` con el insumo excedente.

**Relación con §12 (Sobre-solicitud):** este mecanismo cumple con lo especificado
en §12 (pantalla aparte, marcado en rojo, no genera `Modificacion` automática).
La justificación obligatoria por ítem mencionada en §12 aún NO está enforced
en el form de Ajuste — queda como refinamiento futuro.

---

## 15. Renumeración de códigos de insumo (S10 → enteros amigables)

**Regla:** al importar un presupuesto desde S10 o Excel, el sistema **NO** conserva
los códigos crudos que trae el archivo (que suelen ser identificadores largos e
ilegibles tipo `10000201`, `1120939202`, `4567890123`). En su lugar reemplaza
esos códigos por **enteros amigables secuenciales** empezando en 1 dentro de
cada grupo — por ejemplo:

- Materiales: `1, 2, 3, 4, ...`
- Mano de obra: `1, 2, 3, ...`
- Equipos: `1, 2, 3, ...`
- Subpartidas: `1, 2, 3, ...`

**Por qué:** la finalidad es que el usuario final (Almacenero, Admin de Obra,
Logística) pueda referirse a un insumo por un número corto y memorable en vez
de un identificador extraído del software original.

**Consecuencia esperada — códigos duplicados entre grupos:** dado que la
numeración es **por grupo** (cada grupo empieza en 1), es normal que el código
`1` exista para un material (por ejemplo "Cemento Portland") **y también** para
una máquina, mano de obra, etc. La UI actual **no diferencia** el grupo del
insumo por el código, lo que puede resultar confuso — es un tema pendiente
de arreglar (probablemente prefijando el grupo: `M-1`, `MO-1`, `E-1`, `SP-1`).

**Impacto en la BD:** el campo `InsumoPresupuesto.codigo` es un `CharField`,
pero los valores almacenados son enteros como texto (`"1"`, `"2"`, ..., `"100"`).
Para ordenar numéricamente hace falta CAST a entero:

```python
from django.db.models import IntegerField
from django.db.models.functions import Cast
qs.annotate(_codigo_int=Cast('codigo', IntegerField())).order_by('_codigo_int')
```

Sin el CAST, PostgreSQL ordena lexicográficamente y da `1, 10, 100, 11, 2, 20, ...`
(implementado en el sort del Stock de Almacén — `apps/almacen/views.py::STOCK_ORDER_MAP`).

**Ubicación de la lógica de renumeración:** en el importador (`apps/presupuesto/importador.py`).

**Pendientes conocidos (por resolver en otro ciclo):**
- Diferenciar visualmente los códigos de distintos grupos (prefijo o badge).
- Definir qué pasa si el usuario intenta buscar "1" en el buscador global —
  ¿ambigüedad? ¿desambiguar por grupo?

---

## 16. Flujo Logística → Almacén: recepción manual con validación

**Implementado (2026-08-05):**

### Ciclo actual
1. **Logística** hace click en "Guardar y Generar guía" → guía pasa a `EN_TRANSITO`,
   se descuenta el stock del `InsumoPresupuesto`, el REQ pasa a `ATENDIDO`.
2. **NO se crea automáticamente una Entrada en Almacén** — se removió el
   `_registrar_entrada_almacen` del `guia_crear`. La Entrada nace únicamente
   por acción manual del Almacenero.
3. Se dispara una notificación `"Nueva Guía GR-XXX"` con URL a
   `/almacen/proyecto/N/guias/` (buzón de recepción del Almacén).
4. **Almacén → Guías** (sub-módulo nuevo) muestra las guías EN_TRANSITO/ENTREGADO
   con fondo verde suave + badge "NUEVA" para las no vistas
   (`GuiaRemision.vista_por_almacen`, `BooleanField default=False`, migración
   `logistica/0003`). Al abrir el detalle, se marca vista=True.
5. **Detalle readonly** (`guia_almacen_detalle`) muestra datos e ítems no
   editables. Botón inferior:
   - **"Registrar guía"** (verde) si aún no hay Entrada asociada
   - **"Guía Registrada"** (gris disabled) si `Entrada.objects.filter(guia=guia).exists()`
6. **Nueva Entrada** en modo `?guia=<pk>`:
   - Fecha de recepción = **`date.today()`** automática, no editable
   - Datos de la Guía en solo lectura (labels + texto, sin apariencia de input)
   - Tabla `Insumos | U. Medida | Stock | Cantidad | Observaciones | Acciones`
   - Cantidad prellenada con la despachada; **editable manualmente**
   - Botón **Aplicar** por fila (verde) → actualiza el stock visualmente
     (Stock + Cantidad) y bloquea la cantidad. Cambia a **Editar** (azul outline)
     para revertir. Marca `item_applied_{i}=1` en hidden input
   - Al submit Guardar → solo se crean `DetalleEntrada` de las filas con
     `applied=1`. El resto se ignora
   - Trazabilidad: `Entrada.guia = guia` (OneToOne)

### Reglas de validación de cantidad
Al ingresar cantidad en un ítem (comparada contra `guia.detalle.cantidad`):

| Situación | UI |
|---|---|
| Cantidad **=** Despachada | Todo OK. Aplicar habilitado. Observaciones deshabilitada |
| Cantidad **>** Despachada | Input rojo. Mensaje: "La cantidad despachada no coincide con la cantidad ingresada". **Aplicar bloqueado** (opacity 50%). Regla de seguridad — el Almacén no puede recibir más de lo que Logística despachó |
| Cantidad **<** Despachada | Observaciones **required**, placeholder "Motivo del faltante *". Aplicar solo se habilita cuando hay texto en Observaciones. La observación se persiste en `DetalleEntrada.observaciones` (`CharField 300`, migración `almacen/0010`) |
| Cantidad = 0 o vacía | Aplicar bloqueado |

### Impacto en Stock
El "Stock Almacén" mostrado en `Almacén → Stock` es un cálculo derivado:
`Σ DetalleEntrada.cantidad − Σ DetalleSalida.cantidad` por insumo. Al crear
Entradas nuevas, el saldo se refleja automáticamente. NO se toca
`InsumoPresupuesto.cantidad` (ese sigue siendo el cupo restante del presupuesto
que descuenta Logística al despachar).

### Pendientes conocidos
- **Notificaciones dirigidas** — hoy la notif se dispara globalmente
  (`usuario=None`). Filtrar por rol Almacenero requiere extender `notificar()`.
- **SSE real-time** en la campana — el endpoint `notif_stream` existe pero
  está huérfano (ver §7). Reactivarlo tiene costo por conexiones concurrentes.
- **Rechazo de guía** — hoy si Cantidad > Despachada solo se bloquea Aplicar.
  No hay flujo para "rechazar la guía" formalmente. `Entrada.estado='RECHAZADO'`
  existe en el modelo pero no está expuesto en la UI actual.
