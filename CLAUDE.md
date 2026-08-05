# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Development server (use one only, not several at once)
python servidor_asgi.py             # Uvicorn ASGI — servidor estándar, local y producción (workers=1)
python manage.py runserver          # Django dev server (port 8000)
python servidor.py                  # Waitress WSGI — legado, sigue presente pero no es el camino habitual

# Database
python manage.py makemigrations <app_name>
python manage.py migrate
python manage.py createsuperuser

# Static files (required after any CSS/JS change for Apache/WhiteNoise to serve them)
python manage.py collectstatic --noinput
```

`workers=1` en `servidor_asgi.py` es deliberado: con Python de Microsoft Store (`python3.12.exe`) en Windows, más workers dejan procesos zombie. Para matarlos: `taskkill /IM python3.12.exe /F /T`.

There are no tests implemented — `tests.py` files are empty stubs (including `apps/maquinaria/tests.py`).

## Documentación de dominio — leer antes de tocar lógica de negocio

`REGLAS_NEGOCIO.md` en la raíz es la referencia autoritativa del **por qué** de cada flujo (contadores de insumos, estados de requerimiento, generación de guías, fórmulas de presupuesto). No duplica el esquema de modelos. **Consúltalo antes de modificar lógica de requerimientos, logística o presupuesto** — varias reglas ahí no son deducibles leyendo el código.

Otros documentos: `DOCUMENTACION_SISTEMA.md` (funcional, extenso), `contexto_app.md` (diseño de una app Flutter offline-first aún no implementada — define arquitectura, no genera código), `config_vps.md`, `documentación/normativa.md`.

Ese documento se desactualiza: verifica contra el código antes de dar por firme una afirmación de estado. Al 2026-08-02 el §7 (notificaciones) fue actualizado tras detectar que las llamadas a `notificar()` sí existen en varios módulos.

Secrets come from a `.env` file at the repo root (`python-dotenv`, loaded in `config/settings.py`). `SECRET_KEY` is required (`os.environ['SECRET_KEY']` — raises `KeyError` if missing); `DEBUG`, `ALLOWED_HOSTS`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT` are optional with dev defaults.

## PDF Parsing Toolchain (`anlisis-pdf/`)

Separate Python venv at `anlisis-pdf/venv/` — **not** the main project's Python.

```bash
# Activate the venv (PowerShell)
cd anlisis-pdf
.\venv\Scripts\Activate.ps1

# Key packages installed
pip install pymupdf          # fitz — text-based PDF extraction
pip install openpyxl         # XLSX generation
pip install pytesseract      # OCR wrapper (requires Tesseract binary)
pip install pillow           # required by pytesseract
```

### Tesseract OCR (system binary)
- Installed at `C:\Program Files\Tesseract-OCR\tesseract.exe` (winget install UB-Mannheim.TesseractOCR)
- Spanish language pack: `spa.traineddata` downloaded manually to `C:\Program Files\Tesseract-OCR\tessdata\`
  from https://github.com/tesseract-ocr/tessdata
- Only needed for **scanned** PDFs; text-based S10 exports use PyMuPDF directly (no OCR)

### ML — Motor de aprendizaje (`apps/presupuesto/ml.py`)

| Función | Qué hace |
|---------|----------|
| `buscar_similares(query, presupuesto_id, n)` | TF-IDF coseno sobre nombres de partidas hoja; normaliza especificaciones de concreto/acero/números |
| `recursos_sugeridos(partida)` | Recursos ACU ponderados de partidas similares con ACU configurado |
| `precio_historico(nombre, excluir_presupuesto_id)` | Media/std de precio unitario de partidas similares en proyectos anteriores |
| `invalidar_cache()` | Llama al guardar/eliminar RecursoPartida (ya integrado en las vistas) |

Caché: `LocMemCache` con TTL 1 hora, clave `presupuesto_ml_v1`.
Aprende automáticamente: cada ACU que configures se incorpora al índice tras la siguiente invalidación.
**Limitación inicial**: con 1 proyecto y 0 ACU configurados, las sugerencias aparecerán a medida que el usuario configure recursos.

### Scripts

| Script | Purpose |
|--------|---------|
| `anlisis-pdf/pdf_a_xlsx.py` | Converts a text-based S10 presupuesto PDF → XLSX importable by the system. Column boundaries calibrated to S10's X-coordinates. Handles multi-line descriptions and right-aligned large metrado numbers. |
| `anlisis-pdf/importar.py` | Django shell script: reads the generated XLSX + `porcentajes.json` → imports partidas into the active project's `Presupuesto`, saves GG%/Utilidad%/IGV%. |
| `anlisis-pdf/extraer.py` | OCR extraction for scanned PDFs (Tesseract + PyMuPDF). Outputs `.txt`. |

### Workflow: S10 PDF → Sistema

```bash
# Step 1 — Generate XLSX from PDF (uses anlisis-pdf venv)
cd anlisis-pdf
.\venv\Scripts\python.exe pdf_a_xlsx.py "../PRESUPUESTO.pdf"
# → generates PRESUPUESTO.xlsx and porcentajes.json in anlisis-pdf/

