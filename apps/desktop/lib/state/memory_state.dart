import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../models/memory_item.dart';
import '../services/kora_api_service.dart';
import 'connection_state.dart';

class MemoryState {
  final List<MemoryItem> memories;
  final bool isLoading;
  final String? errorMessage;
  final String? filterType;

  const MemoryState({
    this.memories = const [],
    this.isLoading = false,
    this.errorMessage,
    this.filterType,
  });

  MemoryState copyWith({
    List<MemoryItem>? memories,
    bool? isLoading,
    String? errorMessage,
    String? filterType,
  }) {
    return MemoryState(
      memories: memories ?? this.memories,
      isLoading: isLoading ?? this.isLoading,
      errorMessage: errorMessage ?? this.errorMessage,
      filterType: filterType ?? this.filterType,
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
      state = state.copyWith(memories: list, isLoading: false);
    } catch (e) {
      state = state.copyWith(isLoading: false, errorMessage: e.toString());
    }
  }

  void setFilterType(String? type) {
    state = state.copyWith(filterType: type);
  }

  Future<void> addMemory({
    required String content,
    String type = 'fact',
    double confidence = 1.0,
    String? projectId,
  }) async {
    try {
      final item = await _apiService.createMemory(
        content: content,
        type: type,
        confidence: confidence,
        projectId: projectId,
      );
      state = state.copyWith(memories: [item, ...state.memories]);
    } catch (e) {
      state = state.copyWith(errorMessage: e.toString());
    }
  }

  Future<void> deleteMemory(String id) async {
    try {
      await _apiService.deleteMemory(id);
      state = state.copyWith(
        memories: state.memories.where((m) => m.id != id).toList(),
      );
    } catch (e) {
      state = state.copyWith(errorMessage: e.toString());
    }
  }
}

final memoryProvider = StateNotifierProvider<MemoryNotifier, MemoryState>((ref) {
  final api = ref.watch(apiServiceProvider);
  return MemoryNotifier(api);
});
