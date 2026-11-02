# Requisitos Funcionales — S&S Gestión

> Especificación funcional del sistema, **módulo por módulo**, expresada como requisitos
> (`RF-XX`: *el sistema debe…*). Describe **qué hace** el sistema de cara al usuario, no el
> esquema de datos ni el detalle de implementación.
>
> **Fuentes de verdad complementarias:**
> - `REGLAS_NEGOCIO.md` — el *por qué* y el *cómo* de cada flujo (fórmulas, invariantes).
> - `arquitectura_structure.md` — detalle del modelo RBAC y enforcement.
> - El código — ante discrepancia, **manda el código**. Este documento se desactualiza.
>
> Fecha de redacción: 2026-10-31 · Estado: refleja lo implementado; los pendientes se marcan como `[PENDIENTE]`.

---

## 1. Visión general

S&S Gestión es un sistema de gestión de obras de construcción para un **consorcio**. Cubre el
ciclo completo de una obra: presupuesto contractual → requerimiento de materiales → cotización
→ despacho (guía de remisión) → recepción en almacén → consumo, más el control de maquinaria,
personal y cuadrillas.

### 1.1 Principio rector — un proyecto activo a la vez

**RF-01.** El sistema debe operar siempre sobre **un único proyecto activo**, seleccionado por
el usuario y persistido en su sesión. Todas las vistas, KPIs y consultas se filtran por ese
proyecto. No existen métricas que mezclen proyectos salvo el panel transversal del Superadmin.

**RF-02.** El sistema debe permitir cambiar de proyecto activo desde las vistas de selección de
proyecto, actualizando el contexto de toda la aplicación.

### 1.2 Autenticación

**RF-03.** El sistema debe exigir inicio de sesión para toda ruta salvo las públicas
(`/login/`, `/admin/`, `/static/`, `/media/`). Un usuario no autenticado debe ser redirigido a
`/login/`.

---

## 2. Actores y control de acceso (RBAC)

### 2.1 Actores

| Actor | Rol en obra | Alcance |
|-------|-------------|---------|
| **Superadmin** | Dueño/programador del sistema | Todo el consorcio, todos los proyectos |
| **Administrador de Obra** | Residente de obra | Un proyecto (puede haber varios residentes, uno por proyecto) |
| **Logística** | Área de logística del consorcio | Atraviesa todos los proyectos |
| **Almacenero** | Operador del almacén | Un proyecto |

> **Aclaraciones de dominio:** "Administrador de Obra" ≠ "administrador del sistema" (ese es el
> Superadmin). "Personal" (obreros/cuadrillas) ≠ "Usuarios" (cuentas que ingresan al sistema).

### 2.2 Requisitos de permisos

**RF-04.** El sistema debe gobernar el acceso por un modelo de **roles con permisos booleanos**.
El catálogo de permisos (`GRUPOS_PERMISOS`) es la única fuente de verdad y agrupa los permisos
en: Proyectos, Presupuesto, Almacén/Requerimientos, Catálogo, Maquinaria, Logística,
Administración y Especiales.

**RF-05.** El sistema debe reconocer dos atajos de acceso total: el rol con `es_superadmin` y el
`is_superuser` de Django. Ambos **omiten** toda verificación de permiso.

**RF-06.** El sistema debe resolver la **visibilidad de proyectos** así:
- Superadmin / `es_superadmin` / rol con `acceso_todos_proyectos` → todos los proyectos.
- Rol sin `acceso_todos_proyectos` → solo proyectos donde el usuario es miembro (`ProyectoMiembro`).
- **Sin rol asignado → ve todos los proyectos** (comportamiento *fail-open* deliberado).

**RF-07.** El sistema debe mostrar/ocultar cada sección del sidebar según el permiso requerido
(Presupuesto, Requerimientos, Almacén, Maquinaria, Logística, Administración, etc.).

**RF-08.** El sistema debe permitir crear y editar roles desde la UI (Administración → Usuarios &
Roles). Los 3 roles operativos (Administrador de Obra, Logística, Almacenero) vienen **sembrados
por migración** con sus permisos predefinidos:

| Rol | Permisos clave sembrados |
|-----|--------------------------|
| **Administrador de Obra** | dashboard, ver/editar presupuesto, crear/aprobar requerimientos, ver/gestionar maquinaria, editar catálogo, gestionar personal, ver actividad, configurar proyecto |
| **Logística** | ver logística, revisar reqs, gestionar cotizaciones (log), gestionar logística/guías, inventarios, almacén log, control de maquinaria |
| **Almacenero** | ver almacén, crear requerimientos, gestionar entradas, gestionar salidas |

