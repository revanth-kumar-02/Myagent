import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../models/model_info.dart';
import '../services/kora_api_service.dart';
import 'connection_state.dart';

class SettingsState {
  final ThemeMode themeMode;
  final String backendHttpUrl;
  final String backendWsUrl;
  final List<ModelInfo> availableModels;
  final bool isLoading;
  final String? errorMessage;

  const SettingsState({
    this.themeMode = ThemeMode.light,
    this.backendHttpUrl = 'http://127.0.0.1:8765',
    this.backendWsUrl = 'ws://127.0.0.1:8765/ws',
    this.availableModels = const [],
    this.isLoading = false,
    this.errorMessage,
  });


  SettingsState copyWith({
    ThemeMode? themeMode,
    String? backendHttpUrl,
    String? backendWsUrl,
    List<ModelInfo>? availableModels,
    bool? isLoading,
    String? errorMessage,
  }) {
    return SettingsState(
      themeMode: themeMode ?? this.themeMode,
      backendHttpUrl: backendHttpUrl ?? this.backendHttpUrl,
      backendWsUrl: backendWsUrl ?? this.backendWsUrl,
      availableModels: availableModels ?? this.availableModels,
      isLoading: isLoading ?? this.isLoading,
      errorMessage: errorMessage ?? this.errorMessage,
    );
  }
}

class SettingsNotifier extends StateNotifier<SettingsState> {
  final KoraApiService _apiService;

  SettingsNotifier(this._apiService) : super(const SettingsState()) {
    loadModelInfo();
  }

  Future<void> loadModelInfo() async {
    state = state.copyWith(isLoading: true, errorMessage: null);
    try {
      final list = await _apiService.getModels();
      state = state.copyWith(availableModels: list, isLoading: false);
    } catch (e) {
      state = state.copyWith(isLoading: false, errorMessage: e.toString());
    }
  }

  void toggleTheme() {
    final next = state.themeMode == ThemeMode.dark ? ThemeMode.light : ThemeMode.dark;
    state = state.copyWith(themeMode: next);
  }

  void updateBackendUrls({required String httpUrl, required String wsUrl}) {
    state = state.copyWith(backendHttpUrl: httpUrl, backendWsUrl: wsUrl);
  }
}

final settingsProvider = StateNotifierProvider<SettingsNotifier, SettingsState>((ref) {
  final api = ref.watch(apiServiceProvider);
  return SettingsNotifier(api);
});