# Step 2 — Import into Django (uses system Python + manage.py)
cd ..
python manage.py shell -c "exec(open(r'C:/xampp/htdocs/structure/anlisis-pdf/importar.py', encoding='utf-8').read())"
```

### S10 PDF column layout (calibrated X-coordinates)
```
Item      0   – 108   (codes: 01, 01.01, 01.01.01 ...)
Desc    108   – 342
Und     342   – 408   (units: m2, ml, glb, mes ...)
Metrado 408   – 452   (right-aligned; large values spill left into Und zone)
Precio  452   – 500
Parcial 500   – ∞
```
Numbers appearing in the Und zone are reclassified as Metrado automatically.

## Troubleshooting

### Sidebar / CSS no carga (UI sin estilos)

**Diagnóstico rápido:**
```powershell
# ¿Qué devuelve el CSS?
Invoke-WebRequest -Uri "http://127.0.0.1:8000/static/css/main.css" -UseBasicParsing | Select-Object StatusCode, @{N='CT';E={$_.Headers['Content-Type']}}, @{N='Size';E={$_.Content.Length}}
```

| Resultado | Causa | Solución |
|-----------|-------|----------|
| `text/html` ~4KB | `LoginRequiredMiddleware` bloqueando `/static/` | Verificar que `config/middleware.py` tiene `/static/` y `/media/` en `_RUTAS_PUBLICAS` |
| 404 | Procesos Python viejos en puerto 8000 con código anterior | `netstat -ano \| findstr ":8000 "` → matar todos los PIDs → reiniciar `servidor.py` |
| 404 desde Apache | Accediendo por puerto 8000 sin Apache | Usar `http://localhost/` (puerto 80) o instalar WhiteNoise |
| `text/css` 18KB | CSS sirve bien — limpiar caché del navegador | `Ctrl+Shift+R` en el navegador |

**Soluciones permanentes instaladas:**
- `config/middleware.py` — `/static/` y `/media/` en rutas públicas
- `config/settings.py` — `whitenoise.middleware.WhiteNoiseMiddleware` en posición 2 del MIDDLEWARE
- WhiteNoise permite que el servidor de aplicación sirva estáticos directamente sin Apache

**Reinicio correcto del servidor:**
```powershell
# Verificar que no quedan procesos viejos
netstat -ano | findstr ":8000 "
# Matar cada PID listado, luego:
python servidor.py
```

## Stack

- **Django 6.0.6** · Python 3.12 · PostgreSQL (`ss_gestion`, localhost:5432, credentials read from `.env`)
- **Serving (Windows)**: Apache (XAMPP) on **port 80** as reverse proxy → app server on port 8000. Apache serves `/static/` and `/media/` directly via `Alias` in `c:\xampp\apache\conf\extra\httpd-vhosts.conf`. **Always access via port 80** — accessing port 8000 directly skips Apache and CSS/static files won't load. Run `collectstatic` after any CSS/JS change.
  - El servidor estándar en ambos entornos es **Uvicorn/ASGI** (`servidor_asgi.py` → `config.asgi:application`). `servidor.py` (Waitress/WSGI) sigue en el repo como legado.
- **Frontend**: Bootstrap 5.3.3 + Bootstrap Icons 1.11.3 + Inter font. No build step — all CDN except `static/css/main.css`.

## Project Architecture

### Single-project model
The system operates on **one active project at a time**, tracked per-session via `request.session['proyecto_id']`. `config/context_processors.py → proyecto_activo()` reads that session key and injects the current `Proyecto` into every template as `{{ proyecto_activo }}`. Switching projects happens through project-selection views in `apps/proyectos`.
(`Proyecto` also has a legacy `activo` boolean, still present on the model, but it is not what drives the UI anymore — the session value is authoritative.)

Other global context processors registered in `config/settings.py`: `notif_no_leidas` (unread notification count for the bell icon), `req_enviados_count` (count of `Requerimiento` in `ENVIADO` state, drives a sidebar badge), `permisos_usuario` (see permission system below).

