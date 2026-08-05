# Decisiones de Arquitectura y Producto — S&S Gestión

Registro cronológico de decisiones que cambian el sistema o retiran funcionalidad.
Complementa a `REGLAS_NEGOCIO.md` (que documenta el *cómo* funciona) explicando
el *por qué* de decisiones ya tomadas.

---

## 2026-08-02 — Retiro del sub-módulo "Abastecimiento" del sidebar de Logística

**Qué se hizo:** Se eliminó el link `Logística → Abastecimiento` del sidebar
(`templates/base.html`). El código de la vista `abastecimiento`, su URL
(`logistica:abastecimiento`) y el permiso `puede_gestionar_abastecimiento`
**permanecen** en el repositorio — solo se ocultó la puerta de entrada visible.

**Por qué:** Al día de hoy, el flujo de abastecimiento se realiza desde
`Logística → Cotizaciones`, y la función específica del sub-módulo
"Abastecimiento" no está clarificada por el equipo. Mantenerlo visible en
el sidebar genera confusión sin aportar valor operativo.

**Cómo restaurarlo si más adelante se decide reactivarlo:**
1. Recuperar el bloque `{% if permisos.puede_gestionar_abastecimiento ... %}`
   dentro de `<div id="nav-logistica">` en `templates/base.html` (git log
   muestra la versión previa).
2. La vista y la URL siguen funcionando: `/logistica/proyecto/<id>/abastecimiento/`.
3. Activar `puede_gestionar_abastecimiento` en el rol correspondiente.

**Pendiente:** definir con el equipo qué debe hacer este módulo antes de
reactivarlo — o eliminar el permiso, la URL y la vista en un segundo paso
si se confirma que Cotizaciones cubre por completo el caso de uso.

---

## 2026-08-02 — Eliminación del link duplicado "Cuadrillas" en Administración

**Qué se hizo:** Se eliminó el link `Administración → Cuadrillas` del sidebar
(`templates/base.html`, apuntaba a `maquinaria:cuadrilla_lista`). El link
`Proyecto → Cuadrilla` (que apunta a `maquinaria:registro_lista`) permanece
como único acceso.

**Por qué:** Redundancia visual. El grupo del proyecto (PYR-XXX) ya expone
el módulo de Cuadrilla y era el punto de entrada esperado por el equipo.
El link duplicado en Administración generaba dos caminos al mismo dominio.

**Nota técnica:** el catálogo global de cuadrillas (`maquinaria:cuadrilla_lista`)
sigue siendo accesible por URL directa y desde el detalle de la cuadrilla
dentro del proyecto. Solo se retiró el link redundante del sidebar.
