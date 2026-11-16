# Cambios de la sesión — 14/11/2026

Resumen cronológico (del commit más viejo al más nuevo) de todo lo
implementado en esta sesión. Cada bloque tiene un título corto y una
descripción breve del porqué y qué hace.

---

## 1. Requerimientos: solicitante del perfil, no del responsable del proyecto
`26927b4`

Antes el nuevo requerimiento del Jefe de obra pre-llenaba
`Solicitante` con `proyecto.responsable` y `cargo_solicitante` con
`proyecto.cargo_responsable` — por eso aparecía "JUAN ALBERTO" aunque el
usuario logueado era otro. Ahora toma `request.user.get_full_name()` y
`request.user.perfil.cargo`. Cada rol ve sus propios datos.

---

## 2. Saldo global por insumo + sustitución registrada
`646ba91`

- Nuevo `apps/presupuesto/services.py` con `saldo_disponible_insumo`:
  `cantidad_total − Σ cantidad_aprobada de REQs activos`.
- Validación al crear/editar/aprobar REQ: bloquea pedidos que superen
  el saldo global del presupuesto, no solo el saldo por REQ.
- Consolidación de duplicados del mismo insumo dentro de un REQ (dos
  líneas de 25 ya no se cuelan como 50).
- Botón "Agregar insumo" renombrado a **"Sustituir insumo"** con
  selector *Reemplaza a*. Al sustituir, el original queda anulado y el
  historial registra la acción `SUSTITUIR` con la frase *"Sustituye a X"*.

---

## 3. Sidebar: link "Importar presupuesto" cuando no hay presupuesto
`19500cb`

Antes el link del sidebar, cuando el proyecto no tenía presupuesto
creado, apuntaba a `presupuesto:lista` (la misma página de "Actividad"
donde ya estabas). Al hacer clic solo recargaba sin ir a ningún lado.
Ahora apunta a `presupuesto:crear`, que crea el Presupuesto vacío y
redirige directo a la vista de Importar.

---

## 4. Unidades de medida: auto-registrar las detectadas al importar
`c9295e6`

Al importar presupuesto, las abreviaturas de unidad desconocidas (bol,
gal, hh, kg, m3, etc.) ya no muestran un warning pidiendo que las
agregues a mano. Ahora se **auto-crean** en el catálogo de
UnidadMedida:
- Si matchean el seed conocido → entran con nombre completo + aliases.
- Si son totalmente nuevas → entran con `nombre = CÓDIGO_EN_MAYÚSCULAS`
  para que las edites después.

También arregla un bug donde `importar_automatico` no desempaquetaba la
tupla `(total, unidades_desc)` devuelta por `importar_insumos_excel`.

---

## 5. CSS: ocultar spinner nativo de inputs numéricos
`a64d350`

Agregadas reglas CSS globales para esconder las flechitas ▲▼ nativas de
`<input type="number">` en Chrome/Edge/Firefox. Las flechas son ruido
visual y pueden dispararse accidentalmente con la rueda del mouse. El
teclado (↑↓) sigue funcionando.

---

## 6. Saldo global: contar REQs enviados también, no solo aprobados
`e89cd10`

El bug anterior permitía crear 3 REQs de 25 unidades cada uno porque la
validación solo contaba REQs ya APROBADOS. Ahora los estados que
"reservan" inventario incluyen también `SOLICITADO`, `ENVIADO` y
`EN_REVISION`. Para esos, como aún no hay `cantidad_aprobada`, se usa
`cantidad_requerida` (pesimista pero seguro).

También se agregó validación en el endpoint `enviar` — antes solo
cambiaba el estado sin chequear nada.

---

## 7. Saldo global: mensaje de error más simple y accionable
`943d459`

Simplificado el mensaje cuando se supera el saldo. Antes decía "hay
otros REQ en curso que comprometen este insumo, marcá como ajuste..."
— demasiado técnico. Ahora dice simplemente:

> "ABRAZADERA DE FIERRO GALVANIZADO 1": pediste 25 pero solo quedan
> 0.0000 und disponibles en el presupuesto. Espera a que logística
> apruebe tu solicitud.

---

