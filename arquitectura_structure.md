# Arquitectura de S&S Gestión — Definición de Roles y RBAC

Documento vivo. Registra las decisiones de arquitectura que hemos tomado y las
que están pendientes de decidir. Complementa a:

- [`CLAUDE.md`](CLAUDE.md) — guía técnica para asistentes que trabajan el código
- [`REGLAS_NEGOCIO.md`](REGLAS_NEGOCIO.md) — reglas de dominio (flujos, fórmulas, invariantes)
- [`DECISIONES.md`](DECISIONES.md) — retiros de funcionalidad y cambios de UX

Última actualización: 2026-08-02.

---

## 1. Propósito del sistema

S&S Gestión es un ERP interno para un consorcio de construcción, organizado
alrededor del concepto de **proyecto** (obra civil). El superadmin crea los
proyectos y les asigna equipos. Cada proyecto opera en cierto grado aislado
—arquitectura *multi-proyecto en una sola BD*, no *multi-tenant* clásica—
con su propio Administrador de Obra (residente), su Almacenero y compartiendo
el área de Logística del consorcio.

El sistema trabaja con **un proyecto activo por sesión** (`request.session['proyecto_id']`)
y toda la UI se contextualiza a ese proyecto.

---

## 2. Los tres roles operativos (más el superadmin)

**Aclaración semántica importante** — "Administrador de Obra" NO significa
"administrador del sistema". En términos de ingeniería civil, es el
**residente de obra**: puede haber varios en el sistema, cada uno dentro
de su propio proyecto. El "administrador del sistema" es el Superadmin.

### 2.1 Superadmin

Un solo usuario en la vida real del consorcio (hoy es el desarrollador y dueño
del sistema). Bypassa todos los permisos mediante `is_superuser` o `rol.es_superadmin`.

**Su dashboard:** `panel_dashboard` en `/panel/dashboard/` — vista cross-project.
El único que puede llegar a esa URL.

Responsabilidades exclusivas:
- Crear y eliminar proyectos
- Configurar el consorcio (Empresa, SUNAT, Unidades)
- Crear y editar roles
- Crear y editar usuarios (los 3 tipos operativos + eventuales otros)

### 2.2 Administrador de Obra (Residente)

Es el responsable de UN proyecto. Puede coexistir con otros Admins de Obra en
otros proyectos. NO administra el sistema.

Módulos a los que accede desde el sidebar de su proyecto:

**Su dashboard:** `proyecto_dashboard` en `/proyecto/<pk>/dashboard/` — vista con
KPIs del proyecto (avance físico, financiero, requerimientos, etc.). Es el
dashboard "general" de un proyecto; cualquiera con `puede_ver_dashboard` lo
puede ver.

| Sección | Sub-links | Permisos que lo desbloquean |
|---|---|---|
| Dashboard del proyecto | — | `puede_ver_dashboard` |
| Presupuesto | Actividad, Partidas, Insumos, Adicionales, Deductivos, Importar | `puede_ver_presupuesto`, `puede_editar_presupuesto` |
| Requerimientos | Requerimiento, Req vs Atenciones | `puede_crear_requerimientos`, `puede_aprobar_requerimientos` |
| Cuadrilla | — | `puede_ver_maquinaria`, `puede_gestionar_maquinaria` |
| Maquinaria | — | igual |
| Personal | — | **`puede_gestionar_personal`** *(por crear)* |
| Catálogo | — | `puede_editar_catalogo` |
| Actividad | — | **`puede_ver_actividad`** *(por crear)* |
| Perfil | — | siempre |

Ver §4 para los permisos que faltan crear en el modelo.

### 2.3 Logística

Responsable del área de logística del consorcio. Atraviesa proyectos
(no está anclado a uno solo).

**Su dashboard:** `logistica:dashboard` en `/logistica/proyecto/<id>/` — vista
propia con KPIs de logística (requerimientos entrantes, guías en tránsito,
inventarios, etc.). Es el "dashboard de logística", no el general del proyecto.

| Sección | Permiso |
|---|---|
| Logística (dashboard) | `puede_ver_logistica` |
| Requerimientos recibidos + Consolidados | `puede_revisar_reqs_log` |
| Cotizaciones | `puede_gestionar_cotizaciones_log` |
| Guías de Remisión | `puede_gestionar_logistica` |
| Inventarios | `puede_gestionar_inventarios_log` |
| Almacén (de logística) | `puede_gestionar_almacen_log` |
| Control Maq. y Equipos | `puede_gestionar_ctrl_maq_log` |
| Perfil | siempre |

*(Nota: "Abastecimiento" fue retirado del sidebar el 2026-08-02, ver [`DECISIONES.md`](DECISIONES.md).)*

