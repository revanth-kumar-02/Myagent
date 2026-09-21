import 'dart:convert';
import 'package:uuid/uuid.dart';
import 'message_types.dart';

// ── WsMessage Envelope ───────────────────────────────────────────────────────

class WsMessage {
  final String id;
  final WsMessageType type;
  final String sessionId;
  final String? projectId;
  final Map<String, dynamic> payload;
  final int ts;

  WsMessage({
    String? id,
    required this.type,
    required this.sessionId,
    this.projectId,
    required this.payload,
    int? ts,
  })  : id = id ?? const Uuid().v4(),
        ts = ts ?? DateTime.now().millisecondsSinceEpoch;

  factory WsMessage.fromJson(Map<String, dynamic> json) {
    final typeStr = json['type'] as String? ?? 'ERROR';
    final payloadRaw = json['payload'];
    final Map<String, dynamic> payload = payloadRaw is Map<String, dynamic>
        ? payloadRaw
        : (payloadRaw is Map ? Map<String, dynamic>.from(payloadRaw) : {});

    final int timestamp = (json['ts'] is num)
        ? (json['ts'] as num).toInt()
        : DateTime.now().millisecondsSinceEpoch;

    return WsMessage(
      id: json['id']?.toString() ?? const Uuid().v4(),
      type: WsMessageType.fromString(typeStr),
      sessionId: json['session_id']?.toString() ?? '',
      projectId: json['project_id']?.toString(),
      payload: payload,
      ts: timestamp,
    );
  }

  factory WsMessage.fromRawString(String raw) {
    final decoded = jsonDecode(raw);
    if (decoded is Map<String, dynamic>) {
      return WsMessage.fromJson(decoded);
    } else if (decoded is Map) {
      return WsMessage.fromJson(Map<String, dynamic>.from(decoded));
    }
    throw FormatException('WebSocket message is not a JSON object: $raw');
  }

  Map<String, dynamic> toJson() => {
        'id': id,
        'type': type.toApiString(),
        'session_id': sessionId,
        'project_id': projectId,
        'payload': payload,
        'ts': ts,
      };

  String toRawString() => jsonEncode(toJson());
}

// ── Typed payload helpers ─────────────────────────────────────────────────────

class ChatRequestPayload {
  final String message;
  final List<String> attachments;

  const ChatRequestPayload({required this.message, this.attachments = const []});

  Map<String, dynamic> toJson() => {'message': message, 'attachments': attachments};
}

class IndexRequestPayload {
  final String projectId;
  final String rootPath;
  final bool incremental;

  const IndexRequestPayload({
    required this.projectId,
    required this.rootPath,
    this.incremental = true,
  });

  Map<String, dynamic> toJson() => {
        'project_id': projectId,
        'root_path': rootPath,
        'incremental': incremental,
      };
}