## 8. Logística: renombrar módulo a "Ingreso de Requerimientos"
`2665e30`

El sidebar/breadcrumbs/títulos de logística decían "Requerimiento de
Almacén", lo que se confundía con la vista propia de Almacenero.
Renombrado a **"Ingreso de Requerimientos"** (el nombre original) en 16
lugares (9 archivos: sidebar, nav de logística, breadcrumbs y títulos
de 7 templates).

---

## 9. Revisión REQ: botón Aprobar y Sustituir por ítem via AJAX
`3ab7838`

Antes había que recorrer toda la tabla y clicar un único botón "Aprobar
Requerimiento" al final. Para REQs con 200 insumos esto era riesgoso.

Ahora cada fila tiene una columna **Acciones** con:
- Botón **"Aprobar"** azul (`AJAX`) → guarda la `cantidad_aprobada` de
  ese ítem directo en la base. Al confirmarse, el botón se pone verde
  con ✓ y aparece "Guardado HH:MM:SS". Si tocás el input después, el
  botón vuelve a azul para re-guardar.
- Ícono de flechas (`bi-arrow-repeat`) → abre modal **"Cambiar o Editar
  insumo"** con:
  - Insumo original arriba (read-only).
  - Buscador del nuevo insumo abajo.
  - Cantidad y justificación.
  - Al guardar: crea `DetalleRequerimiento` nuevo, pone `cantidad_aprobada=0`
    al original, registra en historial con `insumo_original` + `insumo`.
- Ícono de tacho (eliminar).

El botón global "Sustituir o Agregar insumo" fue removido. El flujo es
ahora enteramente por fila. El botón grande "Aprobar Requerimiento" del
fondo sigue existiendo para finalizar el estado.

**Nueva pestaña "Cambios de insumos"** entre *Por atender* y
*R. Consolidados* lista todas las sustituciones del proyecto (original
→ nuevo, cantidad, usuario, justificación).

**Migración**: `requerimientos/0017_historial_insumo_original` agrega
FK `insumo_original` a `HistorialRevisionReq`.

---

## 10. Revisión REQ: quitar botón eliminar ítem (no se usa)
`645f177`

El ícono del tacho + modal de "Eliminar ítem con justificación" fueron
removidos. El flujo para quitar un ítem ahora es ponerle cantidad = 0 y
guardar con *Aprobar*, o usar la sustitución.

---

## 11. Solicitar REQ: tooltip con saldo global del insumo
`ecf4157`

En el formulario de Solicitar Requerimiento (Jefe de obra / Almacenero),
al costado del input *CANT. A SOLICITAR* ahora aparece un ícono naranja
con signo de admiración (⚠) cuando el insumo ya tiene pedido
comprometido en otros REQs activos.

Al pasar el cursor, muestra un tooltip:

> *"Ya has solicitado **25 und** anteriormente. Te quedan **0 und** por
> solicitar."*

El ícono **no aparece** si el saldo está limpio (sin ruido visual).

Nuevo endpoint `/almacen/api/insumo/<id>/saldo/` devuelve
`{cantidad_total, ya_pedido, disponible, unidad}`.

---

## 12. Dashboard: contador visible en header + canvas con altura fija
`3f2077e`

- Badge azul con el **total de REQs** en el header del card
  *"Requerimientos por Estado"*. Si ves el badge pero el gráfico no, es
  problema de Chart.js. Si no ves el badge, no hay REQs en el proyecto.
- Los `<canvas>` del dashboard quedaron envueltos en divs con altura
  fija (230px/260px). Chart.js con `maintainAspectRatio: false` necesita
  un contenedor con altura definida; sin eso puede renderizar con
  altura 0 y quedar invisible.
- La query de REQs por estado usa ahora `Count('id')` en lugar de
  `Sum(Value(1))` — mismo resultado, más idiomático.

---

## 13. Insumos: ampliación manual de cantidad + paginación + fila naranja pastel
`deecf07`

Nueva funcionalidad en la vista **Insumos** para modificar la cantidad
de un insumo ya importado, sin tocar el valor original del Excel.

**Modelo nuevo** `AmpliacionInsumo` (migración
`presupuesto/0014_ampliacion_insumo`):
- FK al insumo + cantidad + justificación + usuario + fecha.
- Cada ampliación es una fila separada → trazabilidad completa.

