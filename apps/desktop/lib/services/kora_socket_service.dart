import 'dart:async';
import 'dart:convert';
import 'package:flutter/foundation.dart';
import 'package:uuid/uuid.dart';
import 'package:web_socket_channel/web_socket_channel.dart';

import '../shared/protocol/ws_message.dart';
import '../shared/protocol/message_types.dart';

/// Connection states for Kora WebSocket service.
enum SocketConnectionState {
  disconnected,
  connecting,
  connected,
  error,
}

/// KoraSocketService
///
/// Manages the persistent WebSocket connection to the Kora agent backend.
///
/// Responsibilities:
///   - Connect and reconnect with bounded exponential backoff
///   - Send typed WsMessage frames
///   - Expose incoming message stream & connection state stream for UI state
///   - Heartbeat keep-alive (30-second interval)
///   - Cancel active streaming states on disconnect/error
class KoraSocketService {
  static const String _defaultUrl = 'ws://127.0.0.1:8765/ws';

  final String backendUrl;
  WebSocketChannel? _channel;
  StreamSubscription? _subscription;
  Timer? _heartbeatTimer;
  Timer? _reconnectTimer;

  int _reconnectAttempts = 0;
  static const int _maxReconnectAttempts = 5;
  static const Duration _baseReconnectDelay = Duration(seconds: 1);
  bool _isReconnecting = false;

  SocketConnectionState _state = SocketConnectionState.disconnected;
  final _stateController = StreamController<SocketConnectionState>.broadcast();
  final _messageController = StreamController<WsMessage>.broadcast();

  /// Current connection state.
  SocketConnectionState get state => _state;

  /// Stream of connection state changes.
  Stream<SocketConnectionState> get stateStream => _stateController.stream;

  /// Stream of incoming decoded WsMessage objects.
  Stream<WsMessage> get messages => _messageController.stream;

  /// Whether the socket is currently connected.
  bool get isConnected => _state == SocketConnectionState.connected && _channel != null;

  KoraSocketService({this.backendUrl = _defaultUrl});

  /// Connect to the backend. Call once at app startup.
  Future<void> start() async {
    _reconnectAttempts = 0;
    await _connect();
  }

  /// Manually force a reconnection attempt.
  Future<void> retry() async {
    _reconnectTimer?.cancel();
    _reconnectAttempts = 0;
    await _connect();
  }

  /// Send a typed message to the backend.
  bool send(WsMessage message) {
    if (!isConnected || _channel == null) {
      debugPrint('[KoraSocketService] Cannot send message: WebSocket is not connected (state: $_state)');
      _messageController.add(WsMessage(
        type: WsMessageType.error,
        sessionId: message.sessionId,
        payload: {
          'code': 'NOT_CONNECTED',
          'message': 'Cannot communicate with Kora backend. Connection is $_state at $backendUrl.',
        },
      ));
      return false;
    }
    try {
      _channel!.sink.add(message.toRawString());
      return true;
    } catch (e) {
      debugPrint('[KoraSocketService] send error: $e');
      return false;
    }
  }

  /// Dispose the service. Call on app shutdown.
  void dispose() {
    _heartbeatTimer?.cancel();
    _reconnectTimer?.cancel();
    _subscription?.cancel();
    _channel?.sink.close();
    _setState(SocketConnectionState.disconnected);
    _stateController.close();
    _messageController.close();
  }

  // ── Private ──────────────────────────────────────────────────────────────────

  void _setState(SocketConnectionState newState) {
    if (_state != newState) {
      _state = newState;
      if (!_stateController.isClosed) {
        _stateController.add(newState);
      }
    }
  }

  Future<void> _connect() async {
    _reconnectTimer?.cancel();
    _isReconnecting = false;
    _setState(SocketConnectionState.connecting);

    try {
      final uri = Uri.parse(backendUrl);
      _channel = WebSocketChannel.connect(uri);

      // Listen to incoming frames
      _subscription?.cancel();
      _subscription = _channel!.stream.listen(
        (data) {
          if (_state != SocketConnectionState.connected) {
            _reconnectAttempts = 0;
            _setState(SocketConnectionState.connected);
            _startHeartbeat();
          }
          _onMessage(data);
        },
        onError: _onError,
        onDone: _onDone,
        cancelOnError: false,
      );

      // On Web/Native, when connection establishes or first ping succeeds
      _reconnectAttempts = 0;
      _setState(SocketConnectionState.connected);
      _startHeartbeat();
    } catch (e) {
      debugPrint('[KoraSocketService] Connection failed: $e');
      _channel = null;
      _scheduleReconnect();
    }
  }

  void _onMessage(dynamic data) {
    if (data is! String) {
      _messageController.add(WsMessage(
        type: WsMessageType.error,
        sessionId: '',
        payload: {
          'code': 'INVALID_FRAME_TYPE',
          'message': 'Received non-string frame: ${data.runtimeType}',
        },
      ));
      return;
    }

    try {
      final msg = WsMessage.fromRawString(data);
      _messageController.add(msg);
    } catch (e) {
      debugPrint('[KoraSocketService] Malformed frame received: $e');
      final truncated = data.length > 250 ? '${data.substring(0, 250)}...' : data;
      _messageController.add(WsMessage(
        type: WsMessageType.error,
        sessionId: '',
        payload: {
          'code': 'MALFORMED_FRAME',
          'message': 'Failed to parse frame: $e',
          'raw_snippet': truncated,
        },
      ));
    }
  }

  void _onError(Object error) {
    debugPrint('[KoraSocketService] WebSocket error: $error');
    _channel = null;
    _heartbeatTimer?.cancel();
    _scheduleReconnect();
  }

  void _onDone() {
    debugPrint('[KoraSocketService] WebSocket stream closed.');
    _channel = null;
    _heartbeatTimer?.cancel();
    _scheduleReconnect();
  }

  void _startHeartbeat() {
    _heartbeatTimer?.cancel();
    _heartbeatTimer = Timer.periodic(const Duration(seconds: 30), (_) {
      if (isConnected) {
        send(WsMessage(
          type: WsMessageType.heartbeat,
          sessionId: const Uuid().v4(),
          payload: {},
        ));
      }
    });
  }

  void _scheduleReconnect() {
    if (_isReconnecting) return;
    _isReconnecting = true;

    if (_reconnectAttempts >= _maxReconnectAttempts) {
      debugPrint('[KoraSocketService] Max reconnect attempts reached. Setting state to error.');
      _setState(SocketConnectionState.error);
      _messageController.add(WsMessage(
        type: WsMessageType.error,
        sessionId: '',
        payload: {
          'code': 'CONNECTION_REFUSED',
          'message': 'Unable to connect to Kora backend at $backendUrl after $_maxReconnectAttempts attempts. Please ensure the backend server is running.',
        },
      ));
      _isReconnecting = false;
      return;
    }

    // Bounded exponential backoff: 1s, 2s, 4s, 8s, 16s
    final delaySeconds = (1 << _reconnectAttempts).clamp(1, 16);
    final delay = Duration(seconds: delaySeconds);
    _reconnectAttempts++;
    _setState(SocketConnectionState.disconnected);

    debugPrint('[KoraSocketService] Reconnecting in ${delay.inSeconds}s (attempt $_reconnectAttempts/$_maxReconnectAttempts)...');
    _reconnectTimer = Timer(delay, () async {
      _isReconnecting = false;
      await _connect();
    });
  }
}