---

## 3. Módulo Proyectos

Gestiona los proyectos del consorcio, sus equipos y los dashboards.

**RF-10.** El sistema debe permitir crear, editar y eliminar proyectos (datos generales:
nombre, código, empresa ejecutora, responsable y cargo, fechas, etc.).

**RF-11.** El sistema debe mantener un **equipo por proyecto** (`ProyectoMiembro`), que determina
qué proyectos ve un usuario sin `acceso_todos_proyectos`.

**RF-12.** El sistema debe ofrecer un **dashboard por proyecto** (`/proyecto/<pk>/dashboard/`)
con los indicadores del proyecto activo, y un **panel transversal** (`/panel/dashboard/`)
para visión cruzada de proyectos (Superadmin).

**RF-13.** El sistema debe exponer una función de **"Restablecer Logística"** (Superadmin →
Proyecto → Restablecer) que reponga el contador de cupo de todos los insumos del proyecto:
`cantidad = cantidad_total`.

---

## 4. Módulo Presupuesto

Gestiona el presupuesto contractual: árbol de partidas, análisis de costos unitarios (ACU),
insumos y modificaciones.

### 4.1 Importación

**RF-20.** El sistema debe importar un presupuesto desde un archivo **S10** (`.xls`) o un
`.xlsx` genérico, poblando el árbol de **Partidas** (hasta 5 niveles) y la lista de
**InsumoPresupuesto**.

**RF-21.** El sistema debe guardar por presupuesto los porcentajes `gastos_generales_pct`,
`utilidad_pct`, `igv_pct` (y `supervision_pct`).

**RF-22.** Al importar, el sistema debe **renumerar los códigos de insumo** a enteros amigables
secuenciales por grupo (Materiales 1,2,3…; Mano de obra 1,2,3…; Equipos 1,2,3…; Subpartidas
1,2,3…), descartando los códigos crudos ilegibles del S10.
*Consecuencia conocida: códigos duplicados entre grupos (el "1" existe en materiales y en equipos). `[PENDIENTE]` diferenciar visualmente por grupo.*

### 4.2 Cálculo de totales

**RF-23.** El sistema debe calcular los totales del presupuesto en cascada:
`costo_directo → +GG% → +Utilidad% → sub_total → +IGV% → total_presupuesto`.

### 4.3 Insumos — el contador central

**RF-24.** Cada `InsumoPresupuesto` debe llevar **dos cantidades distintas**:
- `cantidad_total` (UI: **CANTIDAD / PRESUPUESTADO**): cantidad original importada, fuente de
  verdad permanente, **nunca muta**.
- `cantidad` (UI: **STOCK EN OBRA**): **cupo restante del presupuesto** (cuánto se puede aún
  pedir). Es el límite real para solicitar. Se descuenta **al generar la guía de remisión**.

**RF-25.** El sistema debe garantizar que `cantidad` **nunca sea negativa**
(`cantidad = max(0, cantidad − descontado)`).

**RF-26.** El sistema debe llevar además `stock_almacen` (stock físico), **calculado** como
`Σ entradas − Σ salidas`. Es distinto del cupo del presupuesto: el almacén empieza vacío; al
importar NO entra material al almacén. *Ver §12 para la distinción cupo vs stock físico.*

### 4.4 Análisis de costos y modificaciones

**RF-27.** El sistema debe permitir configurar el **ACU** (`RecursoPartida`) de cada partida
hoja: recursos de tipo material, mano de obra, equipo o subpartida, con cantidad y precio.

**RF-28.** El sistema debe soportar **Modificaciones** del presupuesto de tres tipos:
**Adicional** (aumenta), **Deductivo** (reduce), **Vinculante** (reformula sin cambiar monto),
cada una con sus `PartidaModificacion`. El monto vigente = original + Σ adicionales − Σ deductivos.

### 4.5 Motor ML (sugerencias)

**RF-29.** El sistema debe ofrecer, sobre la base de proyectos anteriores:
- búsqueda de partidas similares (TF-IDF),
- recursos ACU sugeridos para una partida,
- precio histórico (media/desviación) de un insumo.

Aprende automáticamente a medida que se configuran ACUs (caché con TTL 1 h).

