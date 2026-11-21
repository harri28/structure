/// Configuración de la API REST.
///
/// Para el emulador Android apuntando a localhost se usaría `10.0.2.2:8000`.
/// Por defecto apuntamos al VPS de producción para que el jefe de obra pueda
/// probar la app contra datos reales desde el día uno.
class ApiConfig {
  static const String baseUrl = 'https://sys360.cloud/api';
}