### 2.4 Almacenero

Operador de almacén de un proyecto. Registra entradas y salidas de material.

**Su dashboard:** `almacen:dashboard` en `/almacen/proyecto/<id>/` — vista propia
con KPIs de almacén (stock crítico, movimientos recientes, etc.). Es el
"dashboard del almacenero".

| Función | Permiso |
|---|---|
| Ver almacén, stock y kardex | `puede_ver_almacen` |
| Crear requerimientos (solo BORRADOR — no puede enviar) | `puede_crear_requerimientos` |
| Aprobar llegadas de materiales | `puede_gestionar_entradas` |
| Registrar salidas | `puede_gestionar_salidas` |
| Perfil | siempre |

**No tiene:** `puede_aprobar_requerimientos`, `puede_gestionar_cotizaciones`,
`puede_gestionar_oc`.

---

### 2.5 Patrón: cada rol tiene su propio dashboard

El sistema tiene 4 dashboards distintos, uno por rol operativo:

| Rol | Vista | URL | Permiso |
|---|---|---|---|
| Superadmin | `panel_dashboard` | `/panel/dashboard/` | bypass |
| Admin de Obra | `proyecto_dashboard` | `/proyecto/<pk>/dashboard/` | `puede_ver_dashboard` |
| Logística | `logistica:dashboard` | `/logistica/proyecto/<id>/` | `puede_ver_logistica` |
| Almacenero | `almacen:dashboard` | `/almacen/proyecto/<id>/` | `puede_ver_almacen` |

Adicionalmente existe `maquinaria:dashboard` — utilidad, no anclado a un rol.

Cuando un usuario aterriza en el sistema, debe caer en el dashboard de su rol.
Hoy la lógica está parcialmente implementada:

- `proyecto_dashboard` verifica `_sin_dashboard()` y, si el usuario no tiene
  `puede_ver_dashboard`, **redirige a `logistica:dashboard`**
  ([apps/proyectos/views.py:54](apps/proyectos/views.py#L54))

**Bug latente ⚠️** El fallback está hardcodeado a Logística. Un Almacenero
que llegue al `/proyecto/<pk>/dashboard/` termina en el dashboard de Logística
en vez del suyo. Y como no tiene `puede_ver_logistica`, con los decoradores ya
aplicados en la Fase 2 va a rebotar de vuelta al dashboard con mensaje de
"sin permiso". Loop de redirects potencial.

**Fix propuesto** (pendiente): `_sin_dashboard()` debe elegir el destino según
qué permiso *sí* tiene el usuario:

```python
if tiene(user, 'puede_ver_logistica'):
    return redirect('logistica:dashboard', proyecto_id=pk)
if tiene(user, 'puede_ver_almacen'):
    return redirect('almacen:dashboard', proyecto_id=pk)
# fallback: perfil propio o mensaje "sin acceso a este proyecto"
```

## 3. Flujo de requerimientos con Opción B (aprobación interna)

Este es un cambio de comportamiento importante respecto a
[`REGLAS_NEGOCIO.md §2`](REGLAS_NEGOCIO.md).

**Semántica nueva de los dos permisos existentes:**

- `puede_crear_requerimientosCrei` → crear y editar requerimientos en estado BORRADOR
- `puede_aprobar_requerimientos` → **pulsar "Enviar a Logística"** (pasar BORRADOR → ENVIADO)

**Resultado operativo:**

- El Almacenero crea un requerimiento en BORRADOR. **No ve el botón Enviar.**
- El Administrador de Obra ve una bandeja con todos los BORRADORes del proyecto
  (los suyos y los del Almacenero) y decide cuáles enviar a Logística.
- El resto del flujo (ENVIADO → EN_REVISION → APROBADO → ATENDIDO) sigue igual
  y sigue documentado en `REGLAS_NEGOCIO.md`.

**Diseño elegido: sin estado nuevo.** El BORRADOR sigue siendo BORRADOR
independientemente de quién lo creó. El filtro es de permisos, no de estado.
Es más simple y no requiere migración de datos.

**Alternativa descartada:** agregar un estado `PENDIENTE_APROB_OBRA` con
migración y columna nueva. Se reserva por si la operación real muestra que
necesita distinguirse visualmente en la bandeja.

---

## 4. Cambios pendientes al modelo `Rol`

Tres `BooleanField` nuevos a agregar en [`apps/configuracion/models.py`](apps/configuracion/models.py)
+ una migración + actualizar `GRUPOS_PERMISOS` para que aparezcan en el UI de creación de roles:

```python
# En GRUPOS_PERMISOS, dentro del grupo 'Proyectos' o uno nuevo:
('puede_gestionar_personal',    'Gestionar personal del proyecto (obreros, cuadrillas)'),
('puede_ver_actividad',         'Ver el registro de actividad del sistema'),
('puede_configurar_proyecto',   'Configurar datos del proyecto (nombre, fechas, presupuesto)'),
```

Y luego ajustar [`templates/base.html`](templates/base.html):

- Link **Personal** (hoy línea ~187): cambiar el `{% if %}` de
  `puede_crear_proyectos or puede_administrar_usuarios` a
  `puede_gestionar_personal`.
- Link **Actividad** (hoy línea ~293): cambiar el `{% if %}` de
  `puede_administrar_usuarios` a `puede_ver_actividad`.
- Link **Configuración** (nuevo, del proyecto): apuntar al nuevo módulo
  `configuracion:proyecto` en vez de `configuracion:hub`, gateado por
  `puede_configurar_proyecto`.

Estos permisos existen conceptualmente para desligar los links del Admin
de Obra de permisos de administración fuerte que hoy son la única llave.

---

## 5. Decisiones ya ejecutadas en el código (2026-08-01 y 2026-08-02)

### Fase 0 — Documentación
- [`CLAUDE.md`](CLAUDE.md) reescrito y verificado contra el código.
  Incluye la regla del contador de insumos, aclaración de que el SSE de
  notificaciones está huérfano, y advertencia de que
  `REGLAS_NEGOCIO.md §7` está desactualizado (las notificaciones sí están
  conectadas, contra lo que dice ese documento).

### Fase 1 — Mecanismo de enforcement
- Decorador `@requiere('permiso'[, 'otro_permiso'])` en
  [`config/permisos.py`](config/permisos.py). Semántica OR. Superuser y
  `es_superadmin` pasan automáticamente. Al fallar redirige a
  `proyectos:dashboard` con `messages.warning`.

### Fase 2 — Aplicación a las 3 áreas de mayor riesgo

**Módulo `configuracion` (13 vistas)** — cierra la escalada de privilegios
(crear roles superadmin, crear usuarios con `is_superuser`).

| Permiso | Vistas |
|---|---|
| `puede_administrar_roles` | `roles`, `rol_crear`, `rol_editar`, `rol_eliminar` |
| `puede_administrar_usuarios` | `usuarios`, `usuario_crear`, `usuario_editar`, `usuario_password`, `usuario_eliminar`, `usuario_toggle` |
| `puede_configurar_empresa` | `empresa` |
| OR de las 3 | `hub` |
| OR usuarios/roles | `equipo` |

**Módulo `logistica` (22 vistas)** — cierra el descuento de contadores
de insumos ([views.py:356](apps/logistica/views.py#L356)).

| Permiso | Vistas |
|---|---|
| `puede_ver_logistica` | `dashboard` |
| `puede_revisar_reqs_log` | `ping_reqs`, `requerimientos_log`, `consolidados_log`, `req_detalle_log`, `req_revisar_log` |
| `puede_gestionar_logistica` | `guia_lista`, `guia_crear`, `guia_detalle`, `guia_editar`, `guia_estado` (**descuenta contadores**), `guia_eliminar`, `guia_imprimir`, `guia_bienes_api`, `guias_pendientes_api`, `transportista_lista`, `transportista_crear`, `transportista_editar` |
| `puede_gestionar_inventarios_log` | `inventarios` |
| `puede_gestionar_almacen_log` | `almacen_log` |
| `puede_gestionar_ctrl_maq_log` | `control_maquinaria` |
| `puede_gestionar_abastecimiento` | `abastecimiento` *(vista queda pero link retirado)* |

**Progreso RBAC global:**

| Fase | Vistas protegidas | % del total (189) |
|---|---|---|
| Antes | 2 (guardas manuales en `proyectos`) | 1% |
| Después de `configuracion` | 15 | 8% |
| **Después de `logistica`** | **37** | **20%** |

Las 22 vistas restantes (`presupuesto`, `almacen`, `maquinaria`, `requerimientos`,
`catalogo`, `registro`, más de `proyectos`) están pendientes.

### Fase 2b — Limpieza de sidebar
- Retirado link **Cuadrillas** de Administración (duplicaba
  `Proyecto → Cuadrilla`).
- Retirado link **Abastecimiento** de Logística
  (motivo y ruta de restauración en [`DECISIONES.md`](DECISIONES.md)).

---

## 6. Pendientes de decisión

Ordenados por criticidad para desbloquear el trabajo.

### 6.1 "Configuración" en el sidebar del Admin de Obra — DECIDIDO (opción B)

**Resolución (2026-08-02):** se crea un módulo nuevo `configuracion:proyecto`
dedicado a la configuración del proyecto activo (nombre, fechas, presupuesto,
etc.). Ver [`REGLAS_NEGOCIO.md §13`](REGLAS_NEGOCIO.md) para el detalle del
alcance, permiso nuevo (`puede_configurar_proyecto`) y preguntas de diseño
abiertas.

**No se implementa en este ciclo.** Primero se cierra el flujo base de RBAC
y la Opción B.

### 6.2 Bug reportado por Sarita — `presupuesto/importar/`

Usuaria de Logística llegó por URL directa a `/presupuesto/3/importar/` y el
sistema no la bloqueó (el módulo `presupuesto` no tiene ni un `@requiere`).

Plan de decoración de las 21 vistas de `presupuesto`:

| Permiso | Vistas |
|---|---|
| `puede_editar_presupuesto` | `crear`, `importar`, `eliminar`, `partidas_limpiar`, `insumos_limpiar`, `modificacion_crear`, `modificacion_editar`, `modificacion_estado`, `modificacion_eliminar`, `acu_recurso_editar`, `acu_recurso_eliminar`, `ml_importar` |
| `puede_ver_presupuesto` | `lista`, `detalle`, `insumos`, `modificacion_detalle`, `partida_hijos`, `partida_panel`, `ml_buscar` |
| OR de los dos | `acu_partida`, `ml_sugeridos` |

Pendiente de aplicar.

### 6.3 Otros módulos por decorar

En orden de riesgo restante:

1. `requerimientos` (12 vistas, 7 mutaciones) — cierra el circuito con
   Logística y aplica la Opción B (gatear `enviar` con `puede_aprobar_requerimientos`)
2. `almacen` (32 vistas, 14 mutaciones)
3. `maquinaria` (31 vistas, 10 mutaciones)
4. `proyectos`, `catalogo`, `registro`, resto (menor riesgo)

### 6.4 Menú desde el backend (registro declarativo)

Discutido pero no implementado. Idea: un solo `MENU = [...]` en
`config/navegacion.py` que alimente tanto el sidebar (context processor)
como el decorador (`@requiere`). Evita que menú y permisos se desincronicen
—hoy hay 7 líneas de código muerto tipo `or permisos.es_superadmin`
en el sidebar—.

Rentable solo si vamos a rehacer el sidebar de todos modos. No urgente.

---

## 7. Enforcement futuro obligatorio: la app Flutter

De [`contexto_app.md`](contexto_app.md): hay una app móvil Flutter offline-first
planificada. Se conectará al backend vía HTTP JSON con JWT.

Un cliente HTTP **no tiene sidebar** que lo guíe — solo URLs. Por eso, antes
de exponer los endpoints JSON de la app Flutter, TODO el sistema debe estar
bajo `@requiere`. Es requisito, no higiene.

**Recomendación de plazo:** completar Fase 2 de RBAC (las 189 vistas) antes de
comenzar el diseño de endpoints de la app.

---

## 8. Cómo probar el RBAC en local

```powershell
# 1. Reiniciar el servidor con código nuevo
python servidor_asgi.py       # limpia el puerto 8000 y arranca Uvicorn

# 2. Verificar que responde
curl -I http://127.0.0.1:8000/login/     # debe ser 200

# 3. Probar en el navegador
# - Como superadmin: acceso a todo, sin cambios visibles
# - Como Sarita (rol Logística): entrar por URL a /configuracion/usuarios/
#   debe redirigir al dashboard con mensaje amarillo
```

Nota: los templates de Django recargan solos, no requieren reinicio del servidor.
Los cambios de código Python sí (Uvicorn no tiene `--reload` habilitado en
`servidor_asgi.py`).

---

## 9. Registro de sesiones de arquitectura

| Fecha | Qué se decidió / ejecutó |
|---|---|
| 2026-08-01 | Reescritura de `CLAUDE.md` verificada contra código. Corrección de memoria (SSE huérfano, servidor ASGI, sin credenciales hardcoded). |
| 2026-08-02 | Diagnóstico RBAC completo (189 vistas, 2 protegidas). Decorador `@requiere` creado. 13 vistas de `configuracion` + 22 de `logistica` protegidas. Sidebar limpiado (Cuadrillas duplicado + Abastecimiento). Definición de los 3 roles operativos. Diseño de Opción B para requerimientos. Descubrimiento de permisos faltantes (`puede_gestionar_personal`, `puede_ver_actividad`). Camino A confirmado (RBAC0 con permisos-columna, no refactor a canónico). |
| 2026-08-02 | Aclaración del patrón "cada rol tiene su propio dashboard" (§2.5). Descubrimiento del bug latente en `_sin_dashboard()` que redirige siempre a logística en vez de al dashboard del rol. |
