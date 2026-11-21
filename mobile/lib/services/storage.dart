import 'package:shared_preferences/shared_preferences.dart';

/// Persistencia local simple: token de auth, proyecto activo y datos del user.
/// Guarda en SharedPreferences (equivalente a localStorage en web).
class Storage {
  static const _kToken       = 'token';
  static const _kUserName    = 'user_name';
  static const _kUserFull    = 'user_full';
  static const _kUserRol     = 'user_rol';
  static const _kProyectoId  = 'proyecto_id';
  static const _kProyectoNom = 'proyecto_nombre';

  static Future<SharedPreferences> get _prefs async =>
      await SharedPreferences.getInstance();

  static Future<void> saveSession({
    required String token,
    required String username,
    required String fullName,
    required String rol,
  }) async {
    final p = await _prefs;
    await p.setString(_kToken, token);
    await p.setString(_kUserName, username);
    await p.setString(_kUserFull, fullName);
    await p.setString(_kUserRol, rol);
  }

  static Future<String?>   getToken()    async => (await _prefs).getString(_kToken);
  static Future<String?>   getUserFull() async => (await _prefs).getString(_kUserFull);
  static Future<String?>   getUserRol()  async => (await _prefs).getString(_kUserRol);

  static Future<void> setProyecto(int id, String nombre) async {
    final p = await _prefs;
    await p.setInt(_kProyectoId, id);
    await p.setString(_kProyectoNom, nombre);
  }

  static Future<int?>    getProyectoId()     async => (await _prefs).getInt(_kProyectoId);
  static Future<String?> getProyectoNombre() async => (await _prefs).getString(_kProyectoNom);

  static Future<void> clear() async {
    final p = await _prefs;
    await p.clear();
  }
}
