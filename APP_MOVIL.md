# App móvil S&S Gestión — plan y estado actual

Documento de referencia sobre el diseño, la decisión de stack y el estado de
construcción de la app móvil para el sistema S&S Gestión. Vive al lado de
`CLAUDE.md` para que cualquier futuro colaborador (o sesión de Claude) pueda
retomar el hilo sin perder contexto.

---

## 1. Objetivo

Dar a los operadores en obra (empezando por el **Jefe de Obra**) una app
Android nativa que les deje:

- Crear **requerimientos de material/equipos** desde el celular.
- Ver el estado de sus propios REQs (BORRADOR → ENVIADO → APROBADO → …).
- Buscar insumos del presupuesto y ver **saldo disponible real** antes de
  pedir.
- Funcionar **offline con cola de sincronización** cuando no hay señal (en
  obra es común).

Luego se van sumando apps por rol: Almacenero, Logística, etc. Cada rol
reutiliza ~70% del stack (auth, cliente HTTP, modelos locales), así que los
siguientes son 2–3 semanas vs las 5–7 del primero.

---

## 2. Stack elegido

| Capa      | Elección                   | Por qué                                                                 |
|-----------|----------------------------|-------------------------------------------------------------------------|
| App móvil | **Flutter 3.22+** (Dart 3) | Un codebase para Android + iOS futuro; offline-first maduro (SQLite + workmanager); performance nativa; no depende de JS ni del navegador. |
| Backend   | **Django 6.0 + DRF**       | Ya existe el sistema web — la API reusa modelos, helpers y permisos.    |
| Auth      | **Token Authentication** de DRF | Simple, suficiente para app privada de obra. Sin OAuth.           |
| HTTP      | `http` (Dart) + `shared_preferences` | Lo mínimo imprescindible para el MVP; no abusar de libs grandes.   |
| Idempotencia | `uuid` cliente + tabla `SyncLog` | Sin esto, un reintento tras corte de red genera REQs duplicados. |

Alternativas descartadas:

- **PWA**: se descartó porque offline serio con fotos, cámara, GPS, QR o
  firma no es confiable en Android, y la obra lo va a necesitar.
- **React Native**: ecosistema offline más fragmentado que Flutter;
  dependencias nativas rompen con upgrades.
- **Nativo Kotlin**: duplica el trabajo cuando se quiera iOS.

---

## 3. Arquitectura de sincronización offline (v2)

Patrón **"online con cola offline"**:

1. Cada acción del usuario (crear REQ, editar borrador, registrar turno)
   se persiste primero en **SQLite local** con estado `PENDIENTE` y un
   `uuid` generado en el cliente.
2. Un **worker en segundo plano** (`workmanager` + `http`) revisa la cola
   cada X segundos cuando hay internet. Envía los items uno por uno con
   **reintentos exponenciales** (1s → 5s → 30s → 2min → 10min). Marca
   `SINCRONIZADO` al recibir OK del backend.
3. El backend es **idempotente** vía `client_uuid`: si llega dos veces el
   mismo request (porque la red se cortó justo al confirmar), consulta la
   tabla `apps.api.SyncLog` y devuelve el REQ ya creado en lugar de
   duplicar.
4. La app muestra un indicador tipo **"3 pendientes de enviar"** para que
   el usuario sepa que hay algo encolado.

Resolución de conflictos: por ahora **last-write-wins** por campo si dos
dispositivos editan el mismo REQ (improbable en el MVP: cada jefe de obra
crea los suyos). Si en el futuro hay edición concurrente real, se agregará
un timestamp por campo o un merge dirigido.

---

## 4. Decisiones de dominio relevantes

### 4.1 Separación REQ Obra / REQ Almacén

Hasta ayer el mismo modelo `Requerimiento` servía para Jefe de Obra y
Almacenero. Como la app offline puede crear REQs en paralelo desde roles
distintos sin internet, el **correlativo compartido generaría colisiones**.
Se agregó:

