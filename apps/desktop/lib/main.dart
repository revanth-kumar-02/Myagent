import 'dart:io';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:window_manager/window_manager.dart';

import 'app.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();

  // ── Desktop Window Setup ──────────────────────────────────────────────────
  if (Platform.isWindows || Platform.isLinux || Platform.isMacOS) {
    try {
      await windowManager.ensureInitialized();
      await windowManager.setMinimumSize(const Size(960, 640));
      await windowManager.setTitle('Kora — Autonomous AI Agent');
      await windowManager.show();
      await windowManager.focus();
    } catch (_) {
      // Ignore if headless or testing
    }
  }

  runApp(
    const ProviderScope(
      child: KoraApp(),
    ),
  );
}
