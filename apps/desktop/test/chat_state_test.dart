import 'package:flutter_test/flutter_test.dart';
import 'package:kora_desktop/models/chat_message.dart';
import 'package:kora_desktop/models/plan_step.dart';
import 'package:kora_desktop/services/kora_socket_service.dart';
import 'package:kora_desktop/services/ollama_direct_service.dart';
import 'package:kora_desktop/shared/protocol/message_types.dart';
import 'package:kora_desktop/shared/protocol/ws_message.dart';
import 'package:kora_desktop/state/chat_state.dart';

class MockSocketService extends KoraSocketService {
  final List<WsMessage> sentMessages = [];

  @override
  SocketConnectionState get state => SocketConnectionState.connected;

  @override
  bool send(WsMessage message) {
    sentMessages.add(message);
    return true;
  }
}

class MockOllamaService extends OllamaDirectService {
  final bool available;
  final List<String> chunks;

  MockOllamaService({
    this.available = false,
    this.chunks = const ['Hello', ' from local Ollama'],
  });

  @override
  Future<bool> isAvailable() async => available;

  @override
  Stream<String> streamChat({
    required List<ChatMessage> history,
    required String prompt,
    String? modelOverride,
  }) async* {
    for (final c in chunks) {
      yield c;
    }
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
    });

    test('CHAT_DONE appends content and clears isStreaming', () async {
      final socket = MockSocketService();
      final notifier = ChatNotifier(socket);

      await notifier.sendMessage('Test prompt');
      expect(notifier.state.isStreaming, isTrue);

      final doneMsg = WsMessage.fromRawString(
        '{"type": "CHAT_DONE", "payload": {"full_text": "Final answer", "model_used": "qwen-chat"}}',
      );
      notifier.testHandleMessage(doneMsg);

      expect(notifier.state.isStreaming, isFalse);
      expect(notifier.state.messages.last.content, 'Final answer');
      expect(notifier.state.messages.last.status, MessageStatus.done);
    });

    test('ERROR updates message and clears isStreaming', () async {
      final socket = MockSocketService();
      final notifier = ChatNotifier(socket);

      await notifier.sendMessage('Test prompt');
      expect(notifier.state.isStreaming, isTrue);

      final errorMsg = WsMessage.fromRawString(
        '{"type": "ERROR", "payload": {"code": "CHAT_ERROR", "message": "Credit limit reached"}}',
      );
      notifier.testHandleMessage(errorMsg);

      expect(notifier.state.isStreaming, isFalse);
      expect(notifier.state.messages.last.status, MessageStatus.error);
      expect(notifier.state.messages.last.errorMessage, 'Credit limit reached');
    });

    test('Clears streaming state on socket disconnect when Ollama is also unavailable', () async {
      final socket = KoraSocketService();
      final notifier = ChatNotifier(socket, MockOllamaService(available: false));

      // Sockets start disconnected, so sendMessage immediately detects disconnected state and clears streaming
      await notifier.sendMessage('Prompt while disconnected');
      expect(notifier.state.isStreaming, isFalse);
      expect(notifier.state.messages.last.status, MessageStatus.error);
      expect(notifier.state.messages.last.errorMessage, contains('disconnected'));
    });

    test('Falls back directly to local Ollama when socket is disconnected', () async {
      final socket = KoraSocketService();
      final notifier = ChatNotifier(
        socket,
        MockOllamaService(available: true, chunks: ['Hello', ' from Ollama!']),
      );

      await notifier.sendMessage('Direct prompt');
      // Allow async generator stream to flush
      await Future<void>.delayed(const Duration(milliseconds: 10));
      expect(notifier.state.messages.length, 2);
      expect(notifier.state.messages.last.content, 'Hello from Ollama!');
      expect(notifier.state.messages.last.status, MessageStatus.done);
      expect(notifier.state.isStreaming, isFalse);
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
