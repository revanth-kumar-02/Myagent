// Kora Desktop — WebSocket message types (mirrors shared/protocol/schema.json)
// This file is the single source of truth for message types in Dart.

// ── Message Type Enum ────────────────────────────────────────────────────────

enum WsMessageType {
  chatRequest,
  chatChunk,
  chatDone,
  planUpdate,
  toolCallNotify,
  toolResultNotify,
  permissionRequest,
  permissionResponse,
  indexRequest,
  indexProgress,
  indexDone,
  indexError,
  heartbeat,
  error;

  static WsMessageType fromString(String s) {
    return switch (s) {
      'CHAT_REQUEST'        => chatRequest,
      'CHAT_CHUNK'          => chatChunk,
      'CHAT_DONE'           => chatDone,
      'PLAN_UPDATE'         => planUpdate,
      'TOOL_CALL_NOTIFY'    => toolCallNotify,
      'TOOL_RESULT_NOTIFY'  => toolResultNotify,
      'PERMISSION_REQUEST'  => permissionRequest,
      'PERMISSION_RESPONSE' => permissionResponse,
      'INDEX_REQUEST'       => indexRequest,
      'INDEX_PROGRESS'      => indexProgress,
      'INDEX_DONE'          => indexDone,
      'INDEX_ERROR'         => indexError,
      'HEARTBEAT'           => heartbeat,
      'ERROR'               => error,
      _                     => throw ArgumentError('Unknown WS message type: $s'),
    };
  }

  String toApiString() {
    return switch (this) {
      WsMessageType.chatRequest        => 'CHAT_REQUEST',
      WsMessageType.chatChunk          => 'CHAT_CHUNK',
      WsMessageType.chatDone           => 'CHAT_DONE',
      WsMessageType.planUpdate         => 'PLAN_UPDATE',
      WsMessageType.toolCallNotify     => 'TOOL_CALL_NOTIFY',
      WsMessageType.toolResultNotify   => 'TOOL_RESULT_NOTIFY',
      WsMessageType.permissionRequest  => 'PERMISSION_REQUEST',
      WsMessageType.permissionResponse => 'PERMISSION_RESPONSE',
      WsMessageType.indexRequest       => 'INDEX_REQUEST',
      WsMessageType.indexProgress      => 'INDEX_PROGRESS',
      WsMessageType.indexDone          => 'INDEX_DONE',
      WsMessageType.indexError         => 'INDEX_ERROR',
      WsMessageType.heartbeat          => 'HEARTBEAT',
      WsMessageType.error              => 'ERROR',
    };
  }
}