- Campo `Requerimiento.origen` (`OBRA` | `ALMACEN`, default `OBRA`).
- Helper `_siguiente_numero(proyecto, origen)` con prefijo separado:
  - **Jefe de Obra**: `REQ001`, `REQ002`, ... (igual que antes — UI sin
    cambios).
  - **Almacenero**: `REQA001`, `REQA002`, ... (nuevo prefijo "A").
- Migración `0018_requerimiento_origen.py` reclasifica los históricos y
  renumera los del Almacén en orden cronológico arrancando en `A001` por
  proyecto.
- Sidebar del Almacenero renombrado: "Solicitar material" →
  "Requerimientos de Almacén".
- La UI del Jefe de Obra no cambia: `REQ001` sigue siendo `REQ001`.

### 4.2 Clasificación automática del origen desde la API

El endpoint `POST /api/proyectos/<pid>/requerimientos/crear/` decide el
origen según el permiso del usuario autenticado:

- `puede_aprobar_requerimientos` → `origen=OBRA`, estado inicial
  `BORRADOR` o `ENVIADO` según la acción.
- Solo `puede_crear_requerimientos` → `origen=ALMACEN`, estado inicial
  `SOLICITADO` (va a la bandeja del Jefe de Obra).

### 4.3 Reuso de lógica del backend

La API **no reimplementa** la validación de saldo ni el cálculo del
siguiente número. Reusa:

- `apps.requerimientos.views._siguiente_numero(proyecto, origen)`
- `apps.requerimientos.views._siguiente_numero_global()`
- `apps.requerimientos.views._sync_snapshot(detalle)`
- `apps.presupuesto.services.saldo_disponible_insumo(ins)`
- `apps.presupuesto.services.consolidar_por_insumo(pares)`
- `config.permisos.proyectos_visibles(user)` y `tiene(user, perm)`

Si el día de mañana se ajusta una regla de negocio en el backend, la app
móvil hereda el cambio automáticamente.

---

## 5. Endpoints de la API REST

Base: `https://sys360.cloud/api/`

| Método | Ruta                                                       | Qué hace                                                |
|--------|------------------------------------------------------------|---------------------------------------------------------|
| POST   | `/auth/token/`                                             | Login → devuelve `token`, `user_id`, `full_name`, `rol`, `is_superuser`. |
| GET    | `/proyectos/`                                              | Proyectos visibles del usuario autenticado.             |
| GET    | `/proyectos/<pid>/insumos/?q=abraz&page=1`                 | Buscador paginado; cada item incluye `saldo_disponible`. |
| GET    | `/proyectos/<pid>/requerimientos/?mios=1&estado=BORRADOR&origen=OBRA` | Lista filtrable; `mios=1` solo los creados por el usuario. |
| POST   | `/proyectos/<pid>/requerimientos/crear/`                   | Crea un REQ (con `client_uuid` para idempotencia).      |
| GET    | `/requerimientos/<pk>/`                                    | Detalle de un REQ con sus detalles.                     |

Auth header: `Authorization: Token <token>`.

**Idempotencia** del POST: si el body incluye `client_uuid` y ese UUID ya
existe en la tabla `SyncLog`, el endpoint devuelve el REQ previo con `200
OK` en vez de crear uno nuevo.

### 5.1 Ejemplo de body para crear REQ

```json
{
  "client_uuid": "550e8400-e29b-41d4-a716-446655440000",
  "accion":      "enviar",
  "fecha":       "2026-11-21",
  "obra":        "CONSORCIO VIAL URBANO COCHECHAN",
  "solicitante": "Harris Steifer Tinoco Rodas",
  "cargo_solicitante": "Jefe de obra",
  "sector_obra": "",
  "observaciones": "Pedido urgente para el frente norte",
  "detalles": [
    {
      "insumo_id": 5304,
      "descripcion": "ABRAZADERA DE FIERRO GALVANIZADO 1\"",
      "unidad": "und",
      "cantidad": "5",
      "cantidad_requerida": "5",
      "observacion": ""
    }
  ]
}
```

### 5.2 Códigos de respuesta

- `200 OK` — idempotente: el `client_uuid` ya existía, devuelve el REQ
  previo.
