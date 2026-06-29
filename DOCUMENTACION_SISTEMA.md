# S&S Gestión — Control de Obras
## Documentación del Sistema
**Versión 1.0 · Junio 2026**

---

## 1. Qué es este sistema

S&S Gestión es un ERP (sistema de gestión empresarial) diseñado para empresas constructoras. Permite administrar proyectos de construcción desde la etapa de formulación hasta la liquidación, controlando presupuestos, materiales, requerimientos, cotizaciones y órdenes de compra.

El sistema corre en una red local (LAN) y puede ser accedido desde cualquier dispositivo conectado a la misma red (PC, tablet, celular).

---

## 2. Tecnologías utilizadas

| Capa | Tecnología | Versión |
|---|---|---|
| Backend | Django (Python) | 6.0.6 |
| Base de datos | PostgreSQL | 16 |
| Lenguaje | Python | 3.12 |
| Estilos | Bootstrap | 5.3.3 |
| Íconos | Bootstrap Icons | 1.11.3 |
| Tipografía | Inter (Google Fonts) | — |
| Frontend JS | Vanilla JavaScript | — |

**Acceso:**
- PC local: `http://localhost:8000`
- Red local: `http://192.168.100.38:8000` *(reemplazar con la IP actual)*

---

## 3. Estructura de carpetas

```
c:\xampp\htdocs\structure\
│
├── config\                     Configuración global del proyecto Django
│   ├── settings.py             Variables de entorno, BD, apps instaladas
│   ├── urls.py                 Enrutamiento principal
│   ├── middleware.py           Middleware de autenticación (LoginRequired)
│   └── context_processors.py  Inyecta proyecto activo y lista de proyectos
│
├── apps\                       Módulos del sistema
│   ├── catalogo\               Catálogo de productos/insumos
│   ├── proyectos\              Gestión de proyectos de construcción
│   ├── presupuesto\            Presupuestos: contractual, adicional, deductivo
│   ├── almacen\                Requerimientos, entradas, salidas, OC, COT
│   └── configuracion\          Empresa y usuarios del sistema
│
├── templates\                  Plantillas HTML
│   ├── base.html               Layout principal (sidebar + topbar + contenido)
│   ├── dashboard.html          Página de inicio del sistema
│   ├── registration\
│   │   └── login.html          Pantalla de inicio de sesión
│   ├── catalogo\
│   ├── proyectos\
│   ├── presupuesto\
│   ├── almacen\
│   └── configuracion\
│
├── static\
│   └── css\
│       └── main.css            Estilos personalizados del sistema
│
├── media\                      Archivos subidos por el usuario
├── iniciar.bat                 Script para iniciar el servidor (doble clic)
└── manage.py                   Comando de administración de Django
```

---

## 4. Módulos del sistema

### 4.1 Dashboard `/proyectos/dashboard/`

Página de inicio. Muestra un resumen ejecutivo con:

| KPI | Descripción |
|---|---|
| Proyectos en ejecución | Total activos vs. total registrados |
| Requerimientos pendientes | Sin atender |
| Cotizaciones pendientes | Sin aprobar |
| Órdenes de compra activas | En estado borrador o enviada |

También muestra una tabla de proyectos en ejecución (con presupuesto y reqs. pendientes), los últimos 8 requerimientos y las últimas 6 entradas de almacén.

---

### 4.2 Catálogo `/catalogo/`

Registro maestro de productos e insumos compartido por todos los proyectos.

**Modelo `Producto`:**

| Campo | Tipo | Descripción |
|---|---|---|
| `codigo` | CharField | Código único (ej: MAT-001) |
| `descripcion` | CharField | Nombre completo del producto |
| `categoria` | CharField | MATERIAL / EQUIPO / EPP / UTIL / HERRAMIENTA / OTRO |
| `unidad` | CharField | UND / KG / M2 / ML / BLS / GAL / etc. |
| `activo` | BooleanField | Si está disponible para usar |

---

### 4.3 Proyectos `/proyectos/`

Núcleo del sistema. Cada proyecto representa una obra de construcción.

**Modelo `Proyecto`:**

| Campo | Tipo | Descripción |
|---|---|---|
| `codigo` | CharField | Código único (ej: PRY-2024-001) |
| `nombre` | CharField | Nombre completo de la obra |
| `cliente` | CharField | Entidad contratante |
| `ubicacion` | CharField | Dirección de la obra |
| `responsable` | CharField | Jefe de obra designado |
| `fecha_inicio` | DateField | Inicio de obra |
| `fecha_fin` | DateField | Término programado |
| `estado` | CharField | Ver estados abajo |
| `descripcion` | TextField | Descripción libre |

