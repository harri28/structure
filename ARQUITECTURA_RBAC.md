# Arquitectura RBAC — S&S Gestión

> Documento de diseño del sistema de Roles y Permisos (Role-Based Access Control).
> Vive junto a `REGLAS_NEGOCIO.md` y `DECISIONES.md` como referencia autoritativa.
> Fecha inicial: 2026-11-13.

---

## 1. Estado actual (línea base antes del refactor)

### Modelos (`apps/configuracion/models.py`)

| Modelo | Función |
|--------|---------|
| `Rol` | Catálogo de roles. **~26 BooleanField** (uno por permiso) definidos por `GRUPOS_PERMISOS`. |
| `PerfilUsuario` | OneToOne con `User`. Campo `rol` (FK a `Rol`, nullable). Un rol **global** por usuario. |
| `ProyectoMiembro` | Membresía usuario↔proyecto. **Sin rol** — hoy solo marca pertenencia. |

### Resolución de permisos (`config/permisos.py`)

```
tiene(user, permiso)       → user.perfil.rol.<permiso>    (bool)
permisos_dict(user)        → {campo: bool} para todos los permisos
proyectos_visibles(user)   → QS de Proyecto; respeta `acceso_todos_proyectos` + membresía
```

Reglas especiales:
- `user.is_superuser` → bypass total (`tiene` → True para todo).
- `rol.es_superadmin` → bypass total.
- `rol.acceso_todos_proyectos` → ve todos los proyectos sin ser miembro.
- **Fail-open**: usuario sin perfil o sin rol asignado **ve todo**. Deliberado, no un bug.

### Roles sembrados (contrato, no editables)

Definidos en `apps/configuracion/migrations/0019_seed_roles_operativos.py`.
Listados en `ROLES_BLOQUEADOS = ['Jefe de obra', 'Logística', 'Almacenero']`.

Sus permisos vienen fijos por diseño. La UI los muestra read-only (candado); el handler `rol_editar` ignora el POST de permisos si el rol está bloqueado (defensa en profundidad contra POST manual).

### Grupos de permisos actuales

Definidos en `GRUPOS_PERMISOS` (fuente de verdad):

1. **Proyectos** — ver dashboard, crear/eliminar proyectos, gestionar personal, configurar.
2. **Presupuesto** — ver, editar.
3. **Almacén** — ver, crear reqs, aprobar reqs, entradas, salidas, cotizaciones, OC.
4. **Catálogo** — editar.
5. **Maquinaria y Cuadrilla** — ver, gestionar.
6. **Logística** — ver + 7 permisos finos (revisar reqs, inventarios, almacén log, control maq, abastecimiento, cotizaciones, guías).
7. **Administración** — usuarios, roles, empresa, actividad.
8. **Especiales** — acceso a todos los proyectos, superadmin.

Total: 28 permisos boolean.

---

## 2. Opciones evaluadas (backlog completo)

| # | Opción | Complejidad | Estado |
|---|--------|-------------|--------|
| 1 | Permisos por proyecto (rol distinto en obra A vs obra B) | Alta | **Fase 3 (en este plan)** |
| 2 | Jerarquía / herencia de roles | Media | Backlog |
| 3 | Permisos a nivel objeto (row-level: solo ver "sus" requerimientos) | Alta | Backlog |
| 4 | `Rol` → `Permiso` en tabla separada (M2M en vez de BooleanField) | Media | Backlog |
| 5 | UI mejorada: matriz visual + edición mejorada | Baja-Media | **Fase 1 (en este plan)** |
| 6 | Auditoría de cambios de roles | Baja | **Fase 2 (en este plan)** |
| 7 | MFA / sesiones / IP whitelist | Media-Alta | Backlog |

**Plan acordado (2026-11-13)**: implementar 5 → 6 → 1 en commits separados. Mantener fail-open actual. No tocar los 3 roles bloqueados.

---

## 3. Fase 1 — UI matriz visual

### Objetivos

