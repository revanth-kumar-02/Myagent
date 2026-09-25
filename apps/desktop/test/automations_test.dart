import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:kora_desktop/core/theme/app_theme.dart';
import 'package:kora_desktop/features/tasks/tasks_screen.dart';
import 'package:kora_desktop/models/automation_model.dart';
import 'package:kora_desktop/services/kora_api_service.dart';
import 'package:kora_desktop/services/kora_socket_service.dart';
import 'package:kora_desktop/shared/protocol/message_types.dart';
import 'package:kora_desktop/shared/protocol/ws_message.dart';
import 'package:kora_desktop/state/connection_state.dart';
import 'package:kora_desktop/state/tasks_state.dart';

class MockKoraApiService extends KoraApiService {
  List<AutomationItem> mockAutomations = [];
  Map<String, int> mockSummary = {
    'total': 0,
    'active': 0,
    'running': 0,
    'scheduled': 0,
    'failed': 0,
    'completed': 0,
  };
  List<AutomationTemplate> mockTemplates = [
    const AutomationTemplate(
      id: 'tpl_1',
      category: 'RESEARCH',
      name: 'Daily AI Research Brief',
      description: 'Performs automated web research via DuckDuckGo',
      goal: 'Search the web for latest AI models',
      triggerType: 'cron',
      triggerConfig: {'cron_expr': '0 8 * * *'},
      allowedTools: ['web_search'],
      plannedActions: ['Execute search', 'Synthesize brief'],
    ),
  ];

  @override
  Future<Map<String, dynamic>> getAutomations({String? status}) async {
    return {
      'automations': mockAutomations.map((a) => a.toJson()).toList(),
      'summary': mockSummary,
    };
  }

  @override
  Future<List<AutomationTemplate>> getAutomationTemplates() async {
    return mockTemplates;
  }

  @override
  Future<AutomationItem> createAutomation(Map<String, dynamic> data) async {
    final item = AutomationItem.fromJson({
      'id': 'auto-new-1',
      ...data,
      'created_at': DateTime.now().toIso8601String(),
    });
    mockAutomations.add(item);
    return item;
  }

  @override
  Future<void> runAutomation(String id) async {}

  @override
  Future<void> pauseAutomation(String id) async {
    final idx = mockAutomations.indexWhere((a) => a.id == id);
    if (idx != -1) {
      mockAutomations[idx] = AutomationItem.fromJson({
        ...mockAutomations[idx].toJson(),
        'status': 'paused',
      });
    }
  }

  @override
  Future<void> resumeAutomation(String id) async {
    final idx = mockAutomations.indexWhere((a) => a.id == id);
    if (idx != -1) {
      mockAutomations[idx] = AutomationItem.fromJson({
        ...mockAutomations[idx].toJson(),
        'status': 'active',
      });
    }
  }

  @override
  Future<void> deleteAutomation(String id) async {
    mockAutomations.removeWhere((a) => a.id == id);
  }

  @override
  Future<Map<String, dynamic>> interpretAutomationPrompt(String prompt) async {
    return {
      'interpreted': true,
      'name': 'Interpreted Job',
      'description': 'Interpreted description',
      'goal': prompt,
      'category': 'RESEARCH',
      'trigger_type': 'cron',
      'trigger_config': {'cron_expr': '0 8 * * *'},
      'schedule_label': 'Daily at 08:00 AM',
      'allowed_tools': ['web_search'],
      'permission_scope': {'allowed_tools': ['web_search']},
      'planned_actions': ['Inspect', 'Execute', 'Summarize'],
    };
  }
}

