import 'dart:convert';
import 'package:http/http.dart' as http;

import '../config/api_config.dart';
import '../models/models.dart';
import 'storage.dart';

/// Cliente HTTP delgado sobre la API REST del backend Django.
///
/// Todos los métodos devuelven el modelo tipado o lanzan [ApiException] con
/// el mensaje a mostrar al usuario.
class ApiService {
  static Uri _uri(String path) => Uri.parse('${ApiConfig.baseUrl}$path');

  static Future<Map<String, String>> _authHeaders() async {
    final token = await Storage.getToken();
    return {
      'Content-Type': 'application/json',
      if (token != null) 'Authorization': 'Token $token',
    };
  }

  /// POST /auth/token/ — guarda la sesión en Storage y devuelve el nombre.
  static Future<Map<String, dynamic>> login(String username, String password) async {
    final r = await http.post(
      _uri('/auth/token/'),
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode({'username': username, 'password': password}),
    );
    if (r.statusCode == 401) {
      throw ApiException('Usuario o contraseña incorrectos.');
    }
    if (r.statusCode != 200) {
      throw ApiException('Error inesperado (${r.statusCode}).');
    }
    final data = jsonDecode(r.body) as Map<String, dynamic>;
    await Storage.saveSession(
      token:    data['token'],
      username: data['username'],
      fullName: data['full_name'] ?? '',
      rol:      data['rol'] ?? '',
    );
    return data;
  }

  /// GET /proyectos/
  static Future<List<Proyecto>> listarProyectos() async {
    final r = await http.get(_uri('/proyectos/'), headers: await _authHeaders());
    _checkOk(r);
    final list = jsonDecode(r.body) as List;
    return list.map((j) => Proyecto.fromJson(j)).toList();
  }

  /// GET /proyectos/{pid}/insumos/?q=...
  static Future<List<Insumo>> buscarInsumos(int proyectoId, String query) async {
    final url = _uri('/proyectos/$proyectoId/insumos/?q=${Uri.encodeQueryComponent(query)}');
    final r = await http.get(url, headers: await _authHeaders());
    _checkOk(r);
    final data = jsonDecode(r.body) as Map<String, dynamic>;
    final list = (data['results'] as List?) ?? [];
    return list.map((j) => Insumo.fromJson(j)).toList();
  }

  /// GET /proyectos/{pid}/requerimientos/?mios=1
  static Future<List<Requerimiento>> listarRequerimientos(
      int proyectoId, {bool mios = true}) async {
    final url = _uri('/proyectos/$proyectoId/requerimientos/?mios=${mios ? 1 : 0}');
    final r = await http.get(url, headers: await _authHeaders());
    _checkOk(r);
    final list = jsonDecode(r.body) as List;
    return list.map((j) => Requerimiento.fromJson(j)).toList();
  }

  /// POST /proyectos/{pid}/requerimientos/crear/
  static Future<Requerimiento> crearRequerimiento({
    required int    proyectoId,
    required String clientUuid,
    required String accion, // 'borrador' | 'enviar'
    required String fecha,  // 'YYYY-MM-DD'
    required String obra,
    required String solicitante,
    required String cargoSolicitante,
    required String sectorObra,
    required String observaciones,
    required List<DetalleReq> detalles,
  }) async {
    final url = _uri('/proyectos/$proyectoId/requerimientos/crear/');
    final r = await http.post(
      url,
      headers: await _authHeaders(),
      body: jsonEncode({
        'client_uuid':       clientUuid,
        'accion':            accion,
        'fecha':             fecha,
        'obra':              obra,
        'solicitante':       solicitante,
        'cargo_solicitante': cargoSolicitante,
        'sector_obra':       sectorObra,
        'observaciones':     observaciones,
        'detalles':          detalles.map((d) => d.toPayload()).toList(),
      }),
    );
    if (r.statusCode != 200 && r.statusCode != 201) {
      throw ApiException(_parseError(r));
    }
    return Requerimiento.fromJson(jsonDecode(r.body));
  }

  static void _checkOk(http.Response r) {
    if (r.statusCode >= 200 && r.statusCode < 300) return;
    throw ApiException(_parseError(r));
  }

  static String _parseError(http.Response r) {
    try {
      final body = jsonDecode(r.body);
      if (body is Map) {
        if (body['detail'] != null) return body['detail'].toString();
        if (body['saldo'] is List)  return (body['saldo'] as List).join('\n');
        return body.entries.map((e) => '${e.key}: ${e.value}').join('\n');
      }
    } catch (_) {}
    return 'Error ${r.statusCode}';
  }
}

class ApiException implements Exception {
  final String message;
  ApiException(this.message);
  @override
  String toString() => message;
}