**Estados del proyecto:**

| Estado | Significado |
|---|---|
| `FORMULACION` | En planificación, sin ejecutar |
| `EJECUCION` | Obra en marcha (activa) |
| `PAUSADO` | Detenida temporalmente |
| `TERMINADO` | Obra física terminada |
| `LIQUIDADO` | Proyecto cerrado económicamente |

**URLs:**
```
/proyectos/dashboard/      Dashboard general
/proyectos/                Lista de proyectos
/proyectos/nuevo/          Crear proyecto
/proyectos/<id>/           Detalle del proyecto
/proyectos/<id>/editar/    Editar proyecto
/proyectos/<id>/eliminar/  Eliminar proyecto
```

---

### 4.4 Presupuesto `/presupuesto/`

Gestión de presupuestos de obra. Soporta 3 tipos.

#### Tipos de presupuesto

| Tipo | Descripción |
|---|---|
| **CONTRACTUAL** | Presupuesto original firmado con el cliente. Contiene la estructura completa de partidas con código, nombre, unidad, cantidad y precio unitario. |
| **ADICIONAL** | Ampliación del contrato. Se crea a partir del contractual. Hereda unidades y precios — solo se editan cantidades. Representa trabajos extra. |
| **DEDUCTIVO** | Reducción del contrato. Se crea a partir del contractual. Hereda unidades y precios — solo se editan cantidades. Representa trabajos eliminados. |

#### Modelos

**`Presupuesto`:**

| Campo | Tipo | Descripción |
|---|---|---|
| `proyecto` | FK → Proyecto | Proyecto al que pertenece |
| `tipo` | CharField | CONTRACTUAL / ADICIONAL / DEDUCTIVO |
| `presupuesto_base` | FK → self | Para adicionales/deductivos: apunta al contractual de origen |
| `nombre` | CharField | Nombre descriptivo |
| `archivo_origen` | CharField | Nombre del archivo Excel importado |
| `fecha_importacion` | DateTimeField | Cuándo se importó |
| `activo` | BooleanField | Estado del presupuesto |

**`Partida`** (árbol jerárquico):

| Campo | Tipo | Descripción |
|---|---|---|
| `presupuesto` | FK → Presupuesto | — |
| `padre` | FK → self | Partida padre (null = capítulo raíz) |
| `partida_origen` | FK → self | En adicionales/deductivos: partida del contractual de origen |
| `codigo` | CharField | Código (ej: 01.02.03.01) |
| `nombre` | CharField | Descripción de la partida |
| `nivel` | PositiveSmallIntegerField | Profundidad (1=capítulo, 2=subcap...) |
| `orden` | PositiveIntegerField | Posición dentro del nivel |
| `unidad` | CharField | Unidad de medida |
| `cantidad` | DecimalField | Metrado |
| `precio_unitario` | DecimalField | Precio por unidad |

> El total de una partida hoja = `cantidad × precio_unitario`.  
> El total de una partida padre = suma de totales de sus hijos.

**`RecursoPartida`** — Análisis de Precios Unitarios (APU):

| Campo | Descripción |
|---|---|
| `partida` | Partida a la que pertenece |
| `tipo` | MATERIAL / MANO_OBRA / EQUIPO / SUBCONTRATO / OTRO |
| `descripcion` | Nombre del recurso |
| `cantidad` | Cuánto se usa por unidad de partida |
| `precio_unitario` | Precio del recurso |

**`InsumoPresupuesto`** — Resumen total de insumos del presupuesto:

| Campo | Descripción |
|---|---|
| `presupuesto` | Presupuesto al que pertenece |
| `descripcion` | Nombre del insumo |
| `cantidad` | Cantidad total requerida en toda la obra |
| `costo_unitario` | Precio unitario |

**URLs:**
```
/presupuesto/proyecto/<id>/              Lista de presupuestos del proyecto
/presupuesto/proyecto/<id>/nuevo/        Crear presupuesto contractual
/presupuesto/<id>/                       Ver partidas
/presupuesto/<id>/insumos/              Ver insumos
/presupuesto/<id>/importar/             Importar desde Excel
/presupuesto/<id>/adicional/            Crear adicional
/presupuesto/<id>/deductivo/            Crear deductivo
/presupuesto/<id>/editar-cantidades/    Editar cantidades (adicional/deductivo)
```

---

### 4.5 Almacén `/almacen/`

Módulo más amplio. Gestiona el flujo completo de materiales.

