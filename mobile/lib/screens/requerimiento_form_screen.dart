import 'package:flutter/material.dart';
import 'package:intl/intl.dart';
import 'package:uuid/uuid.dart';

import '../models/models.dart';
import '../services/api_service.dart';
import '../services/storage.dart';

/// Nuevo Requerimiento: cabecera + lista de ítems. Cada ítem busca el insumo
/// contra la API y valida el saldo disponible en el momento de agregar.
class RequerimientoFormScreen extends StatefulWidget {
  final Proyecto proyecto;
  const RequerimientoFormScreen({super.key, required this.proyecto});
  @override
  State<RequerimientoFormScreen> createState() => _RequerimientoFormScreenState();
}

class _RequerimientoFormScreenState extends State<RequerimientoFormScreen> {
  final _observaciones = TextEditingController();
  final List<DetalleReq> _detalles = [];
  bool _guardando = false;
  String? _error;

  Future<void> _agregarItem() async {
    final insumo = await Navigator.push<Insumo>(context, MaterialPageRoute(
      builder: (_) => _BuscadorInsumos(proyectoId: widget.proyecto.id),
    ));
    if (insumo == null) return;

    final cant = await _pedirCantidad(insumo);
    if (cant == null) return;

    setState(() {
      _detalles.add(DetalleReq(
        insumoId:          insumo.id,
        descripcion:       insumo.descripcion,
        unidad:            insumo.unidad,
        cantidadRequerida: cant,
      ));
    });
  }

  Future<String?> _pedirCantidad(Insumo insumo) async {
    final ctl = TextEditingController();
    return showDialog<String>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: Text(insumo.descripcion, style: const TextStyle(fontSize: 14)),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text('Saldo: ${insumo.saldoDisponible} ${insumo.unidad}',
                style: const TextStyle(fontSize: 12, color: Colors.grey)),
            const SizedBox(height: 12),
            TextField(
              controller: ctl,
              autofocus: true,
              keyboardType: const TextInputType.numberWithOptions(decimal: true),
              decoration: InputDecoration(
                labelText: 'Cantidad', suffixText: insumo.unidad,
                border: const OutlineInputBorder(),
              ),
            ),
          ],
        ),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx), child: const Text('Cancelar')),
          FilledButton(
            onPressed: () {
              final v = ctl.text.trim();
              if (v.isEmpty || double.tryParse(v) == null) return;
              Navigator.pop(ctx, v);
            },
            child: const Text('Agregar'),
          ),
        ],
      ),
    );
  }

  Future<void> _enviar({required bool enviar}) async {
    if (_detalles.isEmpty) {
      setState(() => _error = 'Agrega al menos un ítem.');
      return;
    }
    setState(() { _guardando = true; _error = null; });
    try {
      final fullName = await Storage.getUserFull() ?? '';
      final rol      = await Storage.getUserRol() ?? '';
      await ApiService.crearRequerimiento(
        proyectoId:       widget.proyecto.id,
        clientUuid:       const Uuid().v4(),
        accion:           enviar ? 'enviar' : 'borrador',
        fecha:            DateFormat('yyyy-MM-dd').format(DateTime.now()),
        obra:             widget.proyecto.nombre,
        solicitante:      fullName,
        cargoSolicitante: rol,
        sectorObra:       widget.proyecto.sector,
        observaciones:    _observaciones.text,
        detalles:         _detalles,
      );
      if (!mounted) return;
      Navigator.pop(context, true);
    } catch (e) {
      setState(() => _error = e.toString());
    } finally {
      if (mounted) setState(() => _guardando = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Nuevo Requerimiento')),
      body: ListView(
        padding: const EdgeInsets.all(12),
        children: [
          Card(
            child: Padding(
              padding: const EdgeInsets.all(12),
              child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                Text(widget.proyecto.nombre,
                    style: const TextStyle(fontWeight: FontWeight.w600)),
                Text(widget.proyecto.codigo,
                    style: const TextStyle(fontSize: 11, color: Colors.grey)),
                const SizedBox(height: 12),
                TextField(
                  controller: _observaciones,
                  maxLines: 2,
                  decoration: const InputDecoration(
                    labelText: 'Observaciones (opcional)',
                    border: OutlineInputBorder(),
                  ),
                ),
              ]),
            ),
          ),
          const SizedBox(height: 12),
          Row(children: [
            const Expanded(
              child: Text('Ítems',
                  style: TextStyle(fontWeight: FontWeight.bold, fontSize: 16)),
            ),
            TextButton.icon(
              onPressed: _guardando ? null : _agregarItem,
              icon: const Icon(Icons.add),
              label: const Text('Agregar insumo'),
            ),
          ]),
          if (_detalles.isEmpty)
            const Padding(
              padding: EdgeInsets.all(24),
              child: Center(child: Text('Sin ítems aún.')),
            )
          else
            ..._detalles.asMap().entries.map((e) => Card(
              child: ListTile(
                title: Text(e.value.descripcion, style: const TextStyle(fontSize: 13)),
                subtitle: Text('${e.value.cantidadRequerida} ${e.value.unidad}'),
                trailing: IconButton(
                  icon: const Icon(Icons.delete_outline, color: Colors.red),
                  onPressed: _guardando ? null : () {
                    setState(() => _detalles.removeAt(e.key));
                  },
                ),
              ),
            )),
          if (_error != null) ...[
            const SizedBox(height: 12),
            Container(
              padding: const EdgeInsets.all(12),
              decoration: BoxDecoration(
                color: Colors.red.shade50,
                border: Border.all(color: Colors.red.shade200),
                borderRadius: BorderRadius.circular(6),
              ),
              child: Text(_error!, style: const TextStyle(color: Colors.red)),
            ),
          ],
          const SizedBox(height: 20),
          Row(children: [
            Expanded(
              child: OutlinedButton(
                onPressed: _guardando ? null : () => _enviar(enviar: false),
                child: const Text('Guardar borrador'),
              ),
            ),
            const SizedBox(width: 12),
            Expanded(
              child: FilledButton(
                onPressed: _guardando ? null : () => _enviar(enviar: true),
                child: _guardando
                    ? const SizedBox(
                        height: 16, width: 16,
                        child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white),
                      )
                    : const Text('Enviar a Logística'),
              ),
            ),
          ]),
        ],
      ),
    );
  }
}