---

## 5. Módulo Requerimientos

Solicitud de materiales/equipos por proyecto, numerada, contra los insumos del presupuesto.

### 5.1 Ciclo de estados

**RF-30.** El sistema debe gestionar el requerimiento según el flujo de estados:

```
BORRADOR → ENVIADO → EN_REVISION → APROBADO → COTIZADO → ATENDIDO
                                 → PARCIAL              → PARCIAL
                                 → ANULADO
```

| Estado | Significado |
|--------|-------------|
| `BORRADOR` | Creado, no enviado |
| `ENVIADO` | Enviado a logística (en lista de logística se muestra como **"Nuevo"**) |
| `EN_REVISION` | Logística lo abrió y lo evalúa |
| `APROBADO` | Todas las cantidades aprobadas |
| `COTIZADO` | Las cotizaciones aprobadas cubren lo aprobado; aún sin guía (marcador intermedio) |
| `PARCIAL` | Se aprobó menos de lo pedido **o** se despachó a medias |
| `ATENDIDO` | Todo lo aprobado viajó en guías vivas (EN_TRANSITO/ENTREGADO) |
| `ANULADO` | Cancelado |

**RF-31.** El sistema debe **recalcular el estado automáticamente** al aprobar/rechazar/eliminar
una cotización, emitir o anular una guía. Prioridad:
`ATENDIDO > PARCIAL > COTIZADO > APROBADO`.

### 5.2 Formulario de requerimiento

**RF-32.** El formulario debe mostrar por insumo: **CANTIDAD** (presupuestada, informativa),
**STOCK EN OBRA** (cupo restante) y **CANT. REQUERIDA** (ingresada). La cantidad requerida
**no puede superar** el STOCK EN OBRA en el flujo normal.

**RF-33.** El formulario debe **impedir seleccionar el mismo insumo dos veces** en el mismo
requerimiento (validación cliente: limpia el campo y avisa "⚠ Insumo ya agregado").

**RF-34.** El sistema debe permitir enviar un BORRADOR a logística con un endpoint dedicado
(`POST /requerimientos/<pk>/enviar/`) que solo cambia el estado, sin reenviar el formulario.

**RF-35.** El requerimiento del **Almacenero** debe mostrar **sus propios datos** como
solicitante, nunca los del responsable del proyecto.

### 5.3 Ajustes (adicionales) `[parcial]`

**RF-36.** El sistema debe permitir crear requerimientos marcados como **Ajuste**
(`es_ajuste=True`) desde `requerimientos:crear?ajuste=1`, que **no validan** el tope de cantidad
presupuestada (permiten sobre-solicitar). Se listan aparte (chip "Ajustes") y se marcan con
bandera roja.

**RF-37.** El sistema debe **bloquear "Enviar a Logística"** en el flujo normal si algún ítem
excede lo presupuestado, orientando al usuario al chip "Ajustes".
*`[PENDIENTE]`: el Ajuste no genera `Modificacion` automática ni justificación obligatoria por ítem.*

### 5.4 Requerimientos vs Atenciones

**RF-38.** El sistema debe ofrecer una vista consolidada (solo lectura) por insumo con las
columnas:
- **PRESUPUESTADO** = `cantidad_total`.
- **SOLICITADO** = Σ `cantidad_aprobada` de reqs en `APROBADO/COTIZADO/PARCIAL/ATENDIDO`.
- **ATENDIDO** = Σ cantidades cotizadas (COT aprobada) que viajan en guías vivas.
- **SALDO** = PRESUPUESTADO − ATENDIDO (rojo si negativo, verde si cero).

**RF-39.** El sistema debe permitir, desde cada fila, abrir el **historial por insumo**
(`/vs-atenciones/insumo/<id>/`) con todos los requerimientos que lo incluyeron.

---

## 6. Módulo Logística

Lado receptor del pipeline: revisa requerimientos, cotiza, aprueba y emite guías de remisión.

### 6.1 Revisión y aprobación de requerimientos

**RF-40.** Al abrir un requerimiento `ENVIADO`, el sistema debe transicionarlo automáticamente a
`EN_REVISION` (tanto en vista detalle como en vista de revisión).

**RF-41.** En la revisión, el sistema debe permitir a Logística:
- ajustar la cantidad a aprobar por ítem (entre 0 y la requerida),
- **eliminar** un ítem con **justificación obligatoria**,
- **agregar** un insumo nuevo o sustituto.

