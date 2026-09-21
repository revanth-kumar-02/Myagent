import 'package:flutter_test/flutter_test.dart';
import 'package:kora_desktop/models/chat_message.dart';
import 'package:kora_desktop/models/plan_step.dart';
import 'package:kora_desktop/services/kora_socket_service.dart';
import 'package:kora_desktop/shared/protocol/message_types.dart';
import 'package:kora_desktop/shared/protocol/ws_message.dart';
import 'package:kora_desktop/state/chat_state.dart';

class MockSocketService extends KoraSocketService {
  final List<WsMessage> sentMessages = [];

  @override
  void send(WsMessage message) {
    sentMessages.add(message);
  }

  void emitMessage(WsMessage message) {
    // Invoke handler directly through public or test method
  }
}

void main() {
  group('ChatNotifier State Tests', () {
    test('Initial state is empty and ready', () {
      final socket = MockSocketService();
      final notifier = ChatNotifier(socket);

      expect(notifier.state.messages, isEmpty);
      expect(notifier.state.isStreaming, isFalse);
      expect(notifier.state.activePlanSteps, isEmpty);
      expect(notifier.state.activeTool, isNull);
    });

    test('sendMessage creates user and streaming assistant message', () async {
      final socket = MockSocketService();
      final notifier = ChatNotifier(socket);

      await notifier.sendMessage('What is Kora?');

      expect(notifier.state.messages.length, 2);
      expect(notifier.state.messages[0].role, MessageRole.user);
      expect(notifier.state.messages[0].content, 'What is Kora?');

      expect(notifier.state.messages[1].role, MessageRole.assistant);
      expect(notifier.state.messages[1].status, MessageStatus.streaming);
      expect(notifier.state.isStreaming, isTrue);

      expect(socket.sentMessages.length, 1);
      expect(socket.sentMessages[0].type, WsMessageType.chatRequest);
      expect(socket.sentMessages[0].payload['message'], 'What is Kora?');
    });

    test('cancelGeneration marks message cancelled', () async {
      final socket = MockSocketService();
      final notifier = ChatNotifier(socket);

      await notifier.sendMessage('Long task query');
      notifier.cancelGeneration();

      expect(notifier.state.isStreaming, isFalse);
      expect(notifier.state.messages.last.status, MessageStatus.cancelled);
      expect(socket.sentMessages.any((m) => m.type == WsMessageType.chatCancel), isTrue);
    });

    test('clearMessages resets conversation history', () async {
      final socket = MockSocketService();
      final notifier = ChatNotifier(socket);

      await notifier.sendMessage('Hello');
      expect(notifier.state.messages.isNotEmpty, isTrue);

      notifier.clearMessages();
      expect(notifier.state.messages, isEmpty);
      expect(notifier.state.isStreaming, isFalse);
    });
  });
}
