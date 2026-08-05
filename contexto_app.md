# Contexto App Móvil — S&S Gestión

Documento de definición de la app Flutter complementaria al sistema web.
No genera código — define arquitectura y decisiones antes de implementar.

---

## Objetivo

App móvil offline-first para uso en campo, donde frecuentemente no hay conexión
a internet. Los datos se guardan localmente y se sincronizan con el servidor web
cuando hay conexión disponible.

---

## Módulos incluidos

- Requerimientos
- Logística
- Almacén

---

## Usuarios y roles

- **1 usuario por módulo / rol** — no hay edición simultánea de los mismos datos.
- Los roles son los mismos que en el sistema web (ya existente en `configuracion`).
- Los permisos deben ser editables desde la app.
- Todos los permisos de Almacén están disponibles en la app.

---

## Arquitectura offline-first

### Almacenamiento local
- **SQLite** en el dispositivo (soporte nativo en Flutter via `sqflite`).
- Todos los cambios se guardan primero en local, luego se sincronizan.

### Cola de sincronización
- Cada acción offline (crear, modificar, eliminar, cancelar) se encola.
- Al recuperar conexión, la cola se envía al servidor en orden.
- Estrategia de conflictos: **el último en sincronizar gana** (sin riesgo real
  dado que hay 1 usuario por rol).

### Indicador de estado
- La app muestra visualmente si está online u offline.
- Muestra cuántas acciones están pendientes de sincronizar.

---

## Datos descargados offline (por proyecto activo)

Solo se descarga el proyecto activo — no todos los proyectos.

| Datos | Motivo |
|-------|--------|
| Catálogo de insumos | Necesario para crear requerimientos sin internet |
| Requerimientos del proyecto | Para consultar y modificar en campo |
| Stock de almacén | Para registrar entradas/salidas |
| Guías de remisión pendientes | Para gestión de logística en campo |

**No se descarga:** presupuesto completo, historial extenso — son pesados y no
se usan en campo.

---

## Acciones disponibles offline

### Requerimientos
- Crear requerimiento
- Modificar requerimiento
- Cancelar / anular requerimiento

### Logística
- Revisar y aprobar requerimientos
- Gestionar guías de remisión pendientes

### Almacén
- Registrar entradas
- Registrar salidas
- Consultar stock

---

## Stack técnico

- **Lenguaje:** Flutter (Dart)
- **Salida:** APK Android (instalación directa, sin Play Store)
- **Proyecto:** Carpeta separada del repo Django, ventana independiente en VS Code
- **Conexión al backend:** HTTP JSON → endpoints a agregar en Django
- **Autenticación:** Token-based (JWT) — diferente a las sesiones de cookie del web

---

## Pendientes de definir

- [ ] Pantallas exactas de cada módulo
- [ ] Diseño / navegación de la app
- [ ] Endpoints JSON a agregar en Django
- [ ] Estrategia de sincronización parcial (¿qué pasa si la cola falla a mitad?)
- [ ] Versión mínima de Android objetivo