**RF-42.** Al "Aprobar requerimiento", el sistema debe:
- persistir `cantidad_aprobada` por ítem (eliminados → 0),
- registrar cada eliminación/agregado en `HistorialRevisionReq`,
- fijar estado `APROBADO` (si todas las aprobadas = requeridas) o `PARCIAL`,
- **eliminar guías PENDIENTE heredadas** (flujo viejo) y **no crear ninguna guía**,
- **no descontar** el contador de insumos (eso ocurre al emitir la guía).

**RF-43.** El sistema **no** debe exigir cotización para aprobar un requerimiento.

**RF-44.** El sistema debe mostrar el historial de revisión (`ELIMINAR`/`AGREGAR`, con
justificación, usuario y fecha) en las vistas de detalle de logística y del jefe de obra.

### 6.2 Cotizaciones

**RF-45.** El sistema debe permitir **crear cotizaciones desde el REQ** (modal "Crear
Cotizaciones"), con datos opcionales de proveedor y **buscador SUNAT/RENIEC** (reusa
`maquinaria:consulta_doc`) que autocompleta razón social y dirección.

**RF-46.** El modal debe listar solo los ítems con **saldo cotizable > 0**, con la cantidad
editable topada en `min(cantidad_aprobada, saldo)`. Al confirmar, crea la COT en `PENDIENTE`.

**RF-47.** El sistema debe **numerar las cotizaciones espejando el REQ**: primera del REQ001 →
`COT001`, segunda → `COT001-2`, etc. (cotizaciones libres sin REQ usan correlativo global).

**RF-48.** El sistema debe calcular el **saldo cotizable por ítem y por REQ**:
`saldo = cantidad_aprobada − Σ DetalleCotizacion.cantidad en COT APROBADAS del mismo REQ`.
Las COT `PENDIENTE` y `RECHAZADA` **no** cuentan (permite varias pendientes de distintos
proveedores por el mismo saldo). La validación es **por REQ**, no global por insumo.

**RF-49.** El sistema debe validar el saldo cotizable al **crear** (`cot_desde_req`, `cot_crear`),
**editar** (`cot_editar`) y **aprobar** (`cot_aprobar`) cotizaciones.

**RF-50.** En la aprobación (COT `PENDIENTE`), el sistema debe permitir **edición inline**:
cantidad (`≤` solicitada, no se puede subir) y **precio unitario obligatorio (> 0)**, con
subtotales en vivo y papelera por fila. Al aprobar:
- exige `cantidad > 0`, `precio_unitario > 0`,
- bloquea si quedan 0 ítems (debe usarse Rechazar),
- valida cruzadamente contra el saldo del REQ,
- pasa la COT a `APROBADA` y recalcula el estado del REQ.

**RF-51.** El sistema debe permitir **rechazar** una cotización (`RECHAZADA`), lo que **libera el
saldo** de vuelta al REQ. En COT `APROBADA`/`RECHAZADA` la tabla se muestra como texto fijo.

**RF-52.** El sistema debe ofrecer una **lista de cotizaciones** agrupada por REQ de origen
(más grupo "Sin requerimiento"), con buscador live y vista de impresión (`cot_imprimir`).

### 6.3 Guías de remisión

**RF-53.** El sistema debe generar la guía a partir de **una o varias cotizaciones APROBADAS**
(no del requerimiento). Solo son elegibles las COT que no viajan ya en una guía activa.

**RF-54.** El sistema debe **autogenerar** el N° de guía (`GR-{año}-{correlativo 3 dígitos}`, por
proyecto y año) y la fecha de emisión (hoy), mostrados como texto y forzados en el servidor.

**RF-55.** Al "Guardar y generar guía", el sistema debe, en una sola transacción:
- crear la guía directamente en `EN_TRANSITO` y ligarla a las cotizaciones,
- copiar los ítems a `DetalleGuia`,
- **descontar el contador** solo de los ítems ligados a insumo:
  `insumo.cantidad = max(0, cantidad − cantidad_cotizada)`,
- recalcular el estado de cada requerimiento de origen,
- **no** crear la Entrada en almacén (eso lo hace el Almacenero).

**RF-56.** El sistema debe garantizar que **una cotización solo se despacha una vez**. Al
**anular/eliminar** una guía debe devolver el stock (sin pasar de `cantidad_total`), liberar la
cotización y recalcular el REQ. Una guía anulada **no se reactiva**: se genera una nueva.

