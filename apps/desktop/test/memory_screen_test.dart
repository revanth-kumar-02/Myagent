import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'package:kora_desktop/core/theme/app_theme.dart';
import 'package:kora_desktop/features/memory/memory_screen.dart';
import 'package:kora_desktop/models/memory_item.dart';
import 'package:kora_desktop/services/kora_api_service.dart';
import 'package:kora_desktop/state/connection_state.dart';
import 'package:kora_desktop/state/memory_state.dart';

class MockKoraApiService extends KoraApiService {
  List<MemoryItem> mockMemories = [];
  Map<String, dynamic> mockGraph = {
    'entities': [
      {'id': 'ent-user', 'name': 'User', 'type': 'person', 'label': 'User'},
      {'id': 'ent-python', 'name': 'Python', 'type': 'technology', 'label': 'Python'},
    ],
    'relationships': [
      {'source': 'User', 'target': 'Python', 'type': 'prefers', 'confidence': 0.95},
    ],
  };

  @override
  Future<List<MemoryItem>> getMemories({String? projectId}) async {
    return mockMemories;
  }

  @override
  Future<MemoryItem> createMemory({
    required String content,
    String type = 'user_preference',
    double confidence = 1.0,
    String? projectId,
  }) async {
    final item = MemoryItem(
      id: 'mem-${mockMemories.length + 1}',
      content: content,
      type: type,
      confidence: confidence,
      createdAt: DateTime.now().toIso8601String(),
      projectId: projectId,
    );
    mockMemories.insert(0, item);
    return item;
  }

  @override
  Future<MemoryItem> updateMemory(
    String memoryId, {
    String? content,
    String? type,
    double? confidence,
    double? importance,
    String? status,
  }) async {
    final index = mockMemories.indexWhere((m) => m.id == memoryId);
    if (index != -1) {
      final existing = mockMemories[index];
      final updated = MemoryItem(
        id: existing.id,
        content: content ?? existing.content,
        type: type ?? existing.type,
        confidence: confidence ?? existing.confidence,
        importance: importance ?? existing.importance,
        source: existing.source,
        status: status ?? existing.status,
        createdAt: existing.createdAt,
        updatedAt: DateTime.now().toIso8601String(),
        projectId: existing.projectId,
      );
      mockMemories[index] = updated;
      return updated;
    }
    throw Exception('Not found');
  }

  @override
  Future<MemoryItem> toggleMemoryStatus(String memoryId) async {
    final index = mockMemories.indexWhere((m) => m.id == memoryId);
    if (index != -1) {
      final existing = mockMemories[index];
      final updated = MemoryItem(
        id: existing.id,
        content: existing.content,
        type: existing.type,
        confidence: existing.confidence,
        importance: existing.importance,
        source: existing.source,
        status: existing.status == 'active' ? 'archived' : 'active',
        createdAt: existing.createdAt,
        updatedAt: DateTime.now().toIso8601String(),
        projectId: existing.projectId,
      );
      mockMemories[index] = updated;
      return updated;
    }
    throw Exception('Not found');
  }

  @override
  Future<void> deleteMemory(String memoryId) async {
    mockMemories.removeWhere((m) => m.id == memoryId);
  }

  @override
  Future<Map<String, dynamic>> getKnowledgeGraph({String? projectId}) async {
    return mockGraph;
  }

  @override
  Future<Map<String, dynamic>> getMemoryStats({String? projectId}) async {
    return {
      'active_count': mockMemories.length,
      'total_memories': mockMemories.length,
      'avg_confidence': 0.95,
      'by_type': {'user_preference': 1, 'decision': 1},
    };
  }
}

