import 'dart:io' show Platform;
import 'package:flutter/foundation.dart' show kIsWeb;

/// Application Configuration for Kora Desktop & Web
class AppConfig {
  static const String fallbackHttpUrl = 'http://127.0.0.1:8765';
  static const String fallbackWsUrl = 'ws://127.0.0.1:8765/ws';

  static String get defaultHttpUrl {
    const fromEnv = String.fromEnvironment('KORA_API_URL', defaultValue: '');
    if (fromEnv.isNotEmpty) return fromEnv;
    if (!kIsWeb) {
      try {
        final platEnv = Platform.environment['KORA_API_URL'];
        if (platEnv != null && platEnv.trim().isNotEmpty) {
          return platEnv.trim();
        }
      } catch (_) {}
    }
    return fallbackHttpUrl;
  }

  static String get defaultWsUrl {
    const fromEnv = String.fromEnvironment('KORA_WS_URL', defaultValue: '');
    if (fromEnv.isNotEmpty) return fromEnv;
    if (!kIsWeb) {
      try {
        final platEnv = Platform.environment['KORA_WS_URL'];
        if (platEnv != null && platEnv.trim().isNotEmpty) {
          return platEnv.trim();
        }
      } catch (_) {}
    }
    return fallbackWsUrl;
  }

  final String httpBaseUrl;
  final String wsUrl;
  final Duration requestTimeout;

  const AppConfig({
    this.httpBaseUrl = fallbackHttpUrl,
    this.wsUrl = fallbackWsUrl,
    this.requestTimeout = const Duration(seconds: 30),
  });

  factory AppConfig.configured({
    String? httpBaseUrl,
    String? wsUrl,
    Duration requestTimeout = const Duration(seconds: 30),
  }) {
    return AppConfig(
      httpBaseUrl: httpBaseUrl ?? defaultHttpUrl,
      wsUrl: wsUrl ?? defaultWsUrl,
      requestTimeout: requestTimeout,
    );
  }

  AppConfig copyWith({
    String? httpBaseUrl,
    String? wsUrl,
    Duration? requestTimeout,
  }) {
    return AppConfig(
      httpBaseUrl: httpBaseUrl ?? this.httpBaseUrl,
      wsUrl: wsUrl ?? this.wsUrl,
      requestTimeout: requestTimeout ?? this.requestTimeout,
    );
  }
}
