import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../models/research_result.dart';
import '../services/kora_api_service.dart';
import 'connection_state.dart';

class ResearchState {
  final String query;
  final List<ResearchResult> results;
  final bool isLoading;
  final String? errorMessage;

  const ResearchState({
    this.query = '',
    this.results = const [],
    this.isLoading = false,
    this.errorMessage,
  });

  ResearchState copyWith({
    String? query,
    List<ResearchResult>? results,
    bool? isLoading,
    String? errorMessage,
  }) {
    return ResearchState(
      query: query ?? this.query,
      results: results ?? this.results,
      isLoading: isLoading ?? this.isLoading,
      errorMessage: errorMessage ?? this.errorMessage,
    );
  }
}

class ResearchNotifier extends StateNotifier<ResearchState> {
  final KoraApiService _apiService;

  ResearchNotifier(this._apiService) : super(const ResearchState());

  Future<void> search(String query) async {
    final trimmed = query.trim();
    if (trimmed.isEmpty) return;

    state = state.copyWith(
      query: trimmed,
      isLoading: true,
      errorMessage: null,
    );

    try {
      final list = await _apiService.searchWeb(query: trimmed);
      state = state.copyWith(
        results: list,
        isLoading: false,
      );
    } catch (e) {
      state = state.copyWith(
        isLoading: false,
        errorMessage: e.toString(),
      );
    }
  }

  void clear() {
    state = const ResearchState();
  }
}

final researchProvider = StateNotifierProvider<ResearchNotifier, ResearchState>((ref) {
  final api = ref.watch(apiServiceProvider);
  return ResearchNotifier(api);
});
