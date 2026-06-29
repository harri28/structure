# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Development server (use one or the other, not both)
python manage.py runserver          # Django dev server (port 8000)
python servidor.py                  # Waitress WSGI server (production, port 8000)

# Database
python manage.py makemigrations <app_name>
python manage.py migrate
python manage.py createsuperuser

# Static files (required after any CSS/JS change for Apache to serve them)
python manage.py collectstatic --noinput
```

There are no tests implemented — `tests.py` files are empty stubs.

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
- WhiteNoise permite que Waitress sirva estáticos directamente sin Apache

**Reinicio correcto del servidor:**
```powershell
# Verificar que no quedan procesos viejos
netstat -ano | findstr ":8000 "
# Matar cada PID listado, luego:
python servidor.py
```

## Stack

- **Django 6.0.6** · Python 3.12 · PostgreSQL (`ss_gestion`, user=`postgres`, password=`1234`, localhost:5432)
- **Serving (Windows)**: Apache (XAMPP) on **port 80** as reverse proxy → Waitress on port 8000. Apache serves `/static/` and `/media/` directly via `Alias` in `c:\xampp\apache\conf\extra\httpd-vhosts.conf`. **Always access via port 80** — accessing port 8000 directly skips Apache and CSS/static files won't load. Run `collectstatic` after any CSS/JS change.
- **Frontend**: Bootstrap 5.3.3 + Bootstrap Icons 1.11.3 + Inter font. No build step — all CDN except `static/css/main.css`.

## Project Architecture

### Single-project model
The system operates on **one active project at a time**. `Proyecto.activo = BooleanField` controls which project drives the entire UI. `Proyecto.save()` automatically deactivates all others when one is set active. Switching projects is an admin operation via **Administración → Proyectos**.

The active project is injected globally via `config/context_processors.py → proyecto_activo()`, which does a simple `Proyecto.objects.filter(activo=True).first()`. All sidebar links use `{{ proyecto_activo.pk }}` directly in templates.

### Apps (`apps/`)

| App | Responsibility |
|-----|---------------|
| `proyectos` | `Proyecto` (single active), `ProyectoMiembro` (team), project admin |
| `presupuesto` | `Presupuesto` → `Partida` tree (up to 5 levels) + `RecursoPartida` (ACU) + `InsumoPresupuesto` + `Modificacion`/`PartidaModificacion`. Imports S10 `.xls` and generic `.xlsx` via `importador.py`. `Presupuesto` stores `gastos_generales_pct`, `utilidad_pct`, `igv_pct`; computes `costo_directo()`, `gastos_generales()`, `utilidad()`, `sub_total()`, `igv()`, `total_presupuesto()`. |
| `almacen` | `Requerimiento` → `Entrada` → `Salida` → `Cotizacion` → `OrdenCompra`. All tied to `Proyecto` + `Producto` from catálogo |
| `catalogo` | `Producto` — master product catalog shared across all projects |
| `configuracion` | `ConfigEmpresa` (singleton via `get()`), `Rol` (18 BooleanField permissions), `PerfilUsuario` (User↔Rol) |

### Role / permission system (`config/permisos.py`)
- `tiene(user, permiso)` — returns bool; superuser and `es_superadmin` roles bypass all checks
- `permisos_dict(user)` — returns `{campo: bool}` for all 18 permissions; injected globally as `{{ permisos }}` via context processor
- Roles are created from the UI (Administración → Usuarios & Roles), not hardcoded
- `GRUPOS_PERMISOS` and `TODOS_LOS_PERMISOS` in `apps/configuracion/models.py` are the single source of truth for permission fields

### Sidebar nav block system
Each page template declares which sidebar link is "active" via `{% block nav_* %}active{% endblock %}`:

`nav_dashboard` · `nav_proyecto` · `nav_presupuesto` · `nav_almacen` · `nav_req` · `nav_entradas` · `nav_salidas` · `nav_cot` · `nav_proyectos` · `nav_catalogo` · `nav_config_empresa` · `nav_config_equipo`

### Template conventions
- **Never pass raw `request.POST` / `QueryDict` to templates** as a context variable named `datos` — Django 6 raises `VariableDoesNotExist` when template filters use dict keys as arguments (e.g. `{{ datos.nombre }}`). Always extract values explicitly: `'form_nombre': datos.get('nombre', '')`.
- **`miles` filter** (formats numbers as `200.669,58`) is registered as a builtin in `settings.py → TEMPLATES.OPTIONS.builtins`. No `{% load %}` needed.
- **`get_item` filter** (`{{ dict|get_item:key }}`) lives in `apps/presupuesto/templatetags/pres_fmt.py`. Requires `{% load pres_fmt %}` — it is **not** a builtin.
- All templates extend `templates/base.html`. Project-specific pages live in `templates/proyectos/`, `templates/presupuesto/`, etc.

### Authentication
`config/middleware.py → LoginRequiredMiddleware` redirects unauthenticated requests to `/login/`. Public paths: `/login/`, `/admin/`.

### URL structure
```
/                               → redirect to proyectos:dashboard
/proyectos/                     → admin project list (activate/create/edit)
/proyectos/<pk>/                → project detail (Descripción)

/presupuesto/proyecto/<pk>/     → presupuesto lista (monto vigente + modificaciones)
/presupuesto/<pk>/              → presupuesto detalle (árbol de partidas)
/presupuesto/<pk>/insumos/      → resumen de insumos
/presupuesto/<pk>/importar/     → importar S10 XLSX
/presupuesto/partida/<pk>/acu/  → ACU por partida hoja (CRUD recursos)
/presupuesto/partida/<pk>/ml/sugeridos/   → JSON: recursos ML sugeridos
/presupuesto/partida/<pk>/ml/importar/    → POST: importar recursos ML
/presupuesto/<pk>/ml/buscar/?q= → JSON: búsqueda semántica TF-IDF

/presupuesto/proyecto/<pk>/modificacion/nueva/  → crear Adicional/Deductivo/Vinculante
/presupuesto/modificacion/<pk>/                 → detalle modificación
/presupuesto/modificacion/<pk>/editar/

/almacen/proyecto/<pk>/              → warehouse dashboard
/almacen/proyecto/<pk>/requerimientos/
/almacen/proyecto/<pk>/entradas/
/almacen/proyecto/<pk>/salidas/
/almacen/proyecto/<pk>/cotizaciones/
/almacen/proyecto/<pk>/ordenes/

/configuracion/equipo/          → combined Users & Roles page (tabs)
/configuracion/empresa/
```