**Lógica**:
- `InsumoPresupuesto.cantidad_total` (lo del S10) nunca se modifica.
- Nuevo método `cantidad_total_efectiva()` = `cantidad_total + Σ ampliaciones`.
- `saldo_disponible_insumo` ahora usa esa cantidad efectiva, así el
  Jefe de obra puede volver a solicitar lo que se agregó.

**UI**:
- Botón **"Modificar"** naranja (`#f97316`) al costado de la barra de
  búsqueda. Solo visible con `puede_editar_presupuesto`.
- Modal con buscador de insumo, cantidad actual + desglose, tabla de
  ampliaciones previas, input de cantidad a agregar + justificación.
- **Paginación** arriba (con selector 10/25/50/100 por página) y abajo.
  25 por defecto.
- **Fila con fondo naranja pastel** (`#fff7ed`) + ícono de lápiz al
  costado de la descripción en los insumos modificados.
- Columna CANTIDAD muestra `30,0000` en naranja + línea chica
  `25,0000 + 5,0000` si fue modificado.

Dos endpoints nuevos: `insumo_ampliar` (POST AJAX) y
`insumo_ampliaciones_json` (GET) para datos del modal.

---

## Notas transversales

- Todos los commits están en `main` y pusheados a `origin`.
- **Migraciones** aplicables al VPS:
  - `requerimientos/0017_historial_insumo_original`
  - `presupuesto/0014_ampliacion_insumo`
- **Collectstatic** necesario para los cambios de CSS (commit `a64d350`).

---

# Actualizaciones (pendientes de commit)

Cambios que están **solo en el working tree local** — no se commitearon
ni pushearon todavía. Esperan aprobación del usuario antes de subirlos.

## A1. Modal Modificar insumo: pulido visual + datos extra
*(commiteado — `65a4b18`)*

Ajustes al modal "Modificar cantidad de insumo" en la vista Insumos:

- **Barra de búsqueda**: al seleccionar un insumo, muestra
  `[CÓDIGO] descripción` (código al costado izquierdo, descripción
  después, en la misma línea).
- **Card "Insumo seleccionado"**: el código `[1]` ahora aparece en la
  misma fila que la descripción (antes estaba en una segunda línea
  debajo).
- **Fila de "Cantidad a agregar"**: al costado derecho del input se
  muestran 5 campos **no editables** con los datos del insumo:
  Tipo, Unidad, Cantidad (actual), Costo Unit., Total. Grilla compacta
  con labels en uppercase.

Backend: el endpoint `insumo_ampliaciones_json` ahora devuelve también
`tipo`, `tipo_display`, `costo_unitario` y `total` para alimentar esos
campos read-only.

---

## A11. Logística: solo botón Aprobar por fila (quitado ícono Sustituir)
*(sin commit — pendiente)*

En `templates/logistica/req_revisar.html` se eliminó el ícono de
flechas (`bi-arrow-repeat`) de la columna Acciones de cada fila, junto
con el modal "Cambiar o Editar insumo" y todo su JS asociado. Ahora
solo queda el botón **Aprobar** por fila.

Motivo: la ampliación de cantidad ya se hace centralmente desde
Presupuesto → Insumos → Modificar, por lo que la sustitución por fila
en Logística quedaba redundante.

El endpoint backend `req_item_sustituir` y la pestaña "Cambios de
insumos" **se mantienen** por compatibilidad y para consultar
sustituciones históricas, aunque ya no hay forma de disparar nuevas
desde la UI.

También incluye: agregar entrada equivalente en
`templates/configuracion/actualizaciones.html` (pestaña visible a los
usuarios).

---

## A10. Actualizaciones.html: 3 entradas nuevas visibles al usuario
*(sin commit — pendiente)*

Agregadas tres tarjetas al tope de la pestaña **Configuración →
Actualizaciones** (visibles para todos los usuarios logueados):
- Aviso de "MODIFICADO" en Req vs Atenciones (A8/A9).
- Widget "Insumos modificados" en el Dashboard (A7).
- Búsqueda y orden mejorados en Insumos (A5).

