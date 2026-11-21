import 'package:flutter/material.dart';

import '../models/models.dart';
import '../services/api_service.dart';
import 'requerimiento_form_screen.dart';

class RequerimientoListScreen extends StatefulWidget {
  final Proyecto proyecto;
  const RequerimientoListScreen({super.key, required this.proyecto});
  @override
  State<RequerimientoListScreen> createState() => _RequerimientoListScreenState();
}

class _RequerimientoListScreenState extends State<RequerimientoListScreen> {
  late Future<List<Requerimiento>> _future;

  @override
  void initState() {
    super.initState();
    _future = ApiService.listarRequerimientos(widget.proyecto.id);
  }

  void _refresh() {
    setState(() {
      _future = ApiService.listarRequerimientos(widget.proyecto.id);
    });
  }

  Color _colorEstado(String estado) {
    switch (estado) {
      case 'BORRADOR':    return Colors.grey;
      case 'ENVIADO':     return Colors.blue;
      case 'EN_REVISION': return Colors.orange;
      case 'APROBADO':    return Colors.green;
      case 'COTIZADO':    return Colors.teal;
      case 'ATENDIDO':    return Colors.purple;
      case 'PARCIAL':     return Colors.amber.shade700;
      case 'ANULADO':     return Colors.red;
      default:            return Colors.grey;
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text('Mis Requerimientos', style: TextStyle(fontSize: 16)),
            Text(widget.proyecto.nombre,
                style: const TextStyle(fontSize: 11, color: Colors.white70)),
          ],
        ),
      ),
      body: RefreshIndicator(
        onRefresh: () async { _refresh(); await _future; },
        child: FutureBuilder<List<Requerimiento>>(
          future: _future,
          builder: (context, snap) {
            if (snap.connectionState != ConnectionState.done) {
              return const Center(child: CircularProgressIndicator());
            }
            if (snap.hasError) {
              return ListView(children: [Padding(
                padding: const EdgeInsets.all(24),
                child: Text('Error: ${snap.error}'),
              )]);
            }
            final reqs = snap.data ?? [];
            if (reqs.isEmpty) {
              return ListView(children: const [Padding(
                padding: EdgeInsets.all(32),
                child: Center(child: Text(
                  'Aún no has creado requerimientos.\n\nPulsa + para crear el primero.',
                  textAlign: TextAlign.center,
                )),
              )]);
            }
            return ListView.separated(
              padding: const EdgeInsets.all(12),
              itemCount: reqs.length,
              separatorBuilder: (_, __) => const SizedBox(height: 8),
              itemBuilder: (_, i) {
                final r = reqs[i];
                return Card(
                  child: ListTile(
                    title: Row(children: [
                      Text(r.numeroCompleto,
                          style: const TextStyle(fontWeight: FontWeight.bold)),
                      const SizedBox(width: 8),
                      Container(
                        padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
                        decoration: BoxDecoration(
                          color: _colorEstado(r.estado).withValues(alpha: 0.15),
                          borderRadius: BorderRadius.circular(10),
                        ),
                        child: Text(r.estado,
                            style: TextStyle(
                                fontSize: 10, color: _colorEstado(r.estado),
                                fontWeight: FontWeight.w600)),
                      ),
                    ]),
                    subtitle: Text('${r.fecha} · ${r.detalles.length} ítems'),
                    trailing: const Icon(Icons.chevron_right),
                    onTap: () {
                      // Detalle: aún no implementado. Para MVP basta el listado.
                    },
                  ),
                );
              },
            );
          },
        ),
      ),
      floatingActionButton: FloatingActionButton.extended(
        onPressed: () async {
          final creado = await Navigator.push<bool>(context, MaterialPageRoute(
            builder: (_) => RequerimientoFormScreen(proyecto: widget.proyecto),
          ));
          if (creado == true) _refresh();
        },
        icon: const Icon(Icons.add),
        label: const Text('Nuevo'),
      ),
    );
  }
}