- Que un administrador vea **todos los roles × todos los permisos en una sola matriz** para auditar de un vistazo.
- Que editar un rol sea más usable: grupos colapsables, botones "marcar todo este módulo", y poder **copiar permisos desde otro rol** como punto de partida.

### Cambios

**`apps/configuracion/views.py`**:
- `equipo` ahora arma `matriz_data` con filas=permisos (planas, con el grupo como header) y columnas=roles.
- `rol_crear` acepta `?copiar=<rol_id>` como GET para pre-llenar los checkboxes desde otro rol.
- `rol_editar` expone `otros_roles` para el selector "copiar desde".

**`templates/configuracion/equipo.html`**:
- Nueva pestaña **Matriz** al costado de Usuarios / Roles.
- La matriz es solo lectura (una celda = `✓` verde o vacío). Los roles bloqueados llevan candado en el encabezado.

**`templates/configuracion/rol_form.html`**:
- Cada grupo pasa a ser una "card" con header que dice cuántos permisos están marcados en ese grupo.
- Botones por grupo: *Marcar todo* / *Limpiar módulo*.
- Selector "Copiar permisos de" (solo al crear) → recarga la página con `?copiar=<id>` y pre-chequea.

### Sin cambios

- No se toca la DB.
- No se cambia `config/permisos.py`.
- Los endpoints `rol_crear`, `rol_editar`, `rol_eliminar` mantienen su contrato (URL, método, redirect).

---

## 4. Fase 2 — Auditoría de cambios de roles

### Objetivos

Dejar rastro de **quién** cambió **qué** en el subsistema de roles, para compliance y debugging ("¿por qué este usuario ya no puede aprobar?").

### Cambios

**`apps/configuracion/views.py`** — hooks al final del flujo exitoso en:

| Hook | Evento | Descripción generada |
|------|--------|----------------------|
| `rol_crear` | `CREAR` | `Rol creado: "<nombre>" — N permisos activos: <lista>` |
| `rol_editar` | `EDITAR` | `Rol editado: "<nombre>" — permisos agregados: [...], quitados: [...]` (diff) |
| `rol_eliminar` | `ELIMINAR` | `Rol eliminado: "<nombre>"` |
| `usuario_editar` | `EDITAR` | Si cambió `perfil.rol`: `Cambio de rol: <user> "<rol_viejo>" → "<rol_nuevo>"` |

Todas usan `log(request, accion, 'Configuración', descripcion)` del helper existente `apps/registro/utils.py`. **Sin nuevos modelos ni migraciones.**

### Consumo

El panel `/registro/actividad/` ya filtra por módulo. Los eventos de rol caen bajo "Configuración". Si surge la necesidad, en una fase futura se puede agregar un filtro específico "Cambios de rol" basado en `descripcion__istartswith='Rol '`.

---

## 5. Fase 3 — Permisos por proyecto

### Objetivos

Permitir que un mismo usuario tenga **rol distinto según el proyecto**:
- *Ejemplo*: Juan es `Jefe de obra` en la obra A, pero `Solo lectura` en la obra B.

### Diseño

**Elegido**: agregar un FK en `ProyectoMiembro` (no crear un modelo separado).

```python
class ProyectoMiembro(models.Model):
    proyecto = FK(Proyecto)
    usuario  = FK(User)
    rol      = FK(Rol, null=True, blank=True)   # NUEVO — opt-in
    agregado = DateTimeField(auto_now_add=True)
```

**Resolución de permisos** — nueva precedencia:

```
tiene(user, permiso, proyecto_id=None):
  1. is_superuser         → True
  2. perfil.rol.es_superadmin → True
  3. Si proyecto_id dado:
       miembro = ProyectoMiembro.objects.filter(usuario=user, proyecto_id=proyecto_id).first()
       if miembro and miembro.rol:
           return getattr(miembro.rol, permiso, False)
  4. Fallback: perfil.rol.<permiso>  (comportamiento actual)
```

