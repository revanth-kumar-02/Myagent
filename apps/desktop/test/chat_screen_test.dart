import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:kora_desktop/core/theme/app_theme.dart';
import 'package:kora_desktop/features/chat/chat_screen.dart';
import 'package:kora_desktop/models/citation.dart';
import 'package:kora_desktop/models/plan_step.dart';
import 'package:kora_desktop/widgets/citation_card.dart';
import 'package:kora_desktop/widgets/plan_progress_card.dart';
import 'package:kora_desktop/widgets/tool_badge.dart';

void main() {
  group('Chat Widgets & Screen Tests', () {
    testWidgets('ChatScreen shows input and triggers send', (WidgetTester tester) async {
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

      expect(find.byType(TextField), findsOneWidget);
      expect(find.text('Send'), findsOneWidget);

      await tester.enterText(find.byType(TextField), 'Test message');
      expect(find.text('Test message'), findsOneWidget);

      await tester.tap(find.text('Send'));
      await tester.pump();
    });

    testWidgets('PlanProgressCard renders steps with status icons', (WidgetTester tester) async {
      const steps = [
        PlanStep(index: 0, label: 'Retrieve RAG chunks', status: PlanStepStatus.done),
        PlanStep(index: 1, label: 'Search DuckDuckGo', status: PlanStepStatus.running),
        PlanStep(index: 2, label: 'Synthesize answer', status: PlanStepStatus.pending),
      ];

      await tester.pumpWidget(
        MaterialApp(
          theme: AppTheme.light(),
          home: const Scaffold(
            body: PlanProgressCard(steps: steps),
          ),
        ),
      );

      expect(find.text('Autonomous Plan (1/3 Steps)'), findsOneWidget);
      expect(find.text('Retrieve RAG chunks'), findsOneWidget);
      expect(find.text('Search DuckDuckGo'), findsOneWidget);
      expect(find.text('Synthesize answer'), findsOneWidget);
    });

    testWidgets('CitationCard renders RAG and Web sources', (WidgetTester tester) async {
      const ragSources = [
        RagSource(chunkId: 'c1', filePath: 'apps/agent/core/model_router.py', startLine: 1, endLine: 50),
      ];
      const webSources = [
        WebSource(url: 'https://duckduckgo.com', title: 'DuckDuckGo Engine', snippet: 'Privacy search'),
      ];

      await tester.pumpWidget(
        MaterialApp(
          theme: AppTheme.light(),
          home: const Scaffold(
            body: CitationCard(sources: ragSources, webSources: webSources),
          ),
        ),
      );

      expect(find.text('Sources & Evidence (2)'), findsOneWidget);
      expect(find.textContaining('apps/agent/core/model_router.py'), findsOneWidget);
      expect(find.text('DuckDuckGo Engine'), findsOneWidget);
      expect(find.text('https://duckduckgo.com'), findsOneWidget);
    });

    testWidgets('ToolBadge renders tool name', (WidgetTester tester) async {
      await tester.pumpWidget(
        MaterialApp(
          theme: AppTheme.light(),
          home: const Scaffold(
            body: ToolBadge(toolName: 'duckduckgo_search', isExecuting: true),
          ),
        ),
      );

      expect(find.text('duckduckgo_search'), findsOneWidget);
      expect(find.byType(CircularProgressIndicator), findsOneWidget);
    });
  });
}