**RF-57.** El sistema debe gestionar los estados de guía
`PENDIENTE → EN_TRANSITO → ENTREGADO / ANULADO`. La transición a `ENTREGADO` ocurre
**automáticamente** cuando el Almacenero registra la guía en Almacén (no hay botones manuales de
transición).

**RF-58.** El sistema debe presentar una **lista unificada de guías** (sin pestañas), con
columnas Origen y Destino separadas, cada fila clickable abre la impresión A4 en pestaña nueva.

**RF-59.** El sistema debe ofrecer **impresión A4** de la guía (`/logistica/guia/<pk>/imprimir/`)
con cabecera (logo, razón social, RUC), datos de traslado, transporte, bienes y firmas.

**RF-60.** El sistema debe **bloquear la anulación de un requerimiento** si alguna de sus
cotizaciones viaja en una guía `EN_TRANSITO`/`ENTREGADO`.

### 6.4 Catálogos y reportes

**RF-61.** El sistema debe mantener un catálogo de **Transportistas**.

**RF-62.** El sistema debe exponer sub-vistas de dashboard de logística (inventarios, almacén,
control de maquinaria, abastecimiento) y una vista **Reportes** (`logistica:reportes`), hoy
placeholder "En desarrollo". `[PENDIENTE]`

---

## 7. Módulo Almacén

Recepción física de guías, gestión de stock y salidas. El almacén parte **vacío**.

### 7.1 Recepción de guías (Entradas)

**RF-70.** El sistema debe mostrar al Almacenero las guías `EN_TRANSITO`/`ENTREGADO` del proyecto
(**Almacén → Guías**), resaltando en verde y con badge "NUEVA" las no vistas
(`vista_por_almacen`). Al abrir el detalle, marca la guía como vista.

**RF-71.** El detalle de guía debe ser **solo lectura** y ofrecer un botón **"Registrar guía"**
(verde) si no hay Entrada asociada, o "Guía Registrada" (gris) si ya existe.

**RF-72.** Al crear la Entrada en modo guía, el sistema debe:
- fijar la fecha de recepción = hoy (no editable),
- mostrar los datos de la guía en solo lectura,
- prellenar la cantidad con la despachada, **editable**,
- permitir aplicar ítem por ítem (botón **Aplicar/Editar**),
- crear `DetalleEntrada` **solo** de las filas aplicadas.

**RF-73.** El sistema debe validar la cantidad recibida contra la despachada:

| Situación | Comportamiento |
|-----------|----------------|
| Recibida **=** despachada | OK, Aplicar habilitado, observación deshabilitada |
| Recibida **>** despachada | Input rojo, **Aplicar bloqueado** (no se recibe más de lo despachado) |
| Recibida **<** despachada | Observación **obligatoria** (motivo del faltante), se persiste |
| Recibida = 0 / vacía | Aplicar bloqueado |

**RF-74.** Al registrar la guía (con Entrada asociada), el sistema debe pasar la guía a
`ENTREGADO` y dejar traza en el registro de actividad. **No** debe tocar `InsumoPresupuesto.cantidad`.
`[PENDIENTE]`: flujo formal de rechazo de guía (existe `Entrada.estado='RECHAZADO'` pero no expuesto en UI).

### 7.2 Stock, salidas y kardex

**RF-75.** El sistema debe calcular el **stock físico** por insumo como
`Σ DetalleEntrada.cantidad − Σ DetalleSalida.cantidad`, con orden numérico correcto de los
códigos (CAST a entero).

**RF-76.** El sistema debe registrar **Salidas** de material (a cuadrilla/trabajador/destino),
que descuentan del stock físico.

**RF-77.** El sistema debe soportar **Órdenes de Compra** (`OrdenCompra`), opcionalmente ligadas
a un requerimiento.

---

## 8. Módulo Maquinaria

Catálogo de equipos, partes diarios y liquidaciones.

**RF-80.** El sistema debe mantener un **catálogo de maquinaria** por proyecto (identificación,
tipo de equipo, modalidad de costo, propietario, fechas de obra, estado activo).

**RF-81.** El sistema debe registrar el **parte diario de maquinaria** (`RegistroMaquinaria`):
lectura de horómetro entrada/salida (auto-calcula horas), actividad, observación, auto-numerando
el `numero_parte` por máquina.