#### Flujo normal de materiales

```
REQUERIMIENTO → (aprobación) → COTIZACIÓN → ORDEN DE COMPRA
                                                    ↓
                                               ENTRADA (llega el material)
                                                    ↓
                                               SALIDA (se despacha a la obra)
```

#### Modelos

**`Requerimiento`** — Solicitud de materiales:

| Campo | Descripción |
|---|---|
| `numero` | Correlativo por proyecto (ej: 001) |
| `fecha` | Fecha de la solicitud |
| `tipo` | MATERIAL / EQUIPO / EPP / UTIL / HERRAMIENTA / OTRO |
| `solicitante` | Persona que solicita |
| `estado` | PENDIENTE → APROBADO → ATENDIDO / PARCIAL / ANULADO |
| `detalles` | Lista de productos con cantidad y unidad |

**`Entrada`** — Ingreso de material al almacén:

| Campo | Descripción |
|---|---|
| `numero_guia` | Número de guía de remisión del proveedor |
| `serie` | Serie de la guía (ej: 001) |
| `fecha` | Fecha de recepción |
| `proveedor` | Nombre del proveedor |
| `requerimiento` | Requerimiento de origen (opcional) |
| `detalles` | Productos recibidos con cantidad y precio |

**`Salida`** — Despacho de material a la obra:

| Campo | Descripción |
|---|---|
| `numero` | Correlativo de salida |
| `fecha` | Fecha de despacho |
| `destino` | Frente de obra o área destino |
| `responsable` | Persona que recibe |
| `detalles` | Productos despachados con cantidad |

**`Cotización`** — Pedido de precios a proveedor:

| Campo | Descripción |
|---|---|
| `numero` | Correlativo |
| `proveedor` | Nombre del proveedor |
| `estado` | PENDIENTE / APROBADA / RECHAZADA |
| `detalles` | Productos cotizados con precio ofertado |

**`OrdenCompra`** — Documento formal de compra:

| Campo | Descripción |
|---|---|
| `numero` | Correlativo por proyecto (ej: OC-001) |
| `proveedor` | Proveedor seleccionado |
| `requerimiento` | Requerimiento de origen (opcional) |
| `cotizacion` | Cotización aprobada de origen (opcional) |
| `estado` | BORRADOR → ENVIADA → PARCIAL → COMPLETADA / ANULADA |
| `plazo_entrega` | Tiempo de entrega prometido |
| `detalles` | Productos con cantidad y precio pactado |

> **Stock y Kardex:** El sistema calcula el stock actual de cada producto sumando entradas y restando salidas. El kardex muestra el historial cronológico de movimientos valorizado.

**URLs:**
```
/almacen/proyecto/<id>/                         Dashboard de almacén
/almacen/proyecto/<id>/stock/                   Stock actual
/almacen/proyecto/<id>/stock/<pid>/kardex/      Movimientos de un producto
/almacen/proyecto/<id>/requerimientos/          Lista de requerimientos
/almacen/proyecto/<id>/entradas/                Lista de entradas
/almacen/proyecto/<id>/salidas/                 Lista de salidas
/almacen/proyecto/<id>/cotizaciones/            Lista de cotizaciones
/almacen/proyecto/<id>/ordenes/                 Lista de órdenes de compra
```

---

### 4.6 Configuración `/configuracion/`

Administración de la empresa y los usuarios del sistema.

**`ConfigEmpresa`:**

| Campo | Descripción |
|---|---|
| `razon_social` | Nombre legal de la empresa |
| `ruc` | RUC de la empresa |
| `direccion` | Dirección fiscal |
| `moneda` | Símbolo de moneda (`S/.` por defecto) |
| `igv` | Porcentaje de IGV (18% por defecto) |

**Usuarios** — usa el modelo `User` de Django:

| Campo | Descripción |
|---|---|
| `username` | Nombre de usuario para iniciar sesión |
| `first_name` / `last_name` | Nombre y apellido |
| `email` | Correo electrónico |
| `is_active` | Si puede iniciar sesión |
| `is_staff` | Rol STAFF |
| `is_superuser` | Rol SUPERADMIN (acceso total) |

**URLs:**
```
/configuracion/empresa/                  Ver/editar datos de empresa
/configuracion/usuarios/                 Lista de usuarios
/configuracion/usuarios/nuevo/           Crear usuario
/configuracion/usuarios/<id>/editar/     Editar usuario
/configuracion/usuarios/<id>/password/   Cambiar contraseña
/configuracion/usuarios/<id>/toggle/     Activar/desactivar
/configuracion/usuarios/<id>/eliminar/   Eliminar usuario
```

