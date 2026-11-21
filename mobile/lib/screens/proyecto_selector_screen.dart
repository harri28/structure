import 'package:flutter/material.dart';

import '../models/models.dart';
import '../services/api_service.dart';
import '../services/storage.dart';
import 'login_screen.dart';
import 'requerimiento_list_screen.dart';

class ProyectoSelectorScreen extends StatefulWidget {
  const ProyectoSelectorScreen({super.key});
  @override
  State<ProyectoSelectorScreen> createState() => _ProyectoSelectorScreenState();
}

class _ProyectoSelectorScreenState extends State<ProyectoSelectorScreen> {
  late Future<List<Proyecto>> _future;

  @override
  void initState() {
    super.initState();
    _future = ApiService.listarProyectos();
  }

  Future<void> _logout() async {
    await Storage.clear();
    if (!mounted) return;
    Navigator.pushReplacement(context,
        MaterialPageRoute(builder: (_) => const LoginScreen()));
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Seleccionar proyecto'),
        actions: [
          IconButton(icon: const Icon(Icons.logout), onPressed: _logout),
        ],
      ),
      body: FutureBuilder<List<Proyecto>>(
        future: _future,
        builder: (context, snap) {
          if (snap.connectionState != ConnectionState.done) {
            return const Center(child: CircularProgressIndicator());
          }
          if (snap.hasError) {
            return Center(child: Padding(
              padding: const EdgeInsets.all(24),
              child: Text('No se pudo cargar: ${snap.error}'),
            ));
          }
          final proyectos = snap.data ?? [];
          if (proyectos.isEmpty) {
            return const Center(child: Text('No tienes proyectos asignados.'));
          }
          return ListView.separated(
            padding: const EdgeInsets.all(12),
            itemCount: proyectos.length,
            separatorBuilder: (_, __) => const SizedBox(height: 8),
            itemBuilder: (_, i) {
              final p = proyectos[i];
              return Card(
                child: ListTile(
                  leading: const CircleAvatar(child: Icon(Icons.construction)),
                  title: Text(p.nombre, style: const TextStyle(fontWeight: FontWeight.w600)),
                  subtitle: Text('${p.codigo} · ${p.estado}'),
                  trailing: const Icon(Icons.chevron_right),
                  onTap: () async {
                    await Storage.setProyecto(p.id, p.nombre);
                    if (!mounted) return;
                    Navigator.push(context, MaterialPageRoute(
                      builder: (_) => RequerimientoListScreen(proyecto: p),
                    ));
                  },
                ),
              );
            },
          );
        },
      ),
    );
  }
}
