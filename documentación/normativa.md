# Normativa del Sistema — S&S Gestión

## Propósito

Este documento define las reglas de negocio, estándares y comportamientos esperados del sistema. Sirve como referencia para el desarrollo, configuración e importación de datos.

---

## 1. Estructura de Insumos

### 1.1 Tipos de insumo reconocidos

Los insumos se clasifican en 4 tipos principales:

| Tipo           | Tipo interno  |
|----------------|---------------|
| Mano de Obra   | `MANO_OBRA`   |
| Materiales     | `MATERIAL`    |
| Equipos        | `EQUIPO`      |
| Subpartidas    | `SUBPARTIDA`  |

### 1.2 Estructura de columnas por tipo

| Campo          | Mano de Obra | Materiales | Equipos | Subpartidas |
|----------------|:---:|:---:|:---:|:---:|
| Descripción    | ✓   | ✓   | ✓   | ✓   |
| Unidad         | ✓   | ✓   | ✓   | ✓   |
| Cuadrilla      | ✓   |     |     |     |
| Cantidad       | ✓   | ✓   | ✓   | ✓   |
| Precio S/      | ✓   | ✓   | ✓   | ✓   |
| Parcial S/     | ✓   | ✓   | ✓   | ✓   |

> **Cuadrilla** es exclusiva de Mano de Obra.

### 1.3 Cargos estándar de Mano de Obra

Los códigos de Mano de Obra **no están hardcodeados en el sistema** — los administra el superadmin desde **Configuración → Cargos de Mano de Obra**.

Ejemplo de configuración actual:

| Código | Nombre oficial | Variantes de importación                           |
|--------|---------------|----------------------------------------------------|
| 1      | CAPATAZ       | capataz, maestro, maestro de obra, capataz de obra |
| 2      | OPERARIO      | operario                                           |
| 3      | OFICIAL       | oficial                                            |
| 4      | PEÓN          | peon, peón, piones                                 |

**Regla**: al importar, si la descripción del recurso coincide con alguna variante configurada, el sistema asigna el código estándar correspondiente — ignorando el código que traiga el archivo fuente.

---

## 2. Módulo de Presupuesto

*(pendiente)*

---

## 3. Módulo de Logística / Almacén

*(pendiente)*

---

## 4. Módulo de Requerimientos

*(pendiente)*

---

*Última actualización: 2026-07-10*