**Migración**: `AddField(null=True)` — campo opcional, compatible hacia atrás. Si todos los `ProyectoMiembro` tienen `rol=NULL` (lo esperado al desplegar), el sistema se comporta exactamente como antes.

### Puntos de integración

- `config/permisos.py::tiene` → acepta `proyecto_id` opcional.
- `config/permisos.py::permisos_dict` → acepta `proyecto_id` opcional.
- `config/context_processors.py::permisos_usuario` → usa `request.resolver_match.kwargs.get('proyecto_id')` cuando la vista actual lo define; fallback a `request.session['proyecto_id']`. **Este es el cambio de comportamiento clave**: `{{ permisos }}` en templates pasa a reflejar permisos del proyecto que se está viendo (y queda consistente con la decisión que acaba de tomar `@requiere`).
- `config/permisos.py::proyecto_visible` decorator → sin cambios (sigue siendo pertenencia + `acceso_todos_proyectos`).
- `config/permisos.py::requiere(...)` → sin cambios de API pública. Internamente extrae `proyecto_id` de los `kwargs` de la URL cuando existe y lo pasa a `tiene()`. Si la URL no trae `proyecto_id`, cae al rol global (igual que antes). Evita que una navegación directa por URL salte la restricción cuando el proyecto activo de sesión es otro.

### UI

- Formulario `ProyectoMiembro` (agregar/editar miembro) → selector de rol opcional.
- En la pestaña Usuarios del `equipo.html` → cuando un usuario tiene miembros con rol específico, se muestra badge "rol por proyecto".

### Riesgos y mitigaciones

| Riesgo | Mitigación |
|--------|------------|
| Usuarios existentes rompen porque `permisos_dict` cambia su resolución | El default (rol en `ProyectoMiembro=NULL`) preserva el comportamiento. El cambio solo activa cuando un admin explícitamente asigna rol por proyecto. |
| Views que no reciben `proyecto_id` por URL (ej: `hub`, `empresa`) | `tiene()` sigue funcionando sin `proyecto_id` (cae al rol global). Nada que migrar. |
| El sidebar muestra items según permisos globales, no de proyecto | Context processor pasa a usar proyecto activo de sesión — sidebar se adapta automáticamente. |

---

## 6. Fuera de scope (deuda técnica reconocida)

### Fail-open por diseño

Usuario sin `PerfilUsuario` o con `perfil.rol = NULL` → ve todo. Esto es un riesgo de seguridad si se crean usuarios y se olvidan sin rol.

**Decisión actual (2026-11-13)**: no se cambia. Cerrarlo (fail-closed) requiere:
1. Migración que asigne un rol por defecto a todo usuario sin rol.
2. Hook en `User.post_save` para crear perfil + rol por defecto automáticamente.
3. Validación en `usuario_crear` que exige rol.

Se dejará para una fase posterior, cuando la base de usuarios sea estable.

### Row-level permissions (opción 3)

"Un usuario solo ve sus propios requerimientos" / "un trabajador solo ve su propia asistencia". Requiere un sistema de ownership por fila y un decorador tipo `@objeto_accesible`. Fuera de scope ahora; se puede atacar modelo por modelo sin refactor masivo.

### MFA / 2FA (opción 7)

Se implementa cuando haya un incidente de seguridad o lo pida el cliente. No bloquea nada del plan actual.

---

## 7. Convenciones

- Todos los permisos empiezan con `puede_` (o `acceso_` / `es_` para especiales).
- El `verbose name` del permiso (segundo elemento de las tuplas en `GRUPOS_PERMISOS`) es lo que se muestra en la UI. Al agregar un permiso: definir el campo en `Rol`, agregarlo al grupo correcto en `GRUPOS_PERMISOS`, migrar.
- Para proteger una vista nueva: `@requiere('puede_X')` en `apps/<x>/views.py`.
- Para proteger una URL por proyecto: apilar `@requiere('...')` + `@proyecto_visible`.
- No chequear `user.is_superuser` manualmente en vistas — usar `tiene()` (que ya cubre el bypass).