---

## 5. Autenticación y seguridad

- Toda ruta del sistema requiere estar autenticado.
- Si el usuario no ha iniciado sesión, es redirigido a `/login/`.
- Implementado con `config/middleware.py → LoginRequiredMiddleware`.

**Rutas públicas (sin login):**
- `/login/` — Pantalla de inicio de sesión
- `/admin/` — Panel de administración Django (solo superadmins)

**Configuración en `settings.py`:**
```python
LOGIN_URL           = '/login/'
LOGIN_REDIRECT_URL  = '/'        # Dashboard al iniciar sesión
LOGOUT_REDIRECT_URL = '/login/'  # Login al cerrar sesión
```

> Las contraseñas se almacenan hasheadas con PBKDF2-SHA256 (Django estándar).

---

## 6. Funcionamiento técnico clave

### Proyecto activo en sidebar

El sidebar muestra los links del proyecto activo usando **JavaScript + localStorage** del navegador. Cuando el usuario navega a cualquier página de un proyecto, el servidor inyecta el ID y nombre como variables de contexto. El JS las guarda en `localStorage` (claves: `ss_pid`, `ss_pnombre`) y rellena los hrefs del sidebar con el ID real. El sidebar así recuerda el último proyecto visitado aunque el usuario navegue a otras secciones.

### Formateo de números (español peruano)

Los números monetarios se muestran con formato español:
- `200.669,58` → punto para miles, coma para decimales

Implementado con un filtro de template personalizado en `apps/presupuesto/templatetags/pres_fmt.py`:

```django
{{ valor|miles:2 }}    → "200.669,58"
{{ cantidad|miles:4 }} → "1.000,0000"
```

Registrado como **builtin** en `settings.py`, por lo que está disponible en **todos los templates** sin necesidad de `{% load pres_fmt %}`.

### Árbol de partidas

Las partidas se renderizan como una **tabla plana** (no tablas anidadas). Cada `<tr>` lleva la clase `children-of-<padre_id>` para identificar la jerarquía. El JS maneja el colapso/expansión de forma recursiva: al colapsar un nodo, oculta también todos sus descendientes.

### Context processors

Dos funciones en `config/context_processors.py` inyectan datos en **todos los templates** automáticamente:
- `proyecto_activo` → ID y nombre del proyecto actual
- `todos_proyectos` → Lista completa de proyectos (para el modal selector del sidebar)

---

## 7. Base de datos

| Parámetro | Valor |
|---|---|
| Motor | PostgreSQL 16 |
| Base de datos | `ss_gestion` |
| Usuario | `postgres` |
| Contraseña | `1234` |
| Host | `localhost` |
| Puerto | `5432` |

**Tablas principales:**

| Tabla | Descripción |
|---|---|
| `auth_user` | Usuarios del sistema (Django built-in) |
| `catalogo_producto` | Catálogo de productos |
| `proyectos_proyecto` | Proyectos de construcción |
| `presupuesto_presupuesto` | Presupuestos por proyecto |
| `presupuesto_partida` | Partidas del presupuesto (árbol) |
| `presupuesto_recursopartida` | Recursos/APU por partida |
| `presupuesto_insumopresupuesto` | Insumos totales del presupuesto |
| `almacen_requerimiento` | Solicitudes de materiales |
| `almacen_entrada` | Ingresos de material al almacén |
| `almacen_salida` | Despachos desde almacén |
| `almacen_cotizacion` | Cotizaciones a proveedores |
| `almacen_ordencompra` | Órdenes de compra |
| `configuracion_configempresa` | Datos de la empresa |

**Aplicar migraciones:**
```bash
python manage.py makemigrations
python manage.py migrate
```

---

## 8. Cómo iniciar el sistema

**Opción A (recomendada):** Doble clic en `iniciar.bat`

El script hace automáticamente:
1. Cierra todos los procesos Python que usan el puerto 8000
2. Verifica que PostgreSQL esté activo
3. Aplica migraciones pendientes
4. Inicia el servidor Django en `0.0.0.0:8000`
5. Abre el navegador en `http://localhost:8000`

**Opción B (manual):**
```bash
cd c:\xampp\htdocs\structure
python manage.py runserver 0.0.0.0:8000
```

**Problema común — múltiples servidores en el puerto 8000:**

Si Django no responde o hay errores extraños, pueden existir varios procesos Python corriendo en el mismo puerto:
```bash
netstat -ano | findstr :8000
taskkill /PID <numero_pid> /F   # repetir para cada PID
```