**RF-82.** El sistema debe permitir **liquidaciones mensuales** (`Liquidacion`) que agrupan los
partes de una máquina y calculan el `monto_a_pagar` según la `modalidad_costo`.

**RF-83.** El sistema debe ofrecer un **buscador por documento** (`maquinaria:consulta_doc`,
Factiliza) reutilizado por maquinaria, cotizaciones, revisión de reqs y alta de personal.

---

## 9. Módulo Personal, Cuadrilla y Asistencia

Página "Cuadrilla" con tres pestañas: **Personal**, **Cuadrilla**, **Asistencia**.

### 9.1 Personal

**RF-90.** El sistema debe registrar el **personal de obra** (`Trabajador`) por proyecto —
obreros/operadores que **no ingresan al sistema**, distintos de los usuarios.

**RF-91.** El único dato obligatorio debe ser **nombres + apellidos**; todo lo demás opcional
(datos personales, contacto, emergencia, laboral, habilidades libres, licencia, seguridad social,
foto, CV, observaciones, flag activo).

**RF-92.** El sistema debe ofrecer **autollenado por DNI** (RENIEC vía Factiliza): nombres,
apellidos, dirección, ubigeo y —si disponible— fecha de nacimiento y sexo. Debe rellenar solo
campos vacíos (no pisar correcciones manuales) y dejar todo editable.

**RF-93.** La tabla de Personal debe mostrar solo lo transversal (foto, nombres, DNI, cargo,
teléfono, experiencia, CV clickeable). El sistema debe permitir adjuntar **N documentos**
arbitrarios por trabajador (`DocumentoTrabajador`), aparte del CV.

### 9.2 Cuadrilla

**RF-94.** El sistema debe agrupar al personal en **cuadrillas (frentes de trabajo)** por
proyecto, con nombre, descripción, capataz (filtrado al proyecto), ubicación libre, fechas y
estado.

**RF-95.** El sistema debe permitir asignar trabajadores a una cuadrilla
(`IntegranteCuadrilla`), admitiendo que un trabajador pertenezca a **varias cuadrillas**
simultáneamente. Debe ofrecer alta inline y retiro por integrante.
*Nota: el cálculo tarifario de HH/costo-hora quedó como stub tras el rediseño de oct-2026.* `[PENDIENTE]`

### 9.3 Asistencia

**RF-96.** El sistema debe ofrecer una **vista matricial** de asistencia (filas = trabajadores
activos; columnas = días del período) con estados: Presente, Falta, Tardanza, Permiso, Descanso,
Feriado, o sin marcar.

**RF-97.** El sistema debe soportar períodos **Diario, Semanal (lun–dom ISO), Quincenal (15 días
desde la fecha) y Mensual**, con cabecera y primera columna fijas (sticky) al hacer scroll.

**RF-98.** El sistema debe guardar la matriz **en bulk** (`update_or_create` por celda); una celda
vacía elimina la marca existente.
*`[PENDIENTE]`: no calcula HH, no cruza con cuadrilla, no exporta, no bloquea fechas pasadas, sin permiso dedicado.*

---

## 10. Módulo Catálogo

**RF-100.** El sistema debe mantener un **catálogo maestro de productos** (`Producto`) compartido
por todos los proyectos, con código único, descripción, categoría y unidad.

---

## 11. Módulo Configuración

**RF-110.** El sistema debe gestionar los **Datos del Consorcio** (`ConfigEmpresa`, singleton):
razón social, RUC, dirección, teléfono, email, logo y color/imagen de marca. *(IGV, sitio web y
moneda fueron removidos: los precios vienen con/sin IGV directo del proveedor.)*

**RF-111.** El sistema debe gestionar la configuración de **SUNAT/Factiliza** (`ConfigSunat`),
catálogos de **Unidades de Medida**, **precisión decimal**, **cargos de mano de obra** y
**reglas de detección de insumos**.

**RF-112.** El sistema debe gestionar **usuarios y roles** (Administración), y el **perfil** de
cada usuario (`PerfilUsuario`: vínculo User↔Rol, teléfono).

**RF-113.** `[PENDIENTE]` El sistema debe ofrecer un módulo **"Configuración del Proyecto"** para
que el Admin de Obra edite datos de su proyecto activo (nombre, fechas, parámetros de
presupuesto) — distinto de la configuración global del consorcio. Permiso propuesto:
`puede_configurar_proyecto`.

---

