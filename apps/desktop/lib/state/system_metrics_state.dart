import 'dart:async';
import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../models/system_metrics_model.dart';
import '../services/kora_api_service.dart';
import '../services/kora_socket_service.dart';
import '../shared/protocol/message_types.dart';
import '../shared/protocol/ws_message.dart';
import 'connection_state.dart';

class SystemMetricsState {
  final SystemMetrics metrics;
  final bool isLiveStreaming;
  final DateTime? lastUpdated;
  final String? errorMessage;

  const SystemMetricsState({
    required this.metrics,
    this.isLiveStreaming = false,
    this.lastUpdated,
    this.errorMessage,
  });

  SystemMetricsState copyWith({
    SystemMetrics? metrics,
    bool? isLiveStreaming,
    DateTime? lastUpdated,
    String? errorMessage,
  }) {
    return SystemMetricsState(
      metrics: metrics ?? this.metrics,
      isLiveStreaming: isLiveStreaming ?? this.isLiveStreaming,
      lastUpdated: lastUpdated ?? this.lastUpdated,
      errorMessage: errorMessage,
    );
  }
}

class SystemMetricsNotifier extends StateNotifier<SystemMetricsState> {
  final KoraApiService _apiService;
  final KoraSocketService _socketService;
  StreamSubscription<WsMessage>? _wsSubscription;
  StreamSubscription<SocketConnectionState>? _connSubscription;

  SystemMetricsNotifier({
    required KoraApiService apiService,
    required KoraSocketService socketService,
  })  : _apiService = apiService,
        _socketService = socketService,
        super(SystemMetricsState(metrics: SystemMetrics.empty())) {
    _init();
  }

  void _init() {
    // 1. Initial snapshot fetch via REST
    refresh();

    // 2. Listen to WebSocket telemetry stream
    _wsSubscription = _socketService.messages.listen(_handleWsMessage);

    // 3. Monitor connection state
    _connSubscription = _socketService.stateStream.listen((connState) {
      if (connState == SocketConnectionState.connected) {
        state = state.copyWith(isLiveStreaming: true);
      } else {
        state = state.copyWith(isLiveStreaming: false);
      }
    });

    if (_socketService.isConnected) {
      state = state.copyWith(isLiveStreaming: true);
    }
  }

  Future<void> refresh() async {
    try {
      final metrics = await _apiService.getSystemMetrics();
      state = state.copyWith(
        metrics: metrics,
        lastUpdated: DateTime.now(),
        errorMessage: null,
      );
    } catch (e) {
      debugPrint('[SystemMetricsNotifier] Initial fetch failed: $e');
      // Do not wipe existing metrics on error
      state = state.copyWith(errorMessage: e.toString());
    }
  }

  void _handleWsMessage(WsMessage msg) {
    if (msg.type == WsMessageType.systemMetrics) {
      try {
        final metrics = SystemMetrics.fromJson(msg.payload);
        state = state.copyWith(
          metrics: metrics,
          isLiveStreaming: true,
          lastUpdated: DateTime.now(),
          errorMessage: null,
        );
      } catch (e) {
        debugPrint('[SystemMetricsNotifier] Error parsing SYSTEM_METRICS: $e');
      }
    }
  }

  @override
  void dispose() {
    _wsSubscription?.cancel();
    _connSubscription?.cancel();
    super.dispose();
  }
}

final systemMetricsProvider =
    StateNotifierProvider<SystemMetricsNotifier, SystemMetricsState>((ref) {
  final api = ref.watch(apiServiceProvider);
  final socket = ref.watch(socketServiceProvider);
  return SystemMetricsNotifier(apiService: api, socketService: socket);
});
