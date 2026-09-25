import 'dart:async';
import 'dart:io' show Platform;
import 'package:flutter/foundation.dart';
import 'package:http/http.dart' as http;

import '../../core/config/app_config.dart';
import '../../shared/protocol/message_types.dart';
import '../kora_socket_service.dart';
import 'local_runtime_manager.dart';

/// Standard Provider Runtime Modes
enum KoraRuntimeMode {
  onlineCloud,
  offlineLocal,
  connecting,
  degraded,
  noProvider,
}

class KoraRuntimeStatus {
  final KoraRuntimeMode mode;
  final String provider; // huggingface, ollama, none
  final String? model; // qwen3:1.7b, qwen-chat
  final bool isLocalFallback;
  final String activeApiUrl;
  final String activeWsUrl;

  const KoraRuntimeStatus({
    this.mode = KoraRuntimeMode.connecting,
    this.provider = 'none',
    this.model,
    this.isLocalFallback = false,
    this.activeApiUrl = AppConfig.fallbackHttpUrl,
    this.activeWsUrl = AppConfig.fallbackWsUrl,
  });

  String get displayStatusText {
    switch (mode) {
      case KoraRuntimeMode.connecting:
        return 'Connecting...';
      case KoraRuntimeMode.onlineCloud:
        return 'Online · Cloud AI';
      case KoraRuntimeMode.offlineLocal:
        return 'Online · Local AI';
      case KoraRuntimeMode.degraded:
        return 'Degraded · Local Fallback';
      case KoraRuntimeMode.noProvider:
        return 'AI unavailable';
    }
  }

  KoraRuntimeStatus copyWith({
    KoraRuntimeMode? mode,
    String? provider,
    String? model,
    bool? isLocalFallback,
    String? activeApiUrl,
    String? activeWsUrl,
  }) {
    return KoraRuntimeStatus(
      mode: mode ?? this.mode,
      provider: provider ?? this.provider,
      model: model ?? this.model,
      isLocalFallback: isLocalFallback ?? this.isLocalFallback,
      activeApiUrl: activeApiUrl ?? this.activeApiUrl,
      activeWsUrl: activeWsUrl ?? this.activeWsUrl,
    );
  }
}

/// KoraRuntimeManager
///
/// Orchestrates runtime mode detection, automatic failover between
/// Remote Hosted Kora and Desktop Local Kora runtime, and background recovery.
class KoraRuntimeManager {
  final AppConfig config;
  final KoraSocketService socketService;
  final LocalRuntimeManager localRuntime = LocalRuntimeManager.instance;

  KoraRuntimeStatus _status = const KoraRuntimeStatus();
  final _statusController = StreamController<KoraRuntimeStatus>.broadcast();
  Timer? _recoveryTimer;
  StreamSubscription? _socketMsgSub;

  KoraRuntimeStatus get status => _status;
  Stream<KoraRuntimeStatus> get statusStream => _statusController.stream;

  KoraRuntimeManager({
    AppConfig? config,
    required this.socketService,
  }) : config = config ?? AppConfig() {
    _initSocketListener();
  }

  void _setStatus(KoraRuntimeStatus newStatus) {
    _status = newStatus;
    debugPrint('[KoraRuntimeManager] Status update: ${_status.displayStatusText} (provider: ${_status.provider})');
    if (!_statusController.isClosed) {
      _statusController.add(_status);
    }
  }

  void _initSocketListener() {
    _socketMsgSub = socketService.messages.listen((msg) {
      if (msg.type == WsMessageType.providerStatus) {
        final modeStr = msg.payload['mode'] as String?;
        final provider = msg.payload['provider'] as String? ?? 'none';
        final model = msg.payload['model'] as String?;
        final localFallback = (msg.payload['local_fallback'] as bool?) ?? false;

        KoraRuntimeMode mode = KoraRuntimeMode.connecting;
        if (modeStr == 'online' && !localFallback) {
          mode = KoraRuntimeMode.onlineCloud;
        } else if (modeStr == 'offline' || localFallback) {
          mode = KoraRuntimeMode.offlineLocal;
        } else if (modeStr == 'no_provider' || provider == 'none') {
          mode = KoraRuntimeMode.noProvider;
        } else if (modeStr == 'online_degraded') {
          mode = KoraRuntimeMode.degraded;
        }

        _setStatus(_status.copyWith(
          mode: mode,
          provider: provider,
          model: model,
          isLocalFallback: localFallback,
        ));
      }
    });
  }

