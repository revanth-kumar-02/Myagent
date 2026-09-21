import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../models/model_info.dart';
import '../services/kora_api_service.dart';
import 'connection_state.dart';

class ModelsState {
  final List<ModelInfo> models;
  final bool isLoading;
  final String? errorMessage;
  final String? activeChatModel;

  const ModelsState({
    this.models = const [],
    this.isLoading = false,
    this.errorMessage,
    this.activeChatModel,
  });

  ModelsState copyWith({
    List<ModelInfo>? models,
    bool? isLoading,
    String? errorMessage,
    String? activeChatModel,
  }) {
    return ModelsState(
      models: models ?? this.models,
      isLoading: isLoading ?? this.isLoading,
      errorMessage: errorMessage,
      activeChatModel: activeChatModel ?? this.activeChatModel,
    );
  }
}

class ModelsNotifier extends StateNotifier<ModelsState> {
  final KoraApiService _apiService;

  ModelsNotifier(this._apiService) : super(const ModelsState()) {
    loadModels();
  }

  Future<void> loadModels() async {
    state = state.copyWith(isLoading: true, errorMessage: null);
    try {
      final list = await _apiService.getModels();
      final chatModel = list.firstWhere(
        (m) => m.capabilities.contains('chat'),
        orElse: () => list.isNotEmpty ? list.first : const ModelInfo(name: 'qwen-chat', provider: 'huggingface', capabilities: ['chat'], contextWindow: 32768),
      );
      state = state.copyWith(
        models: list,
        isLoading: false,
        activeChatModel: chatModel.name,
      );
    } catch (e) {
      state = state.copyWith(isLoading: false, errorMessage: e.toString());
    }
  }
}

final modelsProvider = StateNotifierProvider<ModelsNotifier, ModelsState>((ref) {
  final apiService = ref.watch(apiServiceProvider);
  return ModelsNotifier(apiService);
});
