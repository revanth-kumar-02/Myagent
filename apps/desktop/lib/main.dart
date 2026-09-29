import 'dart:io' show Directory, Platform;
import 'package:flutter/foundation.dart' show kIsWeb;
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:window_manager/window_manager.dart';

import 'app.dart';
import 'services/project/project_service.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();

  // ── Desktop Window Setup ──────────────────────────────────────────────────
  if (!kIsWeb && (Platform.isWindows || Platform.isLinux || Platform.isMacOS)) {
    try {
      await windowManager.ensureInitialized();
      await windowManager.setMinimumSize(const Size(960, 640));
      await windowManager.setTitle('Kora — Autonomous AI Agent');
      await windowManager.show();
      await windowManager.focus();
    } catch (_) {
      // Ignore if headless or testing
    }

    // Default workspace initialization if not set
    try {
      final prefs = await SharedPreferences.getInstance();
      if (!prefs.containsKey('kora_projects_workspace_path')) {
        final defDir = Directory(ProjectService.defaultWorkspaceSuggestion);
        if (defDir.existsSync()) {
          await prefs.setString('kora_projects_workspace_path', defDir.path);
        }
      }
    } catch (_) {}
  }

  runApp(
    const ProviderScope(
      child: KoraApp(),
    ),
  );
}
