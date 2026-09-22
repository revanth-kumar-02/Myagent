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

  const MemoryState({
    this.memories = const [],
    this.entities = const [],
    this.relationships = const [],
    this.isLoading = false,
    this.errorMessage,
    this.filterType,
    this.searchQuery = '',
  });

  MemoryState copyWith({
    List<MemoryItem>? memories,
    List<GraphEntityItem>? entities,
    List<GraphRelationshipItem>? relationships,
    bool? isLoading,
    String? errorMessage,
    String? filterType,
    String? searchQuery,
  }) {
    return MemoryState(
      memories: memories ?? this.memories,
      entities: entities ?? this.entities,
      relationships: relationships ?? this.relationships,
      isLoading: isLoading ?? this.isLoading,
      errorMessage: errorMessage ?? this.errorMessage,
      filterType: filterType ?? this.filterType,
      searchQuery: searchQuery ?? this.searchQuery,
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
      final list = await _apiService.getMemories(projectId: projectId);
      final graphRes = await _apiService.getKnowledgeGraph(projectId: projectId);
      
      final rawEntities = graphRes['entities'] as List<dynamic>? ?? [];
      final rawRels = graphRes['relationships'] as List<dynamic>? ?? [];

      final entities = rawEntities.map((e) => GraphEntityItem.fromJson(e as Map<String, dynamic>)).toList();
      final rels = rawRels.map((e) => GraphRelationshipItem.fromJson(e as Map<String, dynamic>)).toList();

      state = state.copyWith(
        memories: list,
        entities: entities,
        relationships: rels,
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
