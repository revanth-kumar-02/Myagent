import 'dart:async';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:uuid/uuid.dart';

import '../models/chat_message.dart';
import '../models/citation.dart';
import '../models/plan_step.dart';
import '../services/kora_socket_service.dart';
import '../shared/protocol/message_types.dart';
import '../shared/protocol/ws_message.dart';
import 'connection_state.dart';

class ChatState {
  final List<ChatMessage> messages;
  final bool isStreaming;
  final String sessionId;
  final String? selectedProjectId;
  final String? activeTool;
  final List<PlanStep> activePlanSteps;

  const ChatState({
    this.messages = const [],
    this.isStreaming = false,
    required this.sessionId,
    this.selectedProjectId,
    this.activeTool,
    this.activePlanSteps = const [],
  });

  ChatState copyWith({
    List<ChatMessage>? messages,
    bool? isStreaming,
    String? sessionId,
    String? selectedProjectId,
    String? activeTool,
    List<PlanStep>? activePlanSteps,
  }) {
    return ChatState(
      messages: messages ?? this.messages,
      isStreaming: isStreaming ?? this.isStreaming,
      sessionId: sessionId ?? this.sessionId,
      selectedProjectId: selectedProjectId ?? this.selectedProjectId,
      activeTool: activeTool ?? this.activeTool,
      activePlanSteps: activePlanSteps ?? this.activePlanSteps,
    );
  }
}

class ChatNotifier extends StateNotifier<ChatState> {
  final KoraSocketService _socketService;
  StreamSubscription? _socketSubscription;

  ChatNotifier(this._socketService)
      : super(ChatState(sessionId: const Uuid().v4())) {
    _initSocketListener();
  }

  void _initSocketListener() {
    _socketSubscription = _socketService.messages.listen(_handleIncomingMessage);
  }

  @override
  void dispose() {
    _socketSubscription?.cancel();
    super.dispose();
  }

  void setSelectedProject(String? projectId) {
    state = state.copyWith(selectedProjectId: projectId);
  }

  void clearMessages() {
    state = state.copyWith(
      messages: [],
      isStreaming: false,
      activeTool: null,
      activePlanSteps: [],
    );
  }

  void cancelGeneration() {
    if (!state.isStreaming) return;
    _socketService.send(WsMessage(
      type: WsMessageType.chatCancel,
      sessionId: state.sessionId,
      projectId: state.selectedProjectId,
      payload: {},
    ));

    // Update active assistant message to cancelled
    if (state.messages.isNotEmpty) {
      final lastMsg = state.messages.last;
      if (lastMsg.role == MessageRole.assistant && lastMsg.status == MessageStatus.streaming) {
        final updated = lastMsg.copyWith(
          status: MessageStatus.cancelled,
          content: lastMsg.content.isEmpty ? 'Generation cancelled.' : '${lastMsg.content}\n\n[Cancelled]',
        );
        final list = List<ChatMessage>.from(state.messages);
        list[list.length - 1] = updated;
        state = state.copyWith(messages: list, isStreaming: false, activeTool: null);
      }
    }
  }

  Future<void> sendMessage(String text) async {
    final trimmed = text.trim();
    if (trimmed.isEmpty || state.isStreaming) return;

    final userMsg = ChatMessage(
      id: const Uuid().v4(),
      role: MessageRole.user,
      content: trimmed,
      status: MessageStatus.done,
    );

    final assistantMsgId = const Uuid().v4();
    final assistantMsg = ChatMessage(
      id: assistantMsgId,
      role: MessageRole.assistant,
      content: '',
      status: MessageStatus.streaming,
      planSteps: [],
    );

    state = state.copyWith(
      messages: [...state.messages, userMsg, assistantMsg],
      isStreaming: true,
      activeTool: null,
      activePlanSteps: [],
    );

    _socketService.send(WsMessage(
      type: WsMessageType.chatRequest,
      sessionId: state.sessionId,
      projectId: state.selectedProjectId,
      payload: {
        'message': trimmed,
        'attachments': [],
      },
    ));
  }

