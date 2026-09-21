import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../services/kora_api_service.dart';
import '../services/kora_socket_service.dart';

enum BackendStatus { connecting, online, offline }

class ConnectionState {
  final BackendStatus status;
  final String? errorMessage;
  final double uptimeSeconds;
  final int modelsAvailable;

  const ConnectionState({
    this.status = BackendStatus.connecting,
    this.errorMessage,
    this.uptimeSeconds = 0.0,
    this.modelsAvailable = 0,
  });

  ConnectionState copyWith({
    BackendStatus? status,
    String? errorMessage,
    double? uptimeSeconds,
    int? modelsAvailable,
  }) {
    return ConnectionState(
      status: status ?? this.status,
      errorMessage: errorMessage,
      uptimeSeconds: uptimeSeconds ?? this.uptimeSeconds,
      modelsAvailable: modelsAvailable ?? this.modelsAvailable,
    );
  }
}

final apiServiceProvider = Provider<KoraApiService>((ref) {
  return KoraApiService();
});

final socketServiceProvider = Provider<KoraSocketService>((ref) {
  final service = KoraSocketService();
  service.start();
  ref.onDispose(() {
    service.dispose();
  });
  return service;
});

class ConnectionNotifier extends StateNotifier<ConnectionState> {
  final KoraApiService _apiService;

  ConnectionNotifier(this._apiService) : super(const ConnectionState()) {
    checkConnection();
  }

  Future<void> checkConnection() async {
    state = state.copyWith(status: BackendStatus.connecting);
    try {
      final health = await _apiService.checkHealth();
      state = state.copyWith(
        status: BackendStatus.online,
        uptimeSeconds: (health['uptime_seconds'] as num?)?.toDouble() ?? 0.0,
        modelsAvailable: health['models_available'] as int? ?? 0,
        errorMessage: null,
      );
    } catch (e) {
      state = state.copyWith(
        status: BackendStatus.offline,
        errorMessage: e.toString(),
      );
    }
  }
}

final connectionProvider = StateNotifierProvider<ConnectionNotifier, ConnectionState>((ref) {
  final api = ref.watch(apiServiceProvider);
  return ConnectionNotifier(api);
});
