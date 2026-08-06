# Contexto de sesión — 2026-08-05

Handoff para retomar cuando la conversación se compacte o abra una sesión nueva.

Complementa a:
- [`CLAUDE.md`](CLAUDE.md) — guía técnica del proyecto
- [`REGLAS_NEGOCIO.md`](REGLAS_NEGOCIO.md) — reglas de dominio (con §14, §15, §16 nuevas)
- [`arquitectura_structure.md`](arquitectura_structure.md) — RBAC y arquitectura
- [`config_vps.md`](config_vps.md) — deploy
- Auto-memoria en `~/.claude/projects/c--xampp-htdocs-structure/memory/`
  (incluye [reference-vps] con IP `161.132.4.82` y [feedback-form-compact])

---

## Estado del sistema al cierre (2026-08-05, tarde)

### Deploys hechos hoy
- **Commit `1b8eea0`** (mañana): RBAC completo, flujo Ajustes, cotizaciones espejo de REQ, chips de Guías, refinamientos UI. Deploy exitoso en VPS con 11 migraciones aplicadas.
- **Commit `5a28708`** (mediodía): Almacén Stock con paginación + búsqueda live AJAX + `.form-compact` utility class.
- **Commit `5e6e3d1`** (tarde): Almacén → Guías buzón de recepción, recepción manual con validación cantidad/observaciones. **Pendiente de deploy en VPS.**

### Repo
- Local y GitHub sincronizados en `5e6e3d1`
- VPS todavía en `1b8eea0` (pendiente `git pull` para los últimos 2 commits)

### Servidor local (Uvicorn) corriendo con el código nuevo.

---

## Cambios importantes de esta sesión

### 1. Almacén → Stock (commit `5a28708`)
- Muestra TODOS los insumos del presupuesto (antes solo los con movimiento)
- Nueva columna **"Presupuestado"** (cantidad_total)
- "Saldo" renombrado a **"Stock Almacén"**
- Paginación server-side (20/página) + endpoint `stock_api` para AJAX
- Buscador live client-side con debounce 250ms
- Dropdown **"Filtrar por"** con 4 opciones y check en la activa; persistencia en `localStorage['stockAlmacenSort']`
- Sort por código usa `CAST(codigo AS INTEGER)` para orden numérico (1, 2, ..., 10, ..., 100). Ver REGLAS_NEGOCIO §15

### 2. Utility class `.form-compact` (commit `5a28708`)
- Movido de CSS inline a `static/css/main.css`
- Aplicable con `<form class="form-compact">` — reduce labels/inputs/cards ~25-30%
- Usado en: `guia_form.html`, `entrada_form.html`
- **Convención documentada** en CLAUDE.md y memoria `[feedback-form-compact]`

### 3. Sub-módulo Almacén → Guías (commit `5e6e3d1`)
Ver **REGLAS_NEGOCIO §16** para el flujo completo. Resumen:
- Nuevo sublink "Guías" en sidebar Almacén (después de Salidas)
- Buzón donde el Almacenero recibe las guías despachadas por Logística
- Guías no vistas: fondo verde suave + badge "NUEVA" (`GuiaRemision.vista_por_almacen`)
- Detalle readonly con datos e ítems
- Botón "Registrar guía" / "Guía Registrada" según haya o no Entrada

### 4. Recepción manual con Aplicar/Editar por ítem (commit `5e6e3d1`)
- **Removido el `_registrar_entrada_almacen` automático** del despacho de Logística
- Ahora la Entrada nace SOLO cuando el Almacenero la crea manualmente
- Form `entrada_form.html` en modo `?guia=<pk>`:
  - Fecha = `date.today()` automática, no editable
  - Datos de la guía en solo lectura (sin apariencia de input)
  - Tabla: Insumos (55%) | U. Medida | Stock | Cantidad | Observaciones | Acciones
  - Botón Aplicar/Editar por fila con toggle JS

### 5. Validación de cantidad vs despachada + Observaciones
- Cantidad = Despachada → OK
- Cantidad > Despachada → **BLOQUEADO** con mensaje "La cantidad despachada no coincide"
- Cantidad < Despachada → habilita columna Observaciones (required) para justificar
- `DetalleEntrada.observaciones` (`CharField 300`) para persistir la justificación
- Migración `almacen/0010_detalleentrada_observaciones`

