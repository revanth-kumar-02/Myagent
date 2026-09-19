// Dart Data Models for Kora Observability & Agent Replay (V14)

class TraceItem {
  final String traceId;
  final String? taskId;
  final String? sessionId;
  final String? projectId;
  final String state;
  final String? model;
  final int durationMs;
  final String finalStatus;
  final String verificationResult;
  final String? error;
  final DateTime createdAt;
  final List<EventItem> events;
  final List<ErrorItem> errors;

  const TraceItem({
    required this.traceId,
    this.taskId,
    this.sessionId,
    this.projectId,
    required this.state,
    this.model,
    required this.durationMs,
    required this.finalStatus,
    required this.verificationResult,
    this.error,
    required this.createdAt,
    this.events = const [],
    this.errors = const [],
  });

  factory TraceItem.fromJson(Map<String, dynamic> json) {
    return TraceItem(
      traceId: json['trace_id'] as String? ?? '',
      taskId: json['task_id'] as String?,
      sessionId: json['session_id'] as String?,
      projectId: json['project_id'] as String?,
      state: json['state'] as String? ?? 'idle',
      model: json['model'] as String?,
      durationMs: json['duration_ms'] as int? ?? 0,
      finalStatus: json['final_status'] as String? ?? 'success',
      verificationResult: json['verification_result'] as String? ?? 'pass',
      error: json['error'] as String?,
      createdAt: json['created_at'] != null
          ? DateTime.tryParse(json['created_at'] as String) ?? DateTime.now()
          : DateTime.now(),
      events: (json['events'] as List<dynamic>?)
              ?.map((e) => EventItem.fromJson(e as Map<String, dynamic>))
              .toList() ??
          const [],
      errors: (json['errors'] as List<dynamic>?)
              ?.map((e) => ErrorItem.fromJson(e as Map<String, dynamic>))
              .toList() ??
          const [],
    );
  }
}

class EventItem {
  final String eventId;
  final String eventType;
  final String component;
  final String status;
  final int durationMs;
  final Map<String, dynamic> payload;
  final DateTime timestamp;

  const EventItem({
    required this.eventId,
    required this.eventType,
    required this.component,
    required this.status,
    required this.durationMs,
    required this.payload,
    required this.timestamp,
  });

  factory EventItem.fromJson(Map<String, dynamic> json) {
    return EventItem(
      eventId: json['event_id'] as String? ?? '',
      eventType: json['event_type'] as String? ?? '',
      component: json['component'] as String? ?? '',
      status: json['status'] as String? ?? 'info',
      durationMs: json['duration_ms'] as int? ?? 0,
      payload: (json['payload'] as Map<String, dynamic>?) ?? {},
      timestamp: json['timestamp'] != null
          ? DateTime.tryParse(json['timestamp'] as String) ?? DateTime.now()
          : DateTime.now(),
    );
  }
}

class ErrorItem {
  final String errorCode;
  final String component;
  final String message;
  final String severity;
  final DateTime timestamp;

  const ErrorItem({
    required this.errorCode,
    required this.component,
    required this.message,
    required this.severity,
    required this.timestamp,
  });

  factory ErrorItem.fromJson(Map<String, dynamic> json) {
    return ErrorItem(
      errorCode: json['error_code'] as String? ?? '',
      component: json['component'] as String? ?? '',
      message: json['message'] as String? ?? '',
      severity: json['severity'] as String? ?? 'error',
      timestamp: json['timestamp'] != null
          ? DateTime.tryParse(json['timestamp'] as String) ?? DateTime.now()
          : DateTime.now(),
    );
  }
}

class ComponentHealthItem {
  final String component;
  final String status; // 'healthy', 'degraded', 'unhealthy'
  final int latencyMs;
  final String message;

  const ComponentHealthItem({
    required this.component,
    required this.status,
    required this.latencyMs,
    required this.message,
  });

  factory ComponentHealthItem.fromJson(Map<String, dynamic> json) {
    return ComponentHealthItem(
      component: json['component'] as String? ?? '',
      status: json['status'] as String? ?? 'healthy',
      latencyMs: json['latency_ms'] as int? ?? 0,
      message: json['message'] as String? ?? 'OK',
    );
  }
}
