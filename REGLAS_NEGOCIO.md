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