### 6. Notificación "Nueva Guía" con URL
- Al despachar: notif dispara `"Nueva Guía GR-XXX"` con `url=/almacen/proyecto/N/guias/`
- Al hacer click en la campana, el Almacenero cae directo en el buzón

---

## Documentación agregada en REGLAS_NEGOCIO.md

- **§14** — Ajustes/Adicionales (ya estaba, chip placeholder "En desarrollo")
- **§15** — Renumeración de códigos S10 → enteros amigables (por qué hay duplicados entre grupos)
- **§16** — Flujo Logística → Almacén con recepción manual (NUEVA, esta sesión)

---

## Recordatorios activos en memoria (`~/.claude/.../memory/`)

- [reference-vps] — IP `161.132.4.82`, dominio `corfiemsistem.com`, ruta `/var/www/ssgestion`, stack nginx + Uvicorn, comandos de deploy
- [project-git-push-ip-mobaxterm] — antes de deploy verificar IP en MobaXterm
- [feedback-almacenero-req-propio] — reqs del Almacenero muestran SUS datos, no del responsable
- [feedback-no-commit-sin-pedir] — no auto-commit
- [feedback-no-agregar-no-pedido] — no implementar campos/features que no se pidieron
- [feedback-form-compact] — para achicar forms, usar clase `.form-compact` de main.css (no CSS inline)
- [feedback-single-project] — KPIs siempre filtrados por proyecto activo

---

## Pendientes conocidos (para próximas sesiones)

### Prioridad alta
- **Deploy commits `5a28708` + `5e6e3d1` en el VPS** (2 migraciones nuevas: `logistica/0003` y `almacen/0010`)
- **Códigos de insumo duplicados entre grupos** — el usuario pidió que se lo recordara. Ver §15. Propuesta: prefijar con grupo (M-1, MO-1, E-1, SP-1)

### Prioridad media
- **Notificaciones dirigidas al rol Almacenero** — hoy `notificar()` va global. Extender para filtrar por rol
- **SSE real-time** en la campana — endpoint `notif_stream` existe pero está huérfano. Ver REGLAS_NEGOCIO §7
- **Flujo formal de "rechazar guía"** — hoy si Cantidad > Despachada solo se bloquea Aplicar. `Entrada.estado='RECHAZADO'` existe en el modelo pero no expuesto en UI

### Prioridad baja / futura
- **Chip Ajustes** — está en placeholder "En desarrollo…". Cuando se retome, la infraestructura (`Requerimiento.es_ajuste`, `DetalleRequerimientoForm.modo_ajuste`) ya está lista
- **Módulo Configuración del Proyecto** (§13 — Admin de Obra edita datos de su proyecto)
- **Fase 2 stock_almacen** — hoy `InsumoPresupuesto.stock_almacen` existe como field pero sin lógica de actualización (§16 usa el cálculo derivado en su lugar)
- **Trazabilidad tipo blockchain** de materiales

---

## Cómo probar el sistema al retomar

1. **Loguearte como logística** → crear un REQ desde jefe de obra, aprobarlo desde logística, despachar la guía (botón "Guardar y Generar guía").
   - **Verificar**: la Entrada NO se crea automáticamente.
   - Aparece notif "Nueva Guía GR-XXX" en la campana.
2. **Loguearte como almacenero** → click en la campana → te lleva a `Almacén → Guías`.
   - La guía nueva se ve en **verde** con badge "NUEVA".
3. **Click en la fila** → detalle readonly. Botón verde "Registrar guía".
4. **Click Registrar** → Nueva Entrada. Fecha=hoy. Datos guía readonly. Tabla con Aplicar/Editar.
   - Probá cantidad IGUAL, MENOR y MAYOR a la despachada — comportamiento diferente en cada caso.
5. **Guardar** → vuelvo al detalle. Botón ahora dice **"Guía Registrada"** en gris.
6. **Almacén → Stock**: el saldo del insumo subió por la nueva Entrada.

---

## Al retomar (nueva sesión)

Orden de lectura recomendado:
1. Este archivo
2. `REGLAS_NEGOCIO.md` — especialmente §11 (contadores), §14 (ajustes), §15 (renumeración), §16 (recepción almacén)
3. `arquitectura_structure.md` — RBAC completo
4. Auto-memoria: cargada automáticamente en cada sesión
