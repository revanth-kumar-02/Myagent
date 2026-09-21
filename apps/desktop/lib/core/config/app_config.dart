/// Application Configuration for Kora Desktop
class AppConfig {
  static const String defaultHttpUrl = 'http://127.0.0.1:8765';
  static const String defaultWsUrl = 'ws://127.0.0.1:8765/ws';

  final String httpBaseUrl;
  final String wsUrl;
  final Duration requestTimeout;

  const AppConfig({
    this.httpBaseUrl = defaultHttpUrl,
    this.wsUrl = defaultWsUrl,
    this.requestTimeout = const Duration(seconds: 30),
  });

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
