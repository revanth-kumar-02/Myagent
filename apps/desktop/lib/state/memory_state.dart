import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../models/memory_item.dart';
import '../services/kora_api_service.dart';
import 'connection_state.dart';

class MemoryState {
  final List<MemoryItem> memories;
  final List<GraphEntityItem> entities;
  final List<GraphRelationshipItem> relationships;
  final bool isLoading;
  final String? errorMessage;
  final String? filterType;
  final String searchQuery;

  // Live stats from /memory/stats
  final int activeCount;
  final int totalMemories;
  final double avgConfidence;
  final Map<String, int> byType;

  const MemoryState({
    this.memories = const [],
    this.entities = const [],
    this.relationships = const [],
    this.isLoading = false,
    this.errorMessage,
    this.filterType,
    this.searchQuery = '',
    this.activeCount = 0,
    this.totalMemories = 0,
    this.avgConfidence = 0.0,
    this.byType = const {},
  });

  MemoryState copyWith({
    List<MemoryItem>? memories,
    List<GraphEntityItem>? entities,
    List<GraphRelationshipItem>? relationships,
    bool? isLoading,
    String? errorMessage,
    String? filterType,
    String? searchQuery,
    int? activeCount,
    int? totalMemories,
    double? avgConfidence,
    Map<String, int>? byType,
  }) {
    return MemoryState(
      memories: memories ?? this.memories,
      entities: entities ?? this.entities,
      relationships: relationships ?? this.relationships,
      isLoading: isLoading ?? this.isLoading,
      errorMessage: errorMessage ?? this.errorMessage,
      filterType: filterType ?? this.filterType,
      searchQuery: searchQuery ?? this.searchQuery,
      activeCount: activeCount ?? this.activeCount,
      totalMemories: totalMemories ?? this.totalMemories,
      avgConfidence: avgConfidence ?? this.avgConfidence,
      byType: byType ?? this.byType,
    );
  }
}

class MemoryNotifier extends StateNotifier<MemoryState> {
  final KoraApiService _apiService;

  MemoryNotifier(this._apiService) : super(const MemoryState()) {
    loadMemories();
  }

  Future<void> loadMemories({String? projectId}) async {
    state = state.copyWith(isLoading: true, errorMessage: null);
    try {
      // Fetch memories, graph, and stats in parallel
      final results = await Future.wait([
        _apiService.getMemories(projectId: projectId),
        _apiService.getKnowledgeGraph(projectId: projectId),
        _apiService.getMemoryStats(projectId: projectId),
      ]);

      final list = results[0] as List<MemoryItem>;
      final graphRes = results[1] as Map<String, dynamic>;
      final statsRes = results[2] as Map<String, dynamic>;

      final rawEntities = graphRes['entities'] as List<dynamic>? ?? [];
      final rawRels = graphRes['relationships'] as List<dynamic>? ?? [];
      final entities = rawEntities.map((e) => GraphEntityItem.fromJson(e as Map<String, dynamic>)).toList();
      final rels = rawRels.map((e) => GraphRelationshipItem.fromJson(e as Map<String, dynamic>)).toList();

      final rawByType = statsRes['by_type'] as Map<String, dynamic>? ?? {};
      final byType = rawByType.map((k, v) => MapEntry(k, (v as num).toInt()));

      state = state.copyWith(
        memories: list,
        entities: entities,
        relationships: rels,
        activeCount: (statsRes['active_count'] as num?)?.toInt() ?? list.length,
        totalMemories: (statsRes['total_memories'] as num?)?.toInt() ?? list.length,
        avgConfidence: (statsRes['avg_confidence'] as num?)?.toDouble() ?? 0.0,
        byType: byType,
        isLoading: false,
      );
    } catch (e) {
      state = state.copyWith(isLoading: false, errorMessage: e.toString());
    }
  }

  void setFilterType(String? type) {
    state = state.copyWith(filterType: type);
  }

  void setSearchQuery(String query) {
    state = state.copyWith(searchQuery: query);
  }

  Future<void> correctMemory(
    String id, {
    String? content,
    String? type,
    double? confidence,
    double? importance,
  }) async {
    try {
      final updated = await _apiService.updateMemory(
        id,
        content: content,
        type: type,
        confidence: confidence,
        importance: importance,
      );
      state = state.copyWith(
        memories: state.memories.map((m) => m.id == id ? updated : m).toList(),
      );
    } catch (e) {
      state = state.copyWith(errorMessage: e.toString());
    }
  }

  Future<void> toggleMemoryStatus(String id) async {
    try {
      final updated = await _apiService.toggleMemoryStatus(id);
      state = state.copyWith(
        memories: state.memories.map((m) => m.id == id ? updated : m).toList(),
      );
    } catch (e) {
      state = state.copyWith(errorMessage: e.toString());
    }
  }

  Future<void> forgetMemory(String id) async {
    try {
      await _apiService.deleteMemory(id);
      state = state.copyWith(
        memories: state.memories.where((m) => m.id != id).toList(),
        activeCount: state.activeCount > 0 ? state.activeCount - 1 : 0,
      );
    } catch (e) {
      state = state.copyWith(errorMessage: e.toString());
    }
  }

  // Alias for backward compatibility if called programmatically
  Future<void> deleteMemory(String id) async => forgetMemory(id);
}

final memoryProvider = StateNotifierProvider<MemoryNotifier, MemoryState>((ref) {
  final api = ref.watch(apiServiceProvider);
  return MemoryNotifier(api);
});