Además se renombró este archivo a `actualizacion.md` (antes
`CAMBIOS_SESION_14NOV2026.md`).

---

## A9. Tooltip de MODIFICADO con formato HTML en 3 líneas
*(commiteado — `00d3249`)*

Texto final del tooltip:

> **MODIFICADO**
> Cantidad inicial: 25.00
> Cantidad agregada: 15.00

Se usa `<br>` dentro del `title` con `data-bs-html="true"`. La
inicialización de Bootstrap Tooltip se hace en `{% block extra_js %}`
con `DOMContentLoaded` para asegurar que Bootstrap ya cargó (antes
estaba dentro de `content` y el browser caía al tooltip nativo del
sistema operativo, por eso se veía como texto plano).

---

## A8. Req vs Atenciones: presupuestado refleja ampliaciones
*(commiteado — `42e9a6d`)*

La columna "PRESUPUESTADO" ahora usa `cantidad_total_efectiva` —
original importada + ampliaciones manuales. Si el insumo fue
modificado, el valor aparece en **naranja** con un ícono de
admiración al costado. El tooltip al hover muestra:
*"Cantidad modificada: 25.00 original + 15.00 agregadas"*.

Aplica en ambas vistas: `requerimientos/vs_atenciones` (Jefe de obra)
y `logistica/vs_atenciones_log` (Logística).

---

## A7. Dashboard: widget de insumos modificados recientemente
*(commiteado — `291ad9e`)*

Nueva card en el dashboard del Jefe de obra con las últimas 10
ampliaciones manuales de insumos (hechas con el botón Modificar).
Columnas: fecha, código, insumo, cantidad agregada, justificación,
usuario. Header naranja pastel para hacer juego con la paleta de
"modificados". Mensaje de empty state si aún no hay ninguna
modificación en el proyecto.

---

## A6. Botón Modificar: altura igual a la barra de búsqueda
*(commiteado — `291ad9e`)*

Se removió `btn-sm` del botón "Modificar" para que su altura matchee
el `form-control` del buscador. Mismo ancho, tipografía `.85rem`.

---

## A5. Insumos: búsqueda server-side + orden numérico por código
*(commiteado — `9c29ab4`)*

- **Búsqueda server-side**: el input de la barra de búsqueda ahora
  envía un GET (?q=…) y filtra toda la lista del presupuesto en el
  backend, no solo los 30 visibles de la página actual. Soporta código,
  descripción y unidad. Preserva el filtro al cambiar de chip o página.
- **Orden numérico**: la lista se ordena por tipo + código numérico
  (1, 2, 3, …, 10, 11, …, 100), no alfabético, en Todos / Mano de Obra
  / Materiales / Equipos / Subcontratos. Se usa LPad para hacer el
  "natural sort" sin romper con códigos vacíos o con decimales.

---

## A4. Insumos: paginación simplificada
*(commiteado — `8aa2ee2`)*

- Paginación sin colores, texto gris chico, estilo minimal.
- Alineada a la derecha.
- Se eliminó el selector "Por página" — ahora es fijo en **30 insumos
  por página**.

---

## A3. Modal Modificar: grilla uniforme de 6 columnas
*(commiteado — `18d8cbe`)*

Los 5 campos read-only al costado de "Cantidad a agregar" (Tipo,
Unidad, Cantidad, Costo Unit., Total) ahora comparten el mismo tamaño
de input y el mismo estilo de label que "Cantidad a agregar". Grilla
`row g-2` con 6 `.col` iguales — labels `.78rem uppercase fw-semibold`
y todos los inputs `form-control-sm` estándar.

---

## A2. Nueva pestaña "Actualizaciones" en Configuración
*(commiteado — `18d8cbe`)*

Tab informativa después de Empresa con el changelog visible para
cualquier usuario autenticado. Diseño limpio: títulos negros,
descripciones simples, texto centrado. Cada entrada tiene fecha corta
(ej. "14 nov") + título + descripción breve, agrupadas bajo un badge
con el mes ("Noviembre 2026").

El contenido vive hardcoded en el template `actualizaciones.html`.
Nuevo view sin decorador de permiso (lo ve cualquier logueado).
