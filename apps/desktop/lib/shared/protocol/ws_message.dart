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
    return WsMessage(
      id: json['id'] as String,
      type: WsMessageType.fromString(json['type'] as String),
      sessionId: json['session_id'] as String,
      projectId: json['project_id'] as String?,
      payload: json['payload'] as Map<String, dynamic>? ?? {},
      ts: json['ts'] as int,
    );
  }

  factory WsMessage.fromRawString(String raw) {
    return WsMessage.fromJson(jsonDecode(raw) as Map<String, dynamic>);
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