- `201 Created` — REQ nuevo creado.
- `400 Bad Request` — validación falla (ej: saldo superado).
  Body: `{"saldo": ["\"X\": pediste 50 pero solo quedan 5 und..."]}`.
- `401 Unauthorized` — token inválido o faltante.
- `403 Forbidden` — sin acceso al proyecto o sin permiso.

---

## 6. Estado del backend

Instalado y funcionando en producción (VPS `sys360.cloud`):

- ✅ `djangorestframework>=3.15` instalado en el venv de uvicorn
  (`/var/www/ssgestion/venv`).
- ✅ Migraciones aplicadas:
  - `api.0001_initial` — tabla `SyncLog` para idempotencia.
  - `authtoken.0001` a `0004` — tabla de tokens de DRF.
  - `requerimientos.0018` — campo `origen` + renumeración retroactiva.
  - `logistica.0012`, `presupuesto.0018` — AutoField → BigAutoField
    pendientes.
  - `maquinaria.0017` — horómetro numérico + `numero_turno`.
- ✅ Middleware: `/api/` bypass del `LoginRequiredMiddleware`.
- ✅ Config DRF en `settings.REST_FRAMEWORK` con TokenAuthentication por
  defecto.

**Nota**: `requirements.txt` del repo tiene flag `git skip-worktree`; la
instalación de `djangorestframework` en el VPS se hizo manualmente con
`pip install` dentro del venv. Si se despliega a un servidor nuevo, hay
que repetir ese `pip install` manualmente.

---

## 7. Estado del scaffold Flutter

Estructura en `mobile/` (commit `c190033`):

```
mobile/
├── pubspec.yaml                      # http, shared_preferences, intl, uuid
├── .gitignore                        # ignora build/, .dart_tool/, keystore, etc.
├── README.md                         # setup rápido para desarrolladores
└── lib/
    ├── main.dart                     # entry point + tema Material 3
    ├── config/
    │   └── api_config.dart           # URL base (sys360.cloud/api)
    ├── models/
    │   └── models.dart               # Proyecto, Insumo, DetalleReq, Requerimiento
    ├── services/
    │   ├── api_service.dart          # cliente HTTP (login, listar, crear, buscar)
    │   └── storage.dart              # token + proyecto activo (SharedPreferences)
    └── screens/
        ├── login_screen.dart         # pide usuario/pass → guarda token
        ├── proyecto_selector_screen.dart  # lista proyectos visibles
        ├── requerimiento_list_screen.dart # Mis REQs con badge de estado
        └── requerimiento_form_screen.dart # Nuevo REQ + buscador inline
```

**Lo que falta** para que compile un APK: generar la capa Android. Flutter
necesita las carpetas `android/`, `ios/`, `test/` autogeneradas por el CLI
(no las puedo versionar a mano sin que luego falle el build de Gradle).

---

## 8. Pasos para generar el APK (una sola vez)

Pre-requisitos: **Windows** con Flutter SDK + Android Studio instalados.

### 8.1 Instalar Flutter y Android Studio

1. Descargar Flutter SDK 3.22+: https://docs.flutter.dev/get-started/install/windows
2. Descomprimir en `C:\src\flutter` (evitar rutas con espacios).
3. Agregar `C:\src\flutter\bin` al PATH del sistema (Panel de Control →
   Variables de entorno).
4. Instalar Android Studio: https://developer.android.com/studio (trae el
   SDK de Android).
5. Abrir Android Studio → SDK Manager → aceptar las licencias.
6. Verificar en una terminal nueva:
   ```bash
   flutter doctor
   ```
   Resolver lo que aparezca en rojo (licencias Android, emulador, etc.).

### 8.2 Generar las carpetas de plataforma

```bash
cd c:\xampp\htdocs\structure\mobile
flutter create . --project-name ssgestion_app --org pe.ssgestion --platforms android
flutter pub get
```

`flutter create .` sobre un directorio con `pubspec.yaml` y `lib/` ya
versionados **no los sobrescribe**: solo agrega lo que falta
(`android/`, `test/`, archivos de build).

