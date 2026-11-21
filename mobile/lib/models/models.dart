/// Modelos de dominio (plain Dart, sin ORM). Mapean 1:1 el JSON de la API.

class Proyecto {
  final int    id;
  final String codigo;
  final String nombre;
  final String sector;
  final String estado;

  Proyecto({
    required this.id, required this.codigo, required this.nombre,
    required this.sector, required this.estado,
  });

  factory Proyecto.fromJson(Map<String, dynamic> j) => Proyecto(
        id:     j['id'],
        codigo: j['codigo'] ?? '',
        nombre: j['nombre'] ?? '',
        sector: j['sector'] ?? '',
        estado: j['estado'] ?? '',
      );
}

class Insumo {
  final int    id;
  final String codigo;
  final String descripcion;
  final String unidad;
  final String cantidadTotal;
  final String saldoDisponible;

  Insumo({
    required this.id, required this.codigo, required this.descripcion,
    required this.unidad, required this.cantidadTotal, required this.saldoDisponible,
  });

  factory Insumo.fromJson(Map<String, dynamic> j) => Insumo(
        id:              j['id'],
        codigo:          j['codigo'] ?? '',
        descripcion:     j['descripcion'] ?? '',
        unidad:          j['unidad'] ?? '',
        cantidadTotal:   j['cantidad_total']?.toString() ?? '0',
        saldoDisponible: j['saldo_disponible']?.toString() ?? '0',
      );
}

class DetalleReq {
  final int?   id;
  final int?   insumoId;
  final String descripcion;
  final String unidad;
  final String cantidadRequerida;
  final String? cantidadAprobada;
  final String observacion;

  DetalleReq({
    this.id, this.insumoId, required this.descripcion, required this.unidad,
    required this.cantidadRequerida, this.cantidadAprobada, this.observacion = '',
  });

  factory DetalleReq.fromJson(Map<String, dynamic> j) => DetalleReq(
        id:                j['id'],
        insumoId:          j['insumo_id'],
        descripcion:       j['insumo_descripcion'] ?? j['descripcion'] ?? '',
        unidad:            j['unidad'] ?? '',
        cantidadRequerida: j['cantidad_requerida']?.toString() ?? '0',
        cantidadAprobada:  j['cantidad_aprobada']?.toString(),
        observacion:       j['observacion'] ?? '',
      );

  Map<String, dynamic> toPayload() => {
        'insumo_id':          insumoId,
        'descripcion':        descripcion,
        'unidad':             unidad,
        'cantidad':           cantidadRequerida,
        'cantidad_requerida': cantidadRequerida,
        'observacion':        observacion,
      };
}

class Requerimiento {
  final int    id;
  final String numero;
  final String origen;
  final String estado;
  final String fecha;
  final String solicitante;
  final String observaciones;
  final List<DetalleReq> detalles;

  Requerimiento({
    required this.id, required this.numero, required this.origen,
    required this.estado, required this.fecha, required this.solicitante,
    required this.observaciones, required this.detalles,
  });

  factory Requerimiento.fromJson(Map<String, dynamic> j) => Requerimiento(
        id:            j['id'],
        numero:        j['numero'] ?? '',
        origen:        j['origen'] ?? 'OBRA',
        estado:        j['estado'] ?? '',
        fecha:         j['fecha']  ?? '',
        solicitante:   j['solicitante'] ?? '',
        observaciones: j['observaciones'] ?? '',
        detalles: ((j['detalles'] as List?) ?? [])
            .map((d) => DetalleReq.fromJson(d as Map<String, dynamic>))
            .toList(),
      );

  String get numeroCompleto => 'REQ$numero';
}
