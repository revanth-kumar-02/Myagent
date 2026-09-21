/// Activity log model for observability

class ActivityLog {
  final String id;
  final String eventType;
  final String details;
  final int latencyMs;
  final String timestamp;

  const ActivityLog({
    required this.id,
    required this.eventType,
    required this.details,
    this.latencyMs = 0,
    required this.timestamp,
  });

  factory ActivityLog.fromJson(Map<String, dynamic> json) {
    return ActivityLog(
      id: json['id'] as String? ?? '',
      eventType: json['event_type'] as String? ?? 'EVENT',
      details: json['details'] as String? ?? '',
      latencyMs: json['latency_ms'] as int? ?? 0,
      timestamp: json['timestamp'] as String? ?? '',
    );
  }

  Map<String, dynamic> toJson() => {
    'id': id,
    'event_type': eventType,
    'details': details,
    'latency_ms': latencyMs,
    'timestamp': timestamp,
  };
}
