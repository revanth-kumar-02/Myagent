import 'package:flutter_test/flutter_test.dart';
import 'package:kora_desktop/shared/protocol/message_types.dart';
import 'package:kora_desktop/shared/protocol/ws_message.dart';

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
  });
}