### 8.3 Probar en un emulador o teléfono

Con un emulador abierto o un teléfono Android conectado por USB (modo
desarrollador + depuración USB activados):

```bash
flutter run
```

Login con `Harris` + tu contraseña → ves el proyecto "CONSORCIO VIAL
URBANO COCHECHAN" → entras a "Mis Requerimientos" → **+** → agregas
insumos y envías.

### 8.4 Generar el APK de release

```bash
cd c:\xampp\htdocs\structure\mobile
flutter build apk --release
```

El archivo final queda en:
```
c:\xampp\htdocs\structure\mobile\build\app\outputs\flutter-apk\app-release.apk
```

Se instala en un teléfono Android transfiriéndolo por USB, WhatsApp,
Google Drive, o publicándolo en Play Store Internal Testing para
distribución al equipo.

### 8.5 Configurar URL del backend según entorno

- **Producción** (default): `https://sys360.cloud/api` — ya configurado.
- **Local** (Django runserver en la misma PC + emulador Android):
  editar `lib/config/api_config.dart` y cambiar a
  `http://10.0.2.2:8000/api` (la IP que el emulador Android usa para
  alcanzar `localhost` del host).

---

## 9. Pendientes (v2)

Priorizados:

1. **Cola offline con SQLite + workmanager**.
   - Modelo local `PendingRequest(uuid, endpoint, payload, retry_count, next_attempt_at, status)`.
   - Worker Android que corra cada ~2 min cuando hay internet y reintente
     con backoff exponencial.
   - UI: indicador tipo "3 pendientes" en el AppBar.
2. **Detalle de un REQ** (hoy la lista solo muestra el resumen; al tocar
   un item no hay pantalla).
3. **Editar borrador** (hoy solo se puede crear, no modificar).
4. **Notificaciones push** cuando el REQ cambia de estado (requiere
   Firebase Cloud Messaging + registro del `device_token` en el backend).
5. **Pantalla de cola de pendientes** con botón "Reintentar ahora".
6. **Modo oscuro** (actualmente solo claro).
7. **Firma digital / foto de evidencia** por ítem (cámara + galería).
8. **Perfiles por rol**: hoy la app sirve al Jefe de Obra; agregar
   pantallas para Almacenero (crear `REQA001`), Logística (aprobar,
   cotizar), etc.

---

## 10. Checklist para agregar un segundo rol (patrón)

Cuando se quiera soportar, por ejemplo, el Almacenero:

- [ ] Backend: evaluar si los endpoints actuales ya cubren el flujo o si
      hay que agregar `POST /api/proyectos/<pid>/requerimientos/solicitar/`.
      (Hoy `crear` ya detecta el rol y asigna `origen=ALMACEN`
      automáticamente, así que probablemente no haga falta.)
- [ ] App: una pantalla de "menú" post-login que elija qué flujo mostrar
      según `Storage.getUserRol()`.
- [ ] Reusar `ApiService`, `models`, `storage`, `_BuscadorInsumos`,
      pantallas de lista y formulario. Solo cambia la rotulación.
- [ ] Testear con un usuario que tenga `puede_crear_requerimientos` pero
      no `puede_aprobar_requerimientos` → sus REQs nacen como
      `REQA001`, `REQA002`, ...

---

## 11. Historial de commits relevantes

| Commit    | Qué hace                                                                                                |
|-----------|---------------------------------------------------------------------------------------------------------|
| `1045c74` | Separar REQ Obra/Almacén (campo `origen`, prefijo `REQA`, renumeración).                                |
| `19fe854` | Migraciones pendientes: `AutoField` → `BigAutoField` en OC y Avance Físico.                             |
| `13c90dc` | API REST para la app móvil: endpoints MVP del Jefe de Obra (DRF + Token Auth + idempotencia vía `SyncLog`). |
| `c190033` | Scaffold Flutter del MVP Jefe de Obra (online).                                                         |

---

**Última actualización**: 2026-11-21 · scaffold Flutter listo, pendiente
instalar SDK y correr `flutter create .` para generar la capa Android.
