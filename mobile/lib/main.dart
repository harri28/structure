import 'package:flutter/material.dart';

import 'screens/login_screen.dart';

void main() {
  runApp(const SsGestionApp());
}

class SsGestionApp extends StatelessWidget {
  const SsGestionApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'S&S Gestión',
      debugShowCheckedModeBanner: false,
      theme: ThemeData(
        useMaterial3: true,
        colorScheme: ColorScheme.fromSeed(seedColor: const Color(0xFF2563eb)),
        appBarTheme: const AppBarTheme(
          backgroundColor: Color(0xFF2563eb),
          foregroundColor: Colors.white,
          elevation: 0,
        ),
        filledButtonTheme: FilledButtonThemeData(
          style: FilledButton.styleFrom(
            backgroundColor: const Color(0xFF2563eb),
            foregroundColor: Colors.white,
          ),
        ),
      ),
      home: const LoginScreen(),
    );
  }
}