  void _handleIncomingMessage(WsMessage msg) {
    switch (msg.type) {
      case WsMessageType.chatChunk:
        final chunk = msg.payload['chunk'] as String? ?? '';
        if (state.messages.isNotEmpty) {
          final last = state.messages.last;
          if (last.role == MessageRole.assistant && last.status == MessageStatus.streaming) {
            final updated = last.copyWith(
              content: last.content + chunk,
            );
            final list = List<ChatMessage>.from(state.messages);
            list[list.length - 1] = updated;
            state = state.copyWith(messages: list);
          }
        }
        break;

      case WsMessageType.planCreated:
      case WsMessageType.planUpdate:
        final stepsRaw = msg.payload['steps'] as List<dynamic>? ?? [];
        final steps = stepsRaw.map((s) => PlanStep.fromJson(s as Map<String, dynamic>)).toList();
        if (steps.isNotEmpty) {
          state = state.copyWith(activePlanSteps: steps);
          if (state.messages.isNotEmpty) {
            final last = state.messages.last;
            if (last.role == MessageRole.assistant) {
              final list = List<ChatMessage>.from(state.messages);
              list[list.length - 1] = last.copyWith(planSteps: steps);
              state = state.copyWith(messages: list);
            }
          }
        }
        break;

      case WsMessageType.toolCallNotify:
        final tool = msg.payload['tool'] as String? ?? 'tool';
        state = state.copyWith(activeTool: tool);
        if (state.messages.isNotEmpty) {
          final last = state.messages.last;
          if (last.role == MessageRole.assistant) {
            final list = List<ChatMessage>.from(state.messages);
            list[list.length - 1] = last.copyWith(activeTool: tool);
            state = state.copyWith(messages: list);
          }
        }
        break;

      case WsMessageType.toolResultNotify:
        state = state.copyWith(activeTool: null);
        if (state.messages.isNotEmpty) {
          final last = state.messages.last;
          if (last.role == MessageRole.assistant) {
            final list = List<ChatMessage>.from(state.messages);
            list[list.length - 1] = last.copyWith(activeTool: null);
            state = state.copyWith(messages: list);
          }
        }
        break;

      case WsMessageType.chatDone:
        final payload = msg.payload;
        final fullText = payload['full_text'] as String? ?? '';
        final modelUsed = payload['model_used'] as String?;
        final inTokens = payload['input_tokens'] as int?;
        final outTokens = payload['output_tokens'] as int?;
        final latency = payload['latency_ms'] as int?;

        final sourcesRaw = payload['sources'] as List<dynamic>? ?? [];
        final sources = sourcesRaw.map((s) => RagSource.fromJson(s as Map<String, dynamic>)).toList();

        final webSourcesRaw = payload['web_sources'] as List<dynamic>? ?? [];
        final webSources = webSourcesRaw.map((w) => WebSource.fromJson(w as Map<String, dynamic>)).toList();

        if (state.messages.isNotEmpty) {
          final last = state.messages.last;
          if (last.role == MessageRole.assistant) {
            final updated = last.copyWith(
              content: fullText.isNotEmpty ? fullText : last.content,
              status: MessageStatus.done,
              sources: sources,
              webSources: webSources,
              modelUsed: modelUsed,
              inputTokens: inTokens,
              outputTokens: outTokens,
              latencyMs: latency,
              activeTool: null,
            );
            final list = List<ChatMessage>.from(state.messages);
            list[list.length - 1] = updated;
            state = state.copyWith(
              messages: list,
              isStreaming: false,
              activeTool: null,
            );
          }
        }
        break;

      case WsMessageType.chatCancelled:
        if (state.messages.isNotEmpty) {
          final last = state.messages.last;
          if (last.role == MessageRole.assistant) {
            final list = List<ChatMessage>.from(state.messages);
            list[list.length - 1] = last.copyWith(
              status: MessageStatus.cancelled,
              activeTool: null,
            );
            state = state.copyWith(messages: list, isStreaming: false, activeTool: null);
          }
        }
        break;

      case WsMessageType.error:
        final errMsg = msg.payload['message'] as String? ?? 'An error occurred';
        if (state.messages.isNotEmpty) {
          final last = state.messages.last;
          if (last.role == MessageRole.assistant && last.status == MessageStatus.streaming) {
            final list = List<ChatMessage>.from(state.messages);
            list[list.length - 1] = last.copyWith(
              status: MessageStatus.error,
              errorMessage: errMsg,
              content: last.content.isEmpty ? 'Error: $errMsg' : last.content,
              activeTool: null,
            );
            state = state.copyWith(messages: list, isStreaming: false, activeTool: null);
          }
        }
        break;

      default:
        break;
    }
  }
}

final chatProvider = StateNotifierProvider<ChatNotifier, ChatState>((ref) {
  final socketService = ref.watch(socketServiceProvider);
  return ChatNotifier(socketService);
});
