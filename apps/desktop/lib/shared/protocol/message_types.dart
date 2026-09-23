// Kora Desktop — WebSocket message types (mirrors shared/protocol/schema.json)
// This file is the single source of truth for message types in Dart.

enum WsMessageType {
  chatRequest,
  chatChunk,
  chatDone,
  chatCancel,
  chatCancelled,
  planCreated,
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
  providerStatus,
  error;

  static WsMessageType fromString(String s) {
    return switch (s) {
      'CHAT_REQUEST'        => chatRequest,
      'CHAT_CHUNK'          => chatChunk,
      'CHAT_DONE'           => chatDone,
      'CHAT_CANCEL'         => chatCancel,
      'CANCEL_REQUEST'      => chatCancel,
      'CHAT_CANCELLED'      => chatCancelled,
      'PLAN_CREATED'        => planCreated,
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
      'PROVIDER_STATUS'     => providerStatus,
      'ERROR'               => error,
      _                     => error,
    };
  }

  String toApiString() {
    return switch (this) {
      WsMessageType.chatRequest        => 'CHAT_REQUEST',
      WsMessageType.chatChunk          => 'CHAT_CHUNK',
      WsMessageType.chatDone           => 'CHAT_DONE',
      WsMessageType.chatCancel         => 'CHAT_CANCEL',
      WsMessageType.chatCancelled      => 'CHAT_CANCELLED',
      WsMessageType.planCreated        => 'PLAN_CREATED',
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
      WsMessageType.providerStatus     => 'PROVIDER_STATUS',
      WsMessageType.error              => 'ERROR',
    };
  }
}
