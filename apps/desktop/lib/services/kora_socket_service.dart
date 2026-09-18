import 'dart:async';
import 'dart:convert';

import 'package:uuid/uuid.dart';
import 'package:web_socket_channel/web_socket_channel.dart';

import '../shared/protocol/ws_message.dart';
import '../shared/protocol/message_types.dart';

/// KoraSocketService
///
/// Manages the persistent WebSocket connection to the Kora agent backend.
///
/// Responsibilities:
///   - Connect and reconnect with exponential backoff
///   - Send typed WsMessage frames
///   - Expose an incoming message stream for consumers (Riverpod providers)
///   - Heartbeat keep-alive (30-second interval)
///   - Lifecycle: start() / dispose()
class KoraSocketService {
  static const String _defaultUrl = 'ws://127.0.0.1:8765/ws';

  final String backendUrl;
  WebSocketChannel? _channel;
  StreamSubscription? _subscription;
  Timer? _heartbeatTimer;
  Timer? _reconnectTimer;

  int _reconnectAttempts = 0;
  static const int _maxReconnectAttempts = 10;
  static const Duration _baseReconnectDelay = Duration(seconds: 1);

  final _messageController = StreamController<WsMessage>.broadcast();

  /// Stream of incoming decoded WsMessage objects.
  Stream<WsMessage> get messages => _messageController.stream;

  /// Whether the socket is currently connected.
  bool get isConnected => _channel != null;

  KoraSocketService({this.backendUrl = _defaultUrl});

  /// Connect to the backend. Call once at app startup.
  Future<void> start() async {
    await _connect();
  }

  /// Send a typed message to the backend.
  void send(WsMessage message) {
    _channel?.sink.add(message.toRawString());
  }

  /// Dispose the service. Call on app shutdown.
  void dispose() {
    _heartbeatTimer?.cancel();
    _reconnectTimer?.cancel();
    _subscription?.cancel();
    _channel?.sink.close();
    _messageController.close();
  }

  // ── Private ──────────────────────────────────────────────────────────────────

  Future<void> _connect() async {
    try {
      _channel = WebSocketChannel.connect(Uri.parse(backendUrl));
      _reconnectAttempts = 0;

      _subscription = _channel!.stream.listen(
        _onMessage,
        onError: _onError,
        onDone: _onDone,
        cancelOnError: false,
      );

      _startHeartbeat();
    } catch (e) {
      _scheduleReconnect();
    }
  }

  void _onMessage(dynamic data) {
    try {
      final msg = WsMessage.fromRawString(data as String);
      _messageController.add(msg);
    } catch (_) {
      // Malformed message — ignore
    }
  }

  void _onError(Object error) {
    _channel = null;
    _heartbeatTimer?.cancel();
    _scheduleReconnect();
  }

  void _onDone() {
    _channel = null;
    _heartbeatTimer?.cancel();
    _scheduleReconnect();
  }

  void _startHeartbeat() {
    _heartbeatTimer?.cancel();
    _heartbeatTimer = Timer.periodic(const Duration(seconds: 30), (_) {
      send(WsMessage(
        type: WsMessageType.heartbeat,
        sessionId: const Uuid().v4(),
        payload: {},
      ));
    });
  }

  void _scheduleReconnect() {
    if (_reconnectAttempts >= _maxReconnectAttempts) return;
    final delay = _baseReconnectDelay * (1 << _reconnectAttempts).clamp(1, 32);
    _reconnectAttempts++;
    _reconnectTimer = Timer(delay, _connect);
  }
}
