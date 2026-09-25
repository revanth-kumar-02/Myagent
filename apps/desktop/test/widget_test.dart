import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'package:kora_desktop/app.dart';
import 'package:kora_desktop/widgets/sidebar.dart';

void main() {
  setUp(() {
    SharedPreferences.setMockInitialValues({});
  });

  testWidgets('AppShell renders with sidebar and home dashboard', (WidgetTester tester) async {
    // Set desktop window size
    tester.view.physicalSize = const Size(1200, 800);
    tester.view.devicePixelRatio = 1.0;
    addTearDown(tester.view.resetPhysicalSize);

    await tester.pumpWidget(
      const ProviderScope(
        child: KoraApp(),
      ),
    );

    // Verify brand title
    expect(find.text('KORA'), findsOneWidget);

    // Verify sidebar tabs
    final sidebar = find.byType(Sidebar);
    expect(find.descendant(of: sidebar, matching: find.text('Home')), findsOneWidget);
    expect(find.descendant(of: sidebar, matching: find.text('Chat')), findsOneWidget);
    expect(find.descendant(of: sidebar, matching: find.text('Projects')), findsOneWidget);
    expect(find.descendant(of: sidebar, matching: find.text('Tasks')), findsOneWidget);
    expect(find.descendant(of: sidebar, matching: find.text('Research')), findsOneWidget);
    expect(find.descendant(of: sidebar, matching: find.text('Activity')), findsOneWidget);
    expect(find.descendant(of: sidebar, matching: find.text('Memory')), findsOneWidget);
    expect(find.descendant(of: sidebar, matching: find.text('Settings')), findsOneWidget);

    // Default primary screen is Home Dashboard
    expect(find.text('Good day, Workspace User'), findsOneWidget);

    // Navigate to Chat
    await tester.tap(find.descendant(of: sidebar, matching: find.text('Chat')));
    await tester.pumpAndSettle();
    expect(find.text('Kora Chat'), findsOneWidget);
    expect(find.text('How can Kora assist you today?'), findsOneWidget);

    // Navigate to Projects
    await tester.tap(find.descendant(of: sidebar, matching: find.text('Projects')));
    await tester.pumpAndSettle();
    expect(find.text('Kora Projects'), findsWidgets);

    // Navigate to Research
    await tester.tap(find.descendant(of: sidebar, matching: find.text('Research')));
    await tester.pumpAndSettle();
    expect(find.text('DuckDuckGo Deep Research'), findsWidgets);
  });
}