### Apps (`apps/`)

| App | Responsibility |
|-----|---------------|
| `proyectos` | `Proyecto`, `ProyectoMiembro` (team), project admin, dashboards |
| `presupuesto` | `Presupuesto` → `Partida` tree (up to 5 levels) + `RecursoPartida` (ACU) + `InsumoPresupuesto` + `Modificacion`/`PartidaModificacion`. Imports S10 `.xls` and generic `.xlsx` via `importador.py`. `Presupuesto` stores `gastos_generales_pct`, `utilidad_pct`, `igv_pct`; computes `costo_directo()`, `gastos_generales()`, `utilidad()`, `sub_total()`, `igv()`, `total_presupuesto()`. Also hosts the ML engine (see above). |
| `requerimientos` | `Requerimiento` (material/equipment request, numbered per project) → `DetalleRequerimiento` line items against `InsumoPresupuesto` (supports substitution via `insumo_sustituto`) + `HistorialRevisionReq` audit trail. State flow: `BORRADOR → ENVIADO → EN_REVISION → APROBADO → ATENDIDO`/`PARCIAL` (or `ANULADO`). Reviewed from the `logistica` app. |
| `almacen` | `Entrada` → `Salida` → `Cotizacion` → `OrdenCompra`, each optionally linked back to the originating `requerimientos.Requerimiento`. Tied to `Proyecto` + `InsumoPresupuesto`. |
| `logistica` | Receiving/processing side of the requirement pipeline: reviews `Requerimiento`s sent by projects (`requerimientos_log`, `req_revisar_log`), `GuiaRemision`/`DetalleGuia` (shipping manifests) + `Transportista` catalog, plus dashboard sub-views (inventarios, almacén, control de maquinaria, abastecimiento). Has a lightweight realtime poll endpoint (`ping_reqs`) explicitly flagged in `urls.py` as removable if superseded. |
| `maquinaria` | Equipment/crew tracking: `Maquinaria` (equipment catalog), `TipoPersonal`/`Cuadrilla`/`IntegranteCuadrilla` (crew composition + hourly cost), `RegistroDiario` (daily crew log tied to a `Partida`), `RegistroMaquinaria` (daily equipment parte diario; auto-computes `horas` from `hora_entrada`/`hora_salida` and auto-numbers `numero_parte` per machine in `save()`), `Liquidacion` (monthly settlement grouping a machine's `RegistroMaquinaria` entries, computes `monto_a_pagar` per `modalidad_costo`). |
| `catalogo` | `Producto` — master product catalog shared across all projects |
| `configuracion` | `ConfigEmpresa` (singleton via `get()`), `Rol` (~26 BooleanField permissions defined by `GRUPOS_PERMISOS`), `PerfilUsuario` (User↔Rol), `UnidadMedida`, decimal precision and cargo (job title) catalogs |
| `registro` | Cross-cutting activity log (`RegistroAccion`, written via `apps/registro/utils.py → log(request, accion, modulo, descripcion)`) and in-app `Notificacion` (written via `notificar(titulo, ..., usuario=None)` — `usuario=None` difunde a todos los usuarios activos). La campana del topbar carga notificaciones con `fetch` a `registro:notif_json` **al hacer clic**, no en tiempo real. El endpoint SSE `notif_stream` existe en el backend pero está **huérfano**: no hay ningún `EventSource` en los templates. Se desactivó porque cada pestaña abierta mantenía una conexión consultando la DB cada 10 s. No lo trates como funcionalidad viva ni lo "arregles" sin pedirlo. |

### El contador de insumos — invariante central del sistema

`InsumoPresupuesto` lleva **dos** cantidades que se confunden con facilidad:

| Campo | Significado | ¿Muta en operación? |
|-------|-------------|---------------------|
| `cantidad_total` | Cantidad original importada de S10. Fuente de verdad permanente. En la UI es **CANTIDAD** / **PRESUPUESTADO**, solo informativa. | Nunca |
| `cantidad` | Contador de saldo restante. En la UI es **STOCK EN OBRA**, y es el límite real para pedir. | Sí |

El descuento ocurre **al generar la Guía de Remisión** (`PENDIENTE → EN_TRANSITO`), **no** al aprobar el requerimiento:

```python
insumo.cantidad = max(Decimal('0'), insumo.cantidad - cantidad_aprobada)   # nunca negativo
```

Aprobar un requerimiento solo escribe `cantidad_aprobada` y auto-genera una guía en `PENDIENTE`; recién "Guardar y generar guía" descuenta el contador, pasa el requerimiento a `ATENDIDO` y crea la `Entrada` en almacén. Confundir ambos momentos produce doble descuento. Para restaurar: Superadmin → Proyecto → Restablecer → Logística hace `cantidad = cantidad_total`.

En la vista **Req vs Atenciones**, `SOLICITADO` suma `cantidad_aprobada` de requerimientos en `APROBADO`/`PARCIAL`/`ATENDIDO`, mientras `ATENDIDO` solo suma los que están en `ATENDIDO`. Detalles y casos borde en `REGLAS_NEGOCIO.md`.

### Role / permission system (`config/permisos.py`)
- `tiene(user, permiso)` — returns bool; superuser and `es_superadmin` roles bypass all checks
- `permisos_dict(user)` — returns `{campo: bool}` for every field in `TODOS_LOS_PERMISOS`; injected globally as `{{ permisos }}` via context processor
- `proyectos_visibles(user)` — QuerySet of projects a user may see. Superuser, `es_superadmin`, or a role with `acceso_todos_proyectos` → all projects. A role *without* `acceso_todos_proyectos` → only projects where the user is a `ProyectoMiembro`. **No role assigned at all → sees every project** (fail-open default — deliberate, not a bug).
- Roles are created from the UI (Administración → Usuarios & Roles), not hardcoded
- `GRUPOS_PERMISOS` and `TODOS_LOS_PERMISOS` in `apps/configuracion/models.py` are the single source of truth for permission fields

### Sidebar nav block system
Each page template declares which sidebar link is "active" via `{% block nav_* %}active{% endblock %}`. See `templates/base.html` for the authoritative, current list — it changes as sections are added. Roughly grouped as: Presupuesto (`nav_pres_*`), Requerimientos (`nav_req`, `nav_req_lista`, `nav_req_vs`), Almacén (`nav_stock`, `nav_consumo`, `nav_entradas`, `nav_salidas`), Logística (`nav_logistica`, `nav_log_*`), Maquinaria (`nav_maquinaria`, `nav_personal`, `nav_reg_cuadrilla`, `nav_cuadrillas_admin`), Configuración (`nav_config_hub`).

### Template conventions
- **Never pass raw `request.POST` / `QueryDict` to templates** as a context variable named `datos` — Django 6 raises `VariableDoesNotExist` when template filters use dict keys as arguments (e.g. `{{ datos.nombre }}`). Always extract values explicitly: `'form_nombre': datos.get('nombre', '')`.
- **`miles` filter** (formats numbers as `200.669,58`) is registered as a builtin in `settings.py → TEMPLATES.OPTIONS.builtins`. No `{% load %}` needed.
- **`get_item` filter** (`{{ dict|get_item:key }}`) lives in `apps/presupuesto/templatetags/pres_fmt.py`. Requires `{% load pres_fmt %}` — it is **not** a builtin.
- All templates extend `templates/base.html`. Project-specific pages live in `templates/proyectos/`, `templates/presupuesto/`, etc.
- **Formularios compactos**: cuando un form quede visualmente muy alto o los inputs se sienten demasiado grandes, aplicar la clase utility `.form-compact` sobre el `<form>` (definida en `static/css/main.css`). Reduce labels a ~11px uppercase, inputs a ~12.5px con padding menor, card-headers/body más apretados, y gutter entre filas. Aplicado hoy en `templates/logistica/guia_form.html` y `templates/almacen/entrada_form.html`. **No copiar CSS inline en otros templates** — reusar esta clase.

### Authentication
`config/middleware.py → LoginRequiredMiddleware` redirects unauthenticated requests to `/login/`. Public path prefixes: `/login/`, `/admin/`, `/static/`, `/media/`.

### URL structure
```
/                               → redirect to proyectos:dashboard
/panel/dashboard/               → cross-project panel dashboard
/proyecto/<pk>/dashboard/       → single-project dashboard

/proyectos/                     → apps.proyectos.urls
/presupuesto/                   → apps.presupuesto.urls
/almacen/                       → apps.almacen.urls
/catalogo/                      → apps.catalogo.urls
/configuracion/                 → apps.configuracion.urls (hub, empresa, sunat, equipo, roles, usuarios, unidades, decimal, cargos, perfil)
/maquinaria/                    → apps.maquinaria.urls
/logistica/                     → apps.logistica.urls
/registro/                      → apps.registro.urls (log de actividad + notificaciones)
/requerimientos/                → apps.requerimientos.urls
```
Within each app's `urls.py`, project-scoped views are namespaced `proyecto/<int:proyecto_id>/...`; entity detail/edit views hang directly off the app root as `<int:pk>/...`.
