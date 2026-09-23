import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shared_preferences/shared_preferences.dart';
import '../core/config/app_config.dart';
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
    this.backendHttpUrl = AppConfig.fallbackHttpUrl,
    this.backendWsUrl = AppConfig.fallbackWsUrl,
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
  static const _themePrefKey = 'kora_theme_mode';
  final KoraApiService _apiService;

  SettingsNotifier(this._apiService) : super(const SettingsState()) {
    _loadPersistedSettings();
    loadModelInfo();
  }

  Future<void> _loadPersistedSettings() async {
    try {
      final envHttp = AppConfig.defaultHttpUrl;
      final envWs = AppConfig.defaultWsUrl;
      if (envHttp != AppConfig.fallbackHttpUrl || envWs != AppConfig.fallbackWsUrl) {
        state = state.copyWith(backendHttpUrl: envHttp, backendWsUrl: envWs);
      }

      final prefs = await SharedPreferences.getInstance();
      final modeStr = prefs.getString(_themePrefKey);
      if (modeStr != null) {
        final mode = switch (modeStr) {
          'dark' => ThemeMode.dark,
          'light' => ThemeMode.light,
          'system' => ThemeMode.system,
          _ => ThemeMode.light,
        };
        state = state.copyWith(themeMode: mode);
      }
    } catch (_) {
      // Keep default light theme if preferences cannot be accessed
    }
  }

  Future<void> setThemeMode(ThemeMode mode) async {
    state = state.copyWith(themeMode: mode);
    try {
      final prefs = await SharedPreferences.getInstance();
      final modeStr = switch (mode) {
        ThemeMode.dark => 'dark',
        ThemeMode.light => 'light',
        ThemeMode.system => 'system',
      };
      await prefs.setString(_themePrefKey, modeStr);
    } catch (_) {}
  }

  void toggleTheme() {
    final next = state.themeMode == ThemeMode.dark ? ThemeMode.light : ThemeMode.dark;
    setThemeMode(next);
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

  void updateBackendUrls({required String httpUrl, required String wsUrl}) {
    state = state.copyWith(backendHttpUrl: httpUrl, backendWsUrl: wsUrl);
  }
}

final settingsProvider = StateNotifierProvider<SettingsNotifier, SettingsState>((ref) {
  final api = ref.watch(apiServiceProvider);
  return SettingsNotifier(api);
});
