import 'dart:convert';
import 'package:flutter_test/flutter_test.dart';
import 'package:kora_desktop/models/chat_message.dart';
import 'package:kora_desktop/services/kora_socket_service.dart';
import 'package:kora_desktop/shared/protocol/message_types.dart';
import 'package:kora_desktop/shared/protocol/ws_message.dart';
import 'package:kora_desktop/state/chat_state.dart';

void main() {
  group('WebSocket Protocol Tests', () {
    test('WsMessageType serialization and deserialization', () {
      expect(WsMessageType.fromString('CHAT_REQUEST'), WsMessageType.chatRequest);
      expect(WsMessageType.fromString('CHAT_CHUNK'), WsMessageType.chatChunk);
      expect(WsMessageType.fromString('CHAT_DONE'), WsMessageType.chatDone);
      expect(WsMessageType.fromString('CHAT_CANCEL'), WsMessageType.chatCancel);
      expect(WsMessageType.fromString('PLAN_UPDATE'), WsMessageType.planUpdate);
      expect(WsMessageType.fromString('TOOL_CALL_NOTIFY'), WsMessageType.toolCallNotify);
      expect(WsMessageType.fromString('TOOL_RESULT_NOTIFY'), WsMessageType.toolResultNotify);

      expect(WsMessageType.chatRequest.toApiString(), 'CHAT_REQUEST');
      expect(WsMessageType.chatChunk.toApiString(), 'CHAT_CHUNK');
      expect(WsMessageType.chatDone.toApiString(), 'CHAT_DONE');
      expect(WsMessageType.chatCancel.toApiString(), 'CHAT_CANCEL');
    });

    test('WsMessage roundtrip JSON encode/decode', () {
      final msg = WsMessage(
        type: WsMessageType.chatRequest,
        sessionId: 'test-session-123',
        projectId: 'proj-456',
        payload: {
          'message': 'Hello Kora',
          'attachments': ['file1.txt'],
        },
      );

      final raw = msg.toRawString();
      final decoded = WsMessage.fromRawString(raw);

      expect(decoded.type, WsMessageType.chatRequest);
      expect(decoded.sessionId, 'test-session-123');
      expect(decoded.projectId, 'proj-456');
      expect(decoded.payload['message'], 'Hello Kora');
      expect(decoded.payload['attachments'], ['file1.txt']);
    });

    test('Parses backend PLAN_UPDATE without id, session_id, ts', () {
      const raw = '{"type": "PLAN_UPDATE", "payload": {"steps": [{"index": 0, "label": "Generate grounded response", "status": "pending"}]}}';
      final msg = WsMessage.fromRawString(raw);
      expect(msg.type, WsMessageType.planUpdate);
      expect(msg.payload['steps'], isNotEmpty);
      expect(msg.id, isNotEmpty);
    });

    test('Parses backend CHAT_CHUNK without id, session_id, ts', () {
      const raw = '{"type": "CHAT_CHUNK", "payload": {"chunk": "Hello, world!"}}';
      final msg = WsMessage.fromRawString(raw);
      expect(msg.type, WsMessageType.chatChunk);
      expect(msg.payload['chunk'], 'Hello, world!');
      expect(msg.id, isNotEmpty);
    });

    test('Parses backend CHAT_DONE without id or ts', () {
      const raw = '{"type": "CHAT_DONE", "session_id": "sess-1", "payload": {"full_text": "Complete response", "input_tokens": 10, "output_tokens": 20}}';
      final msg = WsMessage.fromRawString(raw);
      expect(msg.type, WsMessageType.chatDone);
      expect(msg.sessionId, 'sess-1');
      expect(msg.payload['full_text'], 'Complete response');
    });

    test('Parses backend ERROR without id, session_id, ts', () {
      const raw = '{"type": "ERROR", "payload": {"code": "CHAT_ERROR", "message": "Inference failure"}}';
      final msg = WsMessage.fromRawString(raw);
      expect(msg.type, WsMessageType.error);
      expect(msg.payload['code'], 'CHAT_ERROR');
      expect(msg.payload['message'], 'Inference failure');
    });

    test('Handles malformed JSON safely via error WsMessage', () {
      expect(() => WsMessage.fromRawString('not-json'), throwsFormatException);
    });

    test('Handles unknown event type by defaulting to error', () {
      const raw = '{"type": "UNKNOWN_FUTURE_EVENT", "payload": {}}';
      final msg = WsMessage.fromRawString(raw);
      expect(msg.type, WsMessageType.error);
    });
  });
}
