# Contexto de sesión — 2026-08-04

Documento vivo para retomar el hilo cuando la conversación se compacte o
se abra una nueva sesión. Complementa a los docs "duros":

- [`CLAUDE.md`](CLAUDE.md) — guía técnica para el próximo asistente
- [`REGLAS_NEGOCIO.md`](REGLAS_NEGOCIO.md) — reglas de dominio, flujos, invariantes
- [`arquitectura_structure.md`](arquitectura_structure.md) — historia de la arquitectura RBAC y roles
- [`DECISIONES.md`](DECISIONES.md) — retiros de funcionalidad
- Auto-memoria en `~/.claude/projects/c--xampp-htdocs-structure/memory/`

---

## Estado del sistema (al cierre)

**RBAC completo** — enforcement en todas las vistas críticas:
- Decorador `@requiere('permiso'[, ...])` aplicado a **~189 vistas** públicas
- Decorador `@proyecto_visible` aplicado a **44 vistas** con `proyecto_id`
- `LoginRequiredMiddleware` cubre autenticación
- 4 roles operativos en BD: `Superadmin`, `Almacen`, `Jefe de obra`, `Logística`
  (más `Administrador de Obra` y `Almacenero` huérfanos sembrados por
  migración pero sin usuarios asignados — ver "Duplicados de roles" abajo)

**Flujo Opción B implementado** — Almacenero → Admin de Obra → Logística:
- Estado nuevo `SOLICITADO` en `ESTADOS_REQ`
- Vista nueva `requerimientos:solicitar` (Almacenero, formulario atómico)
- Vista nueva `requerimientos:bandeja_entrada` (Admin de Obra)
- Nota: el usuario tiene rol "Almacen" con permisos que él mismo eligió; puede
  o no tener `puede_aprobar_requerimientos` — verificar antes de usar el flujo B.

**Servidor:** Uvicorn ASGI corriendo en `:8000` (PID 14832 al cierre). Se accede
desde `192.168.100.38:8000`.

---

## Cambios realizados en esta sesión (2026-08-04)

Ordenados por área:

### Proyecto — campos nuevos + auto-llenado

- Modelo `Proyecto`: 2 campos nuevos → `sector` y `cargo_responsable`
- Migración: `apps/proyectos/migrations/0006_proyecto_cargo_responsable_proyecto_sector.py`
- Template `templates/proyectos/form.html`: layout nuevo
  - Fila: Cliente (col-4) | Responsable (col-4) | Cargo del Responsable (col-4)
  - Fila: Ubicación (col-8) | Sector (col-4)
- Vistas de requerimiento auto-llenan Solicitante / Cargo / Sector:
  - `crear` (Jefe de Obra) → viene de `proyecto.responsable`, `proyecto.cargo_responsable`, `proyecto.sector`
  - `solicitar` (Almacenero) → viene del usuario logueado (`get_full_name`, `perfil.cargo`, y `proyecto.sector` para el sector)
- Nota clave documentada en memoria [feedback-almacenero-req-propio]:
  el requerimiento del Almacenero **NUNCA** debe mostrar datos del responsable del proyecto.

### Formulario de Requerimiento — mejoras

- Campo `solicitante` del form: **de dropdown a input de texto libre**
  (se eliminó la lista de miembros y el `ChoiceField` en `apps/requerimientos/forms.py`)
- Widget del ítem en el formset: **queda `readonly` tras seleccionar el material**
  (no se puede editar/borrar; para cambiar, se elimina la fila entera)
- Ya no muestra `cursor: not-allowed` — se comporta como los otros inputs readonly del sistema
- Tooltip explicativo al hover

### Detalle de Requerimiento (Admin de Obra)

- Columna nueva **"Solicitado"** entre Cantidad y Unidad — muestra
  `DetalleRequerimiento.cantidad_requerida`
- `colspan` del empty state ajustado a 6

### Lista de Requerimientos Recibidos (Logística)

- Filas con estado `ENVIADO` (Nuevo) → fondo azul pastel `#eff6ff`
- Columna nueva **"Ítems"** con badge circular (solo número)
- Eliminado el ícono `bi-eye` "Ver detalle" — toda la fila ya es clickeable

### Topbar + Sidebar — mostrar rol del usuario

- Chip azul pastel con el nombre del rol al lado del proyecto activo
- Aplica en **topbar** (versión más grande, con ícono `bi-person-badge`)
- Aplica en **sidebar** (versión más chica, `.role-chip-sm`)
- Superadmin sin rol asignado muestra "Superadmin" como fallback
- Estilos en `static/css/main.css` (clases `.role-chip` y `.role-chip-sm`)

### Sidebar — desplegado siempre

- Se eliminaron los **6 grupos colapsables** (Presupuesto, Requerimientos,
  Almacén, Logística, Requerimientos-de-Logística anidado, Configuración)
- Eliminados: chevron toggles, wrappers `.sb-module-row`, clase `.collapse`
- Los sub-módulos ahora aparecen siempre visibles
- Se limpió el JS de "auto-abrir collapse"

### Sidebar — Logística simplificado

- Se eliminaron los sub-sublinks:
  - `Logística > Requerimientos > Requerimientos recibidos`
  - `Logística > Requerimientos > R. Consolidados`
- Queda solo el link **"Requerimientos"** apuntando a `logistica:requerimientos_log`
- Los chips del content (`templates/logistica/requerimientos.html`) se mantienen
  intactos para navegar entre las dos vistas

### Topbar — sin breadcrumb

- Eliminado el bloque `<nav>` del breadcrumb del topbar
- Los `{% block breadcrumb %}` de templates hijos quedan inertes
  (Django los ignora silenciosamente sin error)

---

## Decisiones importantes tomadas en esta sesión