---

## 9. Arquitectura de roles (en desarrollo)

El sistema implementará un **modelo híbrido: roles globales + membresía por proyecto**.

### Roles planificados

| Rol | Descripción | Acceso |
|---|---|---|
| `SUPERADMIN` | Administrador del sistema | Todo el sistema, usuarios, configuración, panel /admin/ |
| `JEFE_OBRA` | Administrador de obra | Proyectos asignados: presupuesto, aprobaciones, reportes |
| `ALMACENERO` | Almacenero de obra | Requerimientos, entradas, salidas, cotizaciones, OC — solo sus proyectos |
| `AUDITOR` | Auditor | Lectura total en todos los proyectos, sin modificar nada |
| `OPERARIO` | Albañil / campo | Solo crear requerimientos en sus proyectos asignados |

### Modelo ProyectoMiembro (a implementar)

```python
class ProyectoMiembro(models.Model):
    usuario  = models.ForeignKey(User, on_delete=models.CASCADE)
    proyecto = models.ForeignKey(Proyecto, on_delete=models.CASCADE)
    rol      = models.CharField(max_length=20, choices=ROLES)
```

Esto permite que un usuario sea Jefe de obra en el Proyecto A y Auditor en el Proyecto B. El almacenero solo verá los proyectos donde esté asignado.

---

## 10. Estado actual del sistema (Junio 2026)

### Implementado y funcionando

- [x] Autenticación (login / logout)
- [x] Middleware de protección de rutas
- [x] Dashboard con KPIs y actividad reciente
- [x] Catálogo de productos
- [x] Gestión completa de proyectos (CRUD)
- [x] Presupuesto contractual (importación Excel + árbol de partidas)
- [x] Presupuesto adicional y deductivo (edición de cantidades)
- [x] Insumos del presupuesto
- [x] Almacén: requerimientos, entradas, salidas
- [x] Almacén: cotizaciones, órdenes de compra
- [x] Stock y kardex por proyecto
- [x] Módulo de usuarios (CRUD interno)
- [x] Configuración de empresa
- [x] Formateo de números español (200.669,58)
- [x] Acceso por red local (0.0.0.0:8000)
- [x] Sidebar con proyecto activo persistente (localStorage)

### En desarrollo / próximo

- [ ] Sistema de roles granulares (JEFE_OBRA, ALMACENERO, AUDITOR, OPERARIO)
- [ ] Membresía de usuarios por proyecto (ProyectoMiembro)
- [ ] Permisos por módulo según rol
- [ ] Guías de remisión (seguimiento de materiales despachados de tiendas)
- [ ] Reportes y exportación a Excel/PDF
- [ ] Registro de auditoría (log de acciones de usuarios)

### Pendiente de evaluar

- [ ] Módulo de avance de obra (% completado por partida, curva S)
- [ ] Módulo de planillas / mano de obra
- [ ] Notificaciones internas entre usuarios
- [ ] Adjuntos de documentos (facturas, guías escaneadas)

---

## 11. Glosario

| Término | Significado |
|---|---|
| APU | Análisis de Precio Unitario — desglose de costo de un ítem del presupuesto |
| Contractual | Presupuesto original del contrato firmado |
| Adicional | Ampliación del contrato por trabajos extra |
| Deductivo | Reducción del contrato por trabajos eliminados |
| Django | Framework web Python en el que está construido el sistema |
| ERP | Enterprise Resource Planning — sistema integrado de gestión empresarial |
| FK | Foreign Key — relación entre tablas de la base de datos |
| Guía | Guía de remisión: documento que acompaña el despacho de bienes |
| IGV | Impuesto General a las Ventas (18% en Perú) |
| Insumo | Material o recurso necesario para ejecutar partidas de obra |
| Kardex | Registro cronológico de entradas y salidas de un producto |
| LAN | Red de área local (red interna de la empresa u obra) |
| Middleware | Capa de software que procesa peticiones HTTP antes de las vistas |
| Migración | Script que aplica cambios al esquema de la base de datos |
| OC | Orden de Compra |
| Partida | Ítem del presupuesto de obra (puede tener hijos = subpartidas) |
| PostgreSQL | Sistema de base de datos relacional usado por el sistema |
| REQ | Requerimiento de materiales |
| RUC | Registro Único de Contribuyentes (Perú) |
| Stock | Cantidad disponible de un producto en el almacén de obra |

---

*S&S Gestión — Control de Obras · v1.0 · 2026*
