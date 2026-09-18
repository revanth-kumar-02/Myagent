import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:window_manager/window_manager.dart';

import 'app.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();

  // ── Window setup (desktop) ─────────────────────────────────────────────────
  await windowManager.ensureInitialized();
  await windowManager.setMinimumSize(const Size(900, 600));
  await windowManager.setTitle('Kora');
  await windowManager.setTitleBarStyle(TitleBarStyle.hidden);
  await windowManager.show();
  await windowManager.focus();

  runApp(
    const ProviderScope(
      child: KoraApp(),
    ),
  );
}