void main() {
  setUp(() {
    SharedPreferences.setMockInitialValues({});
  });

  group('Memory & Knowledge Screen Tests', () {
    testWidgets('Shows empty state when no memories exist', (WidgetTester tester) async {
      tester.view.physicalSize = const Size(1200, 800);
      tester.view.devicePixelRatio = 1.0;
      addTearDown(tester.view.resetPhysicalSize);

      final mockApi = MockKoraApiService();
      mockApi.mockMemories = [];

      await tester.pumpWidget(
        ProviderScope(
          overrides: [
            apiServiceProvider.overrideWithValue(mockApi),
          ],
          child: MaterialApp(
            theme: AppTheme.dark(),
            home: const Scaffold(body: MemoryScreen()),
          ),
        ),
      );

      await tester.pumpAndSettle();

      expect(find.text('MEMORY & KNOWLEDGE'), findsOneWidget);
      expect(find.text("Kora hasn't learned anything important yet."), findsOneWidget);
      // Ensure "Add Memory" primary button is NOT present
      expect(find.text('Add Memory'), findsNothing);
    });

    testWidgets('Renders real memories, tabs, and supports correction and forget', (WidgetTester tester) async {
      tester.view.physicalSize = const Size(1200, 800);
      tester.view.devicePixelRatio = 1.0;
      addTearDown(tester.view.resetPhysicalSize);

      final mockApi = MockKoraApiService();
      mockApi.mockMemories = [
        MemoryItem(
          id: 'mem-1',
          content: 'User prefers Python for backend development and pytest for testing.',
          type: 'user_preference',
          confidence: 0.95,
          importance: 0.85,
          source: 'user_explicit',
          createdAt: DateTime.now().toIso8601String(),
        ),
        MemoryItem(
          id: 'mem-2',
          content: 'Decided to use Riverpod for desktop state management.',
          type: 'decision',
          confidence: 0.90,
          importance: 0.80,
          source: 'user_explicit',
          createdAt: DateTime.now().toIso8601String(),
        ),
      ];

      await tester.pumpWidget(
        ProviderScope(
          overrides: [
            apiServiceProvider.overrideWithValue(mockApi),
          ],
          child: MaterialApp(
            theme: AppTheme.light(),
            home: const Scaffold(body: MemoryScreen()),
          ),
        ),
      );

      await tester.pumpAndSettle();

      // Verify memory items are rendered
      expect(find.text('User prefers Python for backend development and pytest for testing.'), findsOneWidget);
      expect(find.text('Decided to use Riverpod for desktop state management.'), findsOneWidget);
      expect(find.text('PREFERENCE'), findsOneWidget);
      expect(find.text('DECISION'), findsOneWidget);

      // Filter by Decisions
      await tester.tap(find.text('Decisions'));
      await tester.pumpAndSettle();

      expect(find.text('Decided to use Riverpod for desktop state management.'), findsOneWidget);
      expect(find.text('User prefers Python for backend development and pytest for testing.'), findsNothing);

      // Switch to Entities & Graph tab
      await tester.ensureVisible(find.text('Entities & Graph'));
      await tester.tap(find.text('Entities & Graph'));
      await tester.pumpAndSettle();

      expect(find.text('Extracted Knowledge Entities'), findsOneWidget);
      expect(find.text('Semantic Graph Relationships'), findsOneWidget);
      expect(find.text('Python'), findsWidgets);
      expect(find.text(' [prefers] '), findsOneWidget);

      // Return to All Memories
      await tester.tap(find.text('All Memories'));
      await tester.pumpAndSettle();

      // Open Correct Memory dialog
      await tester.tap(find.byTooltip('Correct / Edit Memory').first);
      await tester.pumpAndSettle();

      expect(find.text('Correct Memory Record'), findsOneWidget);
      expect(find.text('Save Correction'), findsOneWidget);

      // Close dialog
      await tester.tap(find.text('Cancel'));
      await tester.pumpAndSettle();

      // Open Forget dialog
      await tester.tap(find.byTooltip('Forget Memory').first);
      await tester.pumpAndSettle();

      expect(find.text('Forget Memory?'), findsOneWidget);
      expect(find.text('Forget Permanently'), findsOneWidget);

      // Confirm forget
      await tester.tap(find.text('Forget Permanently'));
      await tester.pumpAndSettle();

      expect(find.text('User prefers Python for backend development and pytest for testing.'), findsNothing);
    });
  });
}
