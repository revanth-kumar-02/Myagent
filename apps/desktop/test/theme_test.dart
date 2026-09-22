import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:kora_desktop/app.dart';
import 'package:kora_desktop/core/theme/app_theme.dart';
import 'package:kora_desktop/state/settings_state.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  setUp(() {
    SharedPreferences.setMockInitialValues({});
  });

  group('Kora Theme System Tests', () {
    test('Light theme tokens provide canonical Kora light palette', () {
      final lightTheme = AppTheme.light();
      expect(lightTheme.brightness, Brightness.light);
      expect(lightTheme.scaffoldBackgroundColor, const Color(0xFFFBF9F5)); // Warm Ivory
      expect(lightTheme.colorScheme.primary, const Color(0xFF4A6B5B)); // Sage Green

      final colors = lightTheme.extension<KoraColors>();
      expect(colors, isNotNull);
      expect(colors!.bg, const Color(0xFFFBF9F5));
      expect(colors.textPrimary, const Color(0xFF222523));
      expect(colors.accent, const Color(0xFFC86D51));
    });

    test('Dark theme tokens provide canonical Kora dark palette', () {
      final darkTheme = AppTheme.dark();
      expect(darkTheme.brightness, Brightness.dark);
      expect(darkTheme.scaffoldBackgroundColor, const Color(0xFF171A18)); // Deep Warm Charcoal
      expect(darkTheme.colorScheme.surface, const Color(0xFF212522)); // Dark Olive/Sage Surface

      final colors = darkTheme.extension<KoraColors>();
      expect(colors, isNotNull);
      expect(colors!.bg, const Color(0xFF171A18));
      expect(colors.textPrimary, const Color(0xFFF3F1EC)); // Warm Ivory Text
      expect(colors.accent, const Color(0xFFD98268)); // Muted Terracotta Accent
    });

    testWidgets('KoraApp switches theme dynamically between Light, Dark, and System', (tester) async {
      tester.view.physicalSize = const Size(1200, 800);
      tester.view.devicePixelRatio = 1.0;
      addTearDown(tester.view.resetPhysicalSize);

      await tester.pumpWidget(
        const ProviderScope(
          child: KoraApp(),
        ),
      );
      await tester.pump();

      final materialAppFinder = find.byType(MaterialApp);
      expect(materialAppFinder, findsOneWidget);
      MaterialApp app = tester.widget<MaterialApp>(materialAppFinder);
      expect(app.themeMode, ThemeMode.light);

      final element = tester.element(materialAppFinder);
      final container = ProviderScope.containerOf(element);

      await container.read(settingsProvider.notifier).setThemeMode(ThemeMode.dark);
      await tester.pump();

      app = tester.widget<MaterialApp>(materialAppFinder);
      expect(app.themeMode, ThemeMode.dark);

      await container.read(settingsProvider.notifier).setThemeMode(ThemeMode.system);
      await tester.pump();

      app = tester.widget<MaterialApp>(materialAppFinder);
      expect(app.themeMode, ThemeMode.system);
    });
  });
}
