import 'dart:async';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../services/kora_api_service.dart';
import '../services/kora_socket_service.dart';
import '../shared/protocol/message_types.dart';
import '../shared/protocol/ws_message.dart';

enum BackendStatus { connecting, online, offline }

class ConnectionState {
  final BackendStatus status;
  final String? errorMessage;
  final double uptimeSeconds;
  final int modelsAvailable;
  final String? providerMode; // online, offline, local_fallback, no_provider, online_degraded
  final String? activeProvider; // huggingface, ollama, none
  final String? activeModel; // qwen3:1.7b, etc.
  final bool isLocalFallback;

  const ConnectionState({
    this.status = BackendStatus.connecting,
    this.errorMessage,
    this.uptimeSeconds = 0.0,
    this.modelsAvailable = 0,
    this.providerMode,
    this.activeProvider,
    this.activeModel,
    this.isLocalFallback = false,
  });

  String get displayStatusText {
    if (status == BackendStatus.connecting) return 'Connecting...';
    if (status == BackendStatus.offline) return 'Offline';

    final mode = providerMode?.toLowerCase();
    final prov = activeProvider?.toLowerCase();

    if (mode == 'no_provider' || prov == 'none') {
      return 'No provider';
    }
    if (mode == 'local_fallback' || isLocalFallback) {
      return 'Local fallback · Ollama';
    }
    if (mode == 'offline' || prov == 'ollama') {
      return 'Offline · Local AI';
    }
    if (mode == 'online' || prov == 'huggingface' || mode == 'online_degraded') {
      return 'Online · HuggingFace';
    }
    return 'Online · HuggingFace';
  }

  ConnectionState copyWith({
    BackendStatus? status,
    String? errorMessage,
    double? uptimeSeconds,
    int? modelsAvailable,
    String? providerMode,
    String? activeProvider,
    String? activeModel,
    bool? isLocalFallback,
  }) {
    return ConnectionState(
      status: status ?? this.status,
      errorMessage: errorMessage,
      uptimeSeconds: uptimeSeconds ?? this.uptimeSeconds,
      modelsAvailable: modelsAvailable ?? this.modelsAvailable,
      providerMode: providerMode ?? this.providerMode,
      activeProvider: activeProvider ?? this.activeProvider,
      activeModel: activeModel ?? this.activeModel,
      isLocalFallback: isLocalFallback ?? this.isLocalFallback,
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
  final KoraSocketService _socketService;
  StreamSubscription? _msgSub;
  StreamSubscription? _socketStatusSub;

  ConnectionNotifier(this._apiService, this._socketService) : super(const ConnectionState()) {
    _initListeners();
    checkConnection();
  }

  void _initListeners() {
    _msgSub = _socketService.messages.listen((msg) {
      if (msg.type == WsMessageType.providerStatus) {
        final mode = msg.payload['mode'] as String?;
        final provider = msg.payload['provider'] as String?;
        final model = msg.payload['model'] as String?;
        final localFallback = (msg.payload['local_fallback'] as bool?) ?? false;

        state = state.copyWith(
          providerMode: mode,
          activeProvider: provider,
          activeModel: model,
          isLocalFallback: localFallback,
        );
      }
    });

    _socketStatusSub = _socketService.stateStream.listen((sState) {
      if (sState == SocketConnectionState.connected) {
        state = state.copyWith(status: BackendStatus.online, errorMessage: null);
      } else if (sState == SocketConnectionState.connecting) {
        state = state.copyWith(status: BackendStatus.connecting);
      } else if (sState == SocketConnectionState.disconnected || sState == SocketConnectionState.error) {
        state = state.copyWith(status: BackendStatus.offline);
      }
    });
  }

  @override
  void dispose() {
    _msgSub?.cancel();
    _socketStatusSub?.cancel();
    super.dispose();
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
  final socket = ref.watch(socketServiceProvider);
  return ConnectionNotifier(api, socket);
});
