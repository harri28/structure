# S&S Gestión — App móvil (Jefe de Obra MVP)

App Flutter que se conecta a la API REST del backend Django para que el Jefe
de Obra pueda crear requerimientos desde el celular.

## Estado actual (v0.1)

- **Online only.** La app necesita internet para funcionar. La cola offline
  llegará en v2.
- **Pantallas**: Login → Selector de proyecto → Mis requerimientos → Nuevo
  requerimiento (con buscador de insumos y saldo en vivo).
- **Idempotencia**: cada POST de creación incluye un `client_uuid` para que
  si la red se corta al confirmar, un reintento no genere REQs duplicados.

## Pre-requisitos (una sola vez)

1. **Flutter SDK 3.22+** — https://docs.flutter.dev/get-started/install/windows
   - Descomprimir en `C:\src\flutter`
   - Agregar `C:\src\flutter\bin` al PATH
2. **Android Studio** — https://developer.android.com/studio
   - Instalar Android SDK y crear un emulador (o conectar un teléfono por
     USB con depuración activada).
3. Verificar con:
   ```bash
   flutter doctor
   ```
   Resolver lo que esté en rojo antes de seguir.

## Setup inicial del proyecto

Desde la raíz del repo:

```bash
cd mobile

# 1) Genera la capa Android (y iOS si se quiere) dejando intactos los
#    archivos que ya versionamos (lib/, pubspec.yaml).
flutter create . --project-name ssgestion_app --org pe.ssgestion --platforms android

# 2) Descargar dependencias Dart
flutter pub get

# 3) Correr en el emulador o teléfono conectado
flutter run
```

## Build del APK de release

```bash
cd mobile
flutter build apk --release
# El APK queda en: build/app/outputs/flutter-apk/app-release.apk
```

Transferirlo al teléfono por USB, WhatsApp, Drive, o publicar en Play Store
Interno.

## Configuración

La URL del backend está en `lib/config/api_config.dart`. Por defecto apunta a
`https://sys360.cloud/api`. Para pruebas locales contra el runserver de
Django en la misma PC, cambiar a `http://10.0.2.2:8000/api` (la IP que el
emulador Android usa para alcanzar `localhost` del host).

## Estructura

```
lib/
├── main.dart                       # entry point, tema, ruta inicial
├── config/
│   └── api_config.dart             # URL base de la API
├── models/
│   └── models.dart                 # Proyecto, Insumo, Requerimiento, Detalle
├── services/
│   ├── api_service.dart            # cliente HTTP (login, listar, crear)
│   └── storage.dart                # token + proyecto activo (SharedPrefs)
└── screens/
    ├── login_screen.dart
    ├── proyecto_selector_screen.dart
    ├── requerimiento_list_screen.dart
    └── requerimiento_form_screen.dart  # incluye buscador de insumos
```

## Pendientes (v2+)

- Cola offline: guardar POSTs en SQLite y reenviar al reconectar.
- Pantalla de detalle de un REQ (hoy la lista solo muestra el resumen).
- Pantalla de cola de pendientes de sincronizar (indicador global).
- Editar borradores.
- Notificaciones push cuando el REQ cambia de estado.
