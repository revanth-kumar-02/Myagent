import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:kora_desktop/core/theme/app_theme.dart';
import 'package:kora_desktop/features/chat/chat_screen.dart';
import 'package:kora_desktop/widgets/slash_command_picker.dart';

void main() {
  group('Slash Command Tool Trigger Tests', () {
    testWidgets('Typing / opens the slash command picker', (WidgetTester tester) async {
      tester.view.physicalSize = const Size(1200, 800);
      tester.view.devicePixelRatio = 1.0;
      addTearDown(tester.view.resetPhysicalSize);

      await tester.pumpWidget(
        ProviderScope(
          child: MaterialApp(
            theme: AppTheme.light(),
            home: const Scaffold(body: ChatScreen()),
          ),
        ),
      );

      final textField = find.byType(TextField);
      expect(find.byType(SlashCommandPicker), findsNothing);

      // Type "/"
      await tester.enterText(textField, '/');
      await tester.pump();

      expect(find.byType(SlashCommandPicker), findsOneWidget);
      expect(find.text('/search'), findsOneWidget);
      expect(find.text('/rag'), findsOneWidget);
    });

    testWidgets('Typing /se filters to matching search commands', (WidgetTester tester) async {
      tester.view.physicalSize = const Size(1200, 800);
      tester.view.devicePixelRatio = 1.0;
      addTearDown(tester.view.resetPhysicalSize);

      await tester.pumpWidget(
        ProviderScope(
          child: MaterialApp(
            theme: AppTheme.light(),
            home: const Scaffold(body: ChatScreen()),
          ),
        ),
      );

      final textField = find.byType(TextField);

      // Type "/se"
      await tester.enterText(textField, '/se');
      await tester.pump();

      expect(find.byType(SlashCommandPicker), findsOneWidget);
      expect(find.text('/search'), findsOneWidget);
      expect(find.text('/file_read'), findsNothing);
    });

    testWidgets('Arrow navigation and Enter selection inserts command into composer', (WidgetTester tester) async {
      tester.view.physicalSize = const Size(1200, 800);
      tester.view.devicePixelRatio = 1.0;
      addTearDown(tester.view.resetPhysicalSize);

      await tester.pumpWidget(
        ProviderScope(
          child: MaterialApp(
            theme: AppTheme.light(),
            home: const Scaffold(body: ChatScreen()),
          ),
        ),
      );

      final textField = find.byType(TextField);
      await tester.tap(textField);
      await tester.enterText(textField, '/');
      await tester.pump();

      expect(find.byType(SlashCommandPicker), findsOneWidget);

      // Navigate down to /research
      await tester.sendKeyEvent(LogicalKeyboardKey.arrowDown);
      await tester.pump();

      // Press Enter to select
      await tester.sendKeyEvent(LogicalKeyboardKey.enter);
      await tester.pump();

      // Slash picker closes and text is filled with selected command
      expect(find.byType(SlashCommandPicker), findsNothing);
      final editable = tester.widget<TextField>(textField);
      expect(editable.controller?.text.startsWith('/'), isTrue);
    });

    testWidgets('Escape key dismisses the slash command picker', (WidgetTester tester) async {
      tester.view.physicalSize = const Size(1200, 800);
      tester.view.devicePixelRatio = 1.0;
      addTearDown(tester.view.resetPhysicalSize);

      await tester.pumpWidget(
        ProviderScope(
          child: MaterialApp(
            theme: AppTheme.light(),
            home: const Scaffold(body: ChatScreen()),
          ),
        ),
      );

      final textField = find.byType(TextField);
      await tester.tap(textField);
      await tester.enterText(textField, '/');
      await tester.pump();

      expect(find.byType(SlashCommandPicker), findsOneWidget);

      // Press Escape
      await tester.sendKeyEvent(LogicalKeyboardKey.escape);
      await tester.pump();

      expect(find.byType(SlashCommandPicker), findsNothing);
    });

    testWidgets('URLs and normal text containing / do not open slash command picker', (WidgetTester tester) async {
      tester.view.physicalSize = const Size(1200, 800);
      tester.view.devicePixelRatio = 1.0;
      addTearDown(tester.view.resetPhysicalSize);

      await tester.pumpWidget(
        ProviderScope(
          child: MaterialApp(
            theme: AppTheme.light(),
            home: const Scaffold(body: ChatScreen()),
          ),
        ),
      );

      final textField = find.byType(TextField);

      // Test URL
      await tester.enterText(textField, 'https://example.com/docs');
      await tester.pump();
      expect(find.byType(SlashCommandPicker), findsNothing);

      // Test Fraction
      await tester.enterText(textField, '10/20 score');
      await tester.pump();
      expect(find.byType(SlashCommandPicker), findsNothing);

      // Test Path
      await tester.enterText(textField, 'path C:/Users/name');
      await tester.pump();
      expect(find.byType(SlashCommandPicker), findsNothing);
    });
  });
}