/// Buscador de insumos en vivo contra la API.
class _BuscadorInsumos extends StatefulWidget {
  final int proyectoId;
  const _BuscadorInsumos({required this.proyectoId});
  @override
  State<_BuscadorInsumos> createState() => _BuscadorInsumosState();
}

class _BuscadorInsumosState extends State<_BuscadorInsumos> {
  final _query = TextEditingController();
  List<Insumo> _resultados = [];
  bool _buscando = false;

  Future<void> _buscar(String q) async {
    setState(() => _buscando = true);
    try {
      _resultados = await ApiService.buscarInsumos(widget.proyectoId, q);
    } catch (e) {
      _resultados = [];
    } finally {
      if (mounted) setState(() => _buscando = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: TextField(
          controller: _query,
          autofocus: true,
          decoration: const InputDecoration(
            hintText: 'Buscar insumo...',
            hintStyle: TextStyle(color: Colors.white54),
            border: InputBorder.none,
          ),
          style: const TextStyle(color: Colors.white),
          onChanged: _buscar,
        ),
      ),
      body: _buscando
          ? const Center(child: CircularProgressIndicator())
          : _resultados.isEmpty
              ? const Center(child: Text('Escribe para buscar.'))
              : ListView.separated(
                  itemCount: _resultados.length,
                  separatorBuilder: (_, __) => const Divider(height: 1),
                  itemBuilder: (_, i) {
                    final x = _resultados[i];
                    return ListTile(
                      dense: true,
                      title: Text(x.descripcion, style: const TextStyle(fontSize: 13)),
                      subtitle: Text(
                          'Saldo: ${x.saldoDisponible} ${x.unidad} · Cod. ${x.codigo}',
                          style: const TextStyle(fontSize: 11)),
                      onTap: () => Navigator.pop(context, x),
                    );
                  },
                ),
    );
  }
}