  /// Initialize and start runtime resolution.
  Future<void> initialize() async {
    _setStatus(_status.copyWith(mode: KoraRuntimeMode.connecting));

    // 1. Probe Remote Hosted Backend if configured differently from localhost
    final remoteApiUrl = config.httpBaseUrl;
    final isRemoteConfigured = remoteApiUrl.isNotEmpty && !remoteApiUrl.contains('127.0.0.1') && !remoteApiUrl.contains('localhost');

    if (isRemoteConfigured) {
      debugPrint('[KoraRuntimeManager] Probing remote hosted backend at $remoteApiUrl...');
      final remoteAvailable = await _probeUrl('$remoteApiUrl/api/health');
      if (remoteAvailable) {
        debugPrint('[KoraRuntimeManager] Remote hosted backend is ONLINE!');
        _setStatus(_status.copyWith(
          mode: KoraRuntimeMode.onlineCloud,
          provider: 'huggingface',
          model: 'qwen-chat',
          isLocalFallback: false,
          activeApiUrl: remoteApiUrl,
          activeWsUrl: config.wsUrl,
        ));
        _startRecoveryMonitor();
        return;
      }
      debugPrint('[KoraRuntimeManager] Remote hosted backend unreachable. Switching to offline mode...');
    }

    // 2. Local Kora Backend mode
    if (!kIsWeb) {
      // On Desktop: ensure local runtime is available
      debugPrint('[KoraRuntimeManager] Ensuring local Kora desktop runtime is active...');
      final localStarted = await localRuntime.ensureStarted(baseUrl: AppConfig.fallbackHttpUrl);
      if (localStarted) {
        // If we haven't received a more specific status from WebSocket yet, set local backend online
        if (_status.provider == 'none' || _status.mode == KoraRuntimeMode.connecting) {
          _setStatus(_status.copyWith(
            mode: KoraRuntimeMode.onlineCloud,
            provider: 'huggingface',
            model: 'qwen-chat',
            isLocalFallback: false,
            activeApiUrl: AppConfig.fallbackHttpUrl,
            activeWsUrl: AppConfig.fallbackWsUrl,
          ));
        } else {
          _setStatus(_status.copyWith(
            activeApiUrl: AppConfig.fallbackHttpUrl,
            activeWsUrl: AppConfig.fallbackWsUrl,
          ));
        }
        _startRecoveryMonitor();
        return;
      }
    }

    // Check if local backend port is responding
    final localDirect = await _probeUrl('${AppConfig.fallbackHttpUrl}/api/health');
    if (localDirect) {
      if (_status.provider == 'none' || _status.mode == KoraRuntimeMode.connecting) {
        _setStatus(_status.copyWith(
          mode: KoraRuntimeMode.onlineCloud,
          provider: 'huggingface',
          model: 'qwen-chat',
          isLocalFallback: false,
          activeApiUrl: AppConfig.fallbackHttpUrl,
          activeWsUrl: AppConfig.fallbackWsUrl,
        ));
      } else {
        _setStatus(_status.copyWith(
          activeApiUrl: AppConfig.fallbackHttpUrl,
          activeWsUrl: AppConfig.fallbackWsUrl,
        ));
      }
      _startRecoveryMonitor();
      return;
    }

    // Check if Ollama daemon alone is running (Web or Desktop)
    final ollamaUp = await localRuntime.probeOllama();
    if (ollamaUp) {
      _setStatus(_status.copyWith(
        mode: KoraRuntimeMode.offlineLocal,
        provider: 'ollama',
        model: 'qwen3:1.7b',
        isLocalFallback: true,
      ));
      _startRecoveryMonitor();
      return;
    }

    // Neither remote nor local runtime could be verified
    _setStatus(_status.copyWith(
      mode: KoraRuntimeMode.noProvider,
      provider: 'none',
      model: null,
      isLocalFallback: false,
    ));

    _startRecoveryMonitor();
  }

  void _startRecoveryMonitor() {
    if (Platform.environment.containsKey('FLUTTER_TEST')) return;
    _recoveryTimer?.cancel();
    _recoveryTimer = Timer.periodic(const Duration(seconds: 15), (_) async {
      final remoteApiUrl = config.httpBaseUrl;
      final isRemoteConfigured = remoteApiUrl.isNotEmpty && !remoteApiUrl.contains('127.0.0.1') && !remoteApiUrl.contains('localhost');

      if (isRemoteConfigured) {
        final remoteUp = await _probeUrl('$remoteApiUrl/api/health');
        if (remoteUp && _status.mode != KoraRuntimeMode.onlineCloud) {
          debugPrint('[KoraRuntimeManager] Remote cloud backend has recovered! Switching back to ONLINE_CLOUD.');
          _setStatus(_status.copyWith(
            mode: KoraRuntimeMode.onlineCloud,
            provider: 'huggingface',
            model: 'qwen-chat',
            isLocalFallback: false,
            activeApiUrl: remoteApiUrl,
            activeWsUrl: config.wsUrl,
          ));
        }
      }
    });
  }

  Future<bool> _probeUrl(String url) async {
    try {
      final res = await http.get(Uri.parse(url)).timeout(const Duration(seconds: 2));
      return res.statusCode == 200;
    } catch (_) {
      return false;
    }
  }

  void dispose() {
    _recoveryTimer?.cancel();
    _socketMsgSub?.cancel();
    _statusController.close();
  }
}