## 12. Módulo Registro y Notificaciones

**RF-120.** El sistema debe llevar un **registro de actividad** transversal (`RegistroAccion`)
con acción, módulo y descripción, escrito desde los puntos clave de cada app.

**RF-121.** El sistema debe emitir **notificaciones in-app** (`Notificacion`) en eventos clave
(requerimientos, logística, almacén, presupuesto); `usuario=None` difunde a todos los usuarios
activos.

**RF-122.** La **campana del topbar** debe cargar las notificaciones vía `fetch` (JSON) **al hacer
clic** (no en tiempo real), mostrando contador de no leídas y tipo (info/success/warning/danger).
*El endpoint SSE `notif_stream` existe pero está **huérfano/desactivado** (coste por conexiones concurrentes); no reactivar sin pedirlo.* `[PENDIENTE]`

---

## 13. Reglas de negocio transversales (invariantes)

Requisitos que atraviesan varios módulos y son el núcleo de la corrección del sistema.

**RF-130. Dos contadores distintos.** El sistema debe mantener separados:
- **Cupo del presupuesto** (`InsumoPresupuesto.cantidad`): cuánto se puede aún **pedir**; baja al
  pasar la guía a EN_TRANSITO; parte de `cantidad_total`.
- **Stock físico** (calculado): cuánto material **hay** en el galpón; parte de 0; sube con
  entradas aprobadas, baja con salidas.

**RF-131. El almacén empieza vacío.** Importar el presupuesto **no** mete material al almacén;
el stock físico solo aparece cuando llega físicamente (guía recibida).

**RF-132. Descuento en el momento correcto.** El cupo del presupuesto se descuenta **al generar
la guía** (EN_TRANSITO), nunca al aprobar el requerimiento ni la cotización.

**RF-133. No negatividad.** Ningún contador de cupo puede volverse negativo
(`max(0, …)`).

**RF-134. Validación por REQ.** El saldo cotizable se controla **por requerimiento**, no global
por insumo; el control global del insumo solo ocurre al emitir la guía.

**RF-135. Despacho único.** Una cotización aprobada solo puede despacharse una vez; anular la
guía revierte stock, libera la cotización y recalcula el estado.

---

## 14. Requisitos no funcionales (resumen)

| ID | Requisito |
|----|-----------|
| **RNF-01** | Stack: Django 6.0.6 · Python 3.12 · PostgreSQL. Frontend Bootstrap 5.3.3 sin build step (CDN + `main.css`). |
| **RNF-02** | Servidor estándar: Uvicorn/ASGI (`servidor_asgi.py`, `workers=1` en Windows para evitar zombies). Producción: Apache (puerto 80) como reverse proxy → app en 8000. |
| **RNF-03** | Estáticos servidos por Apache `Alias` o WhiteNoise; ejecutar `collectstatic` tras cambios de CSS/JS. Acceder siempre por puerto 80. |
| **RNF-04** | Secretos desde `.env` (`SECRET_KEY` obligatorio). |
| **RNF-05** | Consultas SUNAT/RENIEC vía servicio externo Factiliza; proyecto Laravel hermano `conexion_sunat/` (no parte de Django). |
| **RNF-06** | Toolchain de parsing de PDFs S10 en venv aparte (`anlisis-pdf/`): PyMuPDF, openpyxl, Tesseract OCR (solo escaneados). |
| **RNF-07** | No hay suite de tests implementada (`tests.py` son stubs vacíos). |

---

## 15. Trazabilidad módulo ↔ app Django

| Módulo funcional | App(s) `apps/` |
|------------------|----------------|
| Proyectos | `proyectos` |
| Presupuesto (+ ML) | `presupuesto` |
| Requerimientos | `requerimientos` |
| Logística (cotizaciones, guías) | `logistica` + `almacen` (cotizaciones) |
| Almacén (entradas, salidas, stock) | `almacen` |
| Maquinaria | `maquinaria` |
| Personal / Cuadrilla / Asistencia | `maquinaria` |
| Catálogo | `catalogo` |
| Configuración / RBAC | `configuracion` + `config/permisos.py` |
| Registro / Notificaciones | `registro` |

---

*Documento generado a partir del código, `REGLAS_NEGOCIO.md`, `arquitectura_structure.md` y los
modelos de cada app. Para el detalle de fórmulas e invariantes, consultar `REGLAS_NEGOCIO.md`;
ante discrepancia, manda el código.*