1. **RBAC es agnóstico al nombre del rol** — el sistema decide por permisos,
   no por el nombre del rol. Puedes crear "Residente", "Ing. Civil", "Loco Pérez"
   y con los permisos correctos se comporta como Jefe de Obra.

2. **Se rechazó bloquear reutilización de permisos entre roles** — el usuario
   propuso que un permiso solo estuviera en un rol. Se le explicó que rompe
   RBAC estándar (y varias vistas OR que ya construimos). Descartado.

3. **Se rechazó el rediseño "Reporte de Material" vs "Requerimiento"** — el
   usuario propuso separar en modelos distintos para el Almacenero y el Admin
   de Obra. Después de discutir el alcance decidió no hacerlo por ahora.
   El flujo Opción B (estado `SOLICITADO`) queda.

4. **Cargo del Responsable en Datos Generales del Proyecto** — auto-llena
   Solicitante/Cargo/Sector en el requerimiento del Jefe de Obra. Para el
   Almacenero, el cargo viene de `PerfilUsuario.cargo` con fallback al rol.

5. **Botón "Aprobar" por ítem en revisión de logística** — se propuso pero
   el usuario decidió mantener solo el botón global "Aprobar requerimiento".

---

## Duplicados de roles en BD (pendiente decidir)

| Rol usado (asignado a usuario) | Huérfano (sembrado por migración) |
|---|---|
| **Almacen** (asignado a `almacen`) | **Almacenero** (sin usuarios) |
| **Jefe de obra** (asignado a `Harris`) | **Administrador de Obra** (sin usuarios) |
| **Logística** | mismo — no duplicado |
| **Superadmin** | mismo — no duplicado |

**Divergencia real:** los roles tuyos ("Almacen", "Jefe de obra") tienen
permisos que tú definiste manualmente, **no** los del diseño. Ej: "Jefe de obra"
tiene `puede_crear_proyectos` (que no debería según el diseño) y le faltan los
3 permisos nuevos (`puede_gestionar_personal`, `puede_ver_actividad`,
`puede_configurar_proyecto`).

**3 opciones documentadas:**
- (A) Actualizar permisos de tus roles y borrar los huérfanos
- (B) Reasignar usuarios a los roles del diseño y borrar los tuyos
- (C) Dejar todo como está — actualizar manualmente

Sin decisión aún.

---

## Pendientes de features futuras

Ver `REGLAS_NEGOCIO.md §9` y `arquitectura_structure.md §6.3` para detalle:

- **§12 Sobre-solicitud/excedente del Admin de Obra** — con justificación
  obligatoria en rojo, en pantalla separada. NO genera `Modificacion` automática.
- **§13 Módulo Configuración del Proyecto** (`configuracion:proyecto`) —
  para que el Admin de Obra edite datos de su proyecto (nombre, fechas,
  parámetros). Requiere permiso nuevo `puede_configurar_proyecto`.
- **Fase 2 de `stock_almacen`** — la lógica de actualización con Entradas/Salidas
  (Fase 1 = solo el campo persistido, hecho).
- **Trazabilidad tipo blockchain** — seguimiento de materiales desde
  requerimiento hasta llegada al almacén.
- **Notificaciones** — están conectadas (`REGLAS_NEGOCIO.md §7` corregido) pero
  el SSE sigue huérfano (no reactivar sin pedirlo).

---

## Recordatorios activos en memoria auto

Guardados en `~/.claude/projects/c--xampp-htdocs-structure/memory/`:

- **[project-git-push-ip-mobaxterm]** — antes de `git push` / deploy, verificar
  la IP configurada en MobaXterm para el VPS.
- **[feedback-almacenero-req-propio]** — regla firme: requerimientos del Almacenero
  reflejan SUS datos (nombre, cargo), NUNCA los del responsable del proyecto.
- **[feedback-no-commit-sin-pedir]** — no hacer `git commit` automáticamente.
- **[feedback-no-agregar-no-pedido]** — no implementar campos/features que no
  se pidieron explícitamente.

---

## Cómo probar lo del día

1. Loguearte como **Harris** (Jefe de obra):
   - Ir a `Proyectos → editar PRY-001` y confirmar campos "Sector" y
     "Cargo del Responsable" ya llenos.
   - Crear un nuevo requerimiento → Solicitante/Cargo/Sector auto-llenados.
   - Ver el detalle → nueva columna "Solicitado".
   - Verificar que el sidebar tiene Presupuesto/Requerimientos/Almacén/... siempre
     desplegados (sin chevrons).
   - Chip azul "Jefe de obra" al lado de "PRY-001-Conilla" en topbar.

2. Loguearte como **logistica** (rol Logística):
   - Ir a `Logística → Requerimientos` → lista con filas azul pastel para nuevos +
     columna "Ítems" con el conteo + sin ícono ver-detalle.
   - Al abrir un requerimiento, cambia a `EN_REVISION` (funcionalidad existente).
   - Sidebar sin sub-sublinks "Requerimientos recibidos" y "R. Consolidados";
     esos chips siguen dentro del content.

3. (Opcional) Loguearte como **almacen** — para probar el flujo Opción B se
   necesita que el rol "Almacen" NO tenga `puede_aprobar_requerimientos`.
   Verificar en `/configuracion/roles/` cuáles permisos tiene y ajustar.

---

## Al retomar (nueva sesión)

Si retomás con contexto perdido, lee en este orden:
1. Este archivo (`contexto_sesion_2026-08-04.md`)
2. `arquitectura_structure.md` — modelo RBAC completo y fases previas
3. `REGLAS_NEGOCIO.md` — reglas de dominio (§10 Opción B, §11 contadores,
   §12 excedente, §13 config del proyecto)
4. Auto-memoria: cargada automáticamente en cada sesión.