void main() {
  group('Kora Automation Center Model Tests', () {
    test('AutomationItem fromJson and toJson roundtrip', () {
      final json = {
        'id': 'auto-123',
        'name': 'Git Watcher',
        'description': 'Watches repo',
        'goal': 'Inspect git status',
        'status': 'active',
        'priority': 'high',
        'trigger_type': 'interval',
        'trigger': {
          'trigger_type': 'interval',
          'interval_seconds': 1800,
        },
        'allowed_tools': ['git_ops'],
        'permission_scope': {'allowed_tools': ['git_ops']},
        'created_at': '2026-09-25T08:00:00Z',
        'next_run_at': '2026-09-25T08:30:00Z',
      };

      final item = AutomationItem.fromJson(json);
      expect(item.id, 'auto-123');
      expect(item.name, 'Git Watcher');
      expect(item.status, 'active');
      expect(item.triggerType, 'interval');
      expect(item.allowedTools, ['git_ops']);
      expect(item.scheduleLabel, 'Every 30m');
    });

    test('AutomationExecution and AutomationStep fromJson', () {
      final json = {
        'run_id': 'run-99',
        'task_id': 'auto-123',
        'run_number': 1,
        'status': 'completed',
        'started_at': '2026-09-25T08:00:00Z',
        'completed_at': '2026-09-25T08:00:02Z',
        'duration_ms': 2100,
        'model_used': 'HuggingFace Cloud (Online)',
        'result': 'Summary completed',
        'steps': [
          {
            'step_id': 's1',
            'step_index': 1,
            'goal': 'Run git status',
            'tool_name': 'git_ops',
            'status': 'completed',
            'duration_ms': 400,
            'output': {'branch': 'main'},
          }
        ],
      };

      final exec = AutomationExecution.fromJson(json);
      expect(exec.runId, 'run-99');
      expect(exec.status, 'completed');
      expect(exec.durationMs, 2100);
      expect(exec.modelUsed, 'HuggingFace Cloud (Online)');
      expect(exec.steps.length, 1);
      expect(exec.steps.first.toolName, 'git_ops');
      expect(exec.steps.first.output, {'branch': 'main'});
    });
  });

  group('Kora Automation Center UI & State Tests', () {
    testWidgets('Renders Kora Automation Center with empty state', (tester) async {
      tester.view.physicalSize = const Size(1200, 800);
      tester.view.devicePixelRatio = 1.0;
      addTearDown(tester.view.resetPhysicalSize);

      final mockApi = MockKoraApiService();

      await tester.pumpWidget(
        ProviderScope(
          overrides: [
            apiServiceProvider.overrideWithValue(mockApi),
          ],
          child: MaterialApp(
            theme: AppTheme.light(),
            home: const Scaffold(body: TasksScreen()),
          ),
        ),
      );

      await tester.pumpAndSettle();

      expect(find.text('Kora Automation Center'), findsOneWidget);
      expect(find.text('Autonomous background workflows, scheduled triggers, and dynamic agent jobs.'), findsOneWidget);
      expect(find.text('+ New Automation'), findsAtLeastNWidgets(1));
      expect(find.text('Refresh'), findsOneWidget);

      // Metrics bar
      expect(find.text('Active'), findsOneWidget);
      expect(find.text('Running'), findsOneWidget);
      expect(find.text('Scheduled'), findsOneWidget);
      expect(find.text('Failed'), findsOneWidget);
      expect(find.text('Completed'), findsOneWidget);

      // Honest empty state
      expect(find.text('No automations yet.'), findsOneWidget);
    });

    testWidgets('Renders real automation card and controls', (tester) async {
      tester.view.physicalSize = const Size(1200, 800);
      tester.view.devicePixelRatio = 1.0;
      addTearDown(tester.view.resetPhysicalSize);

      final mockApi = MockKoraApiService();
      mockApi.mockAutomations = [
        const AutomationItem(
          id: 'auto-1',
          name: 'Daily AI Research Brief',
          description: 'Automated research briefing',
          goal: 'Search the web for top AI models',
          status: 'active',
          triggerType: 'interval',
          triggerConfig: {'interval_seconds': 3600},
          allowedTools: ['web_search'],
          createdAt: '2026-09-25T08:00:00Z',
          nextRunAt: '2026-09-25T09:00:00Z',
        ),
      ];
      mockApi.mockSummary = {
        'total': 1,
        'active': 1,
        'running': 0,
        'scheduled': 1,
        'failed': 0,
        'completed': 0,
      };

      await tester.pumpWidget(
        ProviderScope(
          overrides: [
            apiServiceProvider.overrideWithValue(mockApi),
          ],
          child: MaterialApp(
            theme: AppTheme.light(),
            home: const Scaffold(body: TasksScreen()),
          ),
        ),
      );

      await tester.pumpAndSettle();

      // Card rendered
      expect(find.text('Daily AI Research Brief'), findsOneWidget);
      expect(find.text('Automated research briefing'), findsOneWidget);
      expect(find.text('Goal: Search the web for top AI models'), findsOneWidget);
      expect(find.text('web_search'), findsOneWidget);
      expect(find.text('ACTIVE'), findsAtLeastNWidgets(1));
      expect(find.text('Every 1h'), findsOneWidget);

      // Buttons
      expect(find.byTooltip('Run now'), findsOneWidget);
      expect(find.byTooltip('Pause'), findsOneWidget);
      expect(find.byTooltip('View Trace & History'), findsOneWidget);
      expect(find.byTooltip('Delete'), findsOneWidget);
    });

    testWidgets('Opens New Automation Modal with 3 tabs', (tester) async {
      tester.view.physicalSize = const Size(1200, 800);
      tester.view.devicePixelRatio = 1.0;
      addTearDown(tester.view.resetPhysicalSize);

      final mockApi = MockKoraApiService();

      await tester.pumpWidget(
        ProviderScope(
          overrides: [
            apiServiceProvider.overrideWithValue(mockApi),
          ],
          child: MaterialApp(
            theme: AppTheme.light(),
            home: const Scaffold(body: TasksScreen()),
          ),
        ),
      );

      await tester.pumpAndSettle();

      // Tap + New Automation
      await tester.tap(find.text('+ New Automation').first);
      await tester.pumpAndSettle();

      expect(find.text('Create Autonomous Automation'), findsOneWidget);
      expect(find.text('Natural Language'), findsOneWidget);
      expect(find.text('Custom Builder'), findsOneWidget);
      expect(find.text('Starter Templates'), findsOneWidget);
      expect(find.text('Interpret with Kora'), findsOneWidget);
    });
  });
}
