import 'dart:async';
import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:uuid/uuid.dart';

import '../models/chat_message.dart';
import '../models/citation.dart';
import '../models/plan_step.dart';
import '../services/kora_socket_service.dart';
import '../services/ollama_direct_service.dart';
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

  static const Object _sentinel = Object();

  ChatState copyWith({
    List<ChatMessage>? messages,
    bool? isStreaming,
    String? sessionId,
    Object? selectedProjectId = _sentinel,
    Object? activeTool = _sentinel,
    List<PlanStep>? activePlanSteps,
  }) {
    return ChatState(
      messages: messages ?? this.messages,
      isStreaming: isStreaming ?? this.isStreaming,
      sessionId: sessionId ?? this.sessionId,
      selectedProjectId: identical(selectedProjectId, _sentinel)
          ? this.selectedProjectId
          : (selectedProjectId as String?),
      activeTool: identical(activeTool, _sentinel)
          ? this.activeTool
          : (activeTool as String?),
      activePlanSteps: activePlanSteps ?? this.activePlanSteps,
    );
  }
}

class ChatNotifier extends StateNotifier<ChatState> {
  final KoraSocketService _socketService;
  final OllamaDirectService _ollamaService;
  StreamSubscription? _socketSubscription;
  StreamSubscription? _stateSubscription;
  StreamSubscription? _directOllamaSub;
  bool _isDirectOllamaActive = false;

  ChatNotifier(this._socketService, [OllamaDirectService? ollamaService])
      : _ollamaService = ollamaService ?? OllamaDirectService(),
        super(ChatState(sessionId: const Uuid().v4())) {
    _initSocketListener();
  }

  void _initSocketListener() {
    _socketSubscription = _socketService.messages.listen(_handleIncomingMessage);
    _stateSubscription = _socketService.stateStream.listen((connState) {
      if ((connState == SocketConnectionState.disconnected || connState == SocketConnectionState.error) &&
          state.isStreaming &&
          !_isDirectOllamaActive) {
        _abortStreamingDueToDisconnect(connState);
      }
    });
  }

  void _abortStreamingDueToDisconnect(SocketConnectionState connState) {
    if (state.messages.isNotEmpty) {
      final last = state.messages.last;
      if (last.role == MessageRole.assistant && last.status == MessageStatus.streaming) {
        final errText = connState == SocketConnectionState.error
            ? 'Connection failed: Unable to communicate with Kora backend at ws://127.0.0.1:8765/ws.'
            : 'Connection lost: Disconnected from Kora backend.';
        final list = List<ChatMessage>.from(state.messages);
        list[list.length - 1] = last.copyWith(
          status: MessageStatus.error,
          errorMessage: errText,
          content: last.content.isEmpty ? errText : '${last.content}\n\n[$errText]',
          activeTool: null,
        );
        state = state.copyWith(messages: list, isStreaming: false, activeTool: null);
      }
    } else {
      state = state.copyWith(isStreaming: false, activeTool: null);
    }
  }

  @override
  void dispose() {
    _socketSubscription?.cancel();
    _stateSubscription?.cancel();
    _directOllamaSub?.cancel();
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
    _isDirectOllamaActive = false;
    _directOllamaSub?.cancel();
    _directOllamaSub = null;
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

  /// Inject visual context into chat from the Vision workspace.
  ///
  /// Adds a system-style user message containing the visual context string
  /// and sends it through the normal WS CHAT_REQUEST pipeline so the agent
  /// has full awareness of the screen/image content.
  Future<void> sendVisionContext(String contextString) async {
    if (contextString.isEmpty) return;
    const prefix = '**[Visual Context from Vision Workspace]**\n\n';
    await sendMessage('$prefix$contextString');
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

    if (_socketService.isConnected) {
      _isDirectOllamaActive = false;
      _socketService.send(WsMessage(
        type: WsMessageType.chatRequest,
        sessionId: state.sessionId,
        projectId: state.selectedProjectId,
        payload: {
          'message': trimmed,
          'attachments': [],
        },
      ));
    } else {
      // Backend is unavailable/offline -> stream directly from local Ollama
      _isDirectOllamaActive = true;
      await _streamFromDirectOllama(trimmed, assistantMsgId);
    }
  }

  Future<void> _streamFromDirectOllama(String prompt, String assistantMsgId) async {
    try {
      final ollamaAvailable = await _ollamaService.isAvailable();
      if (!ollamaAvailable) {
        _isDirectOllamaActive = false;
        _updateAssistantMessage(
          assistantMsgId,
          (msg) => msg.copyWith(
            status: MessageStatus.error,
            errorMessage: 'Cannot communicate with Kora backend (disconnected). Local Ollama is also unreachable at http://127.0.0.1:11434.\n\nStart Ollama or the Kora backend to chat.',
            content: 'Cannot communicate with Kora backend (disconnected). Local Ollama is also unreachable at http://127.0.0.1:11434.\n\nStart Ollama or the Kora backend to chat.',
          ),
        );
        state = state.copyWith(isStreaming: false);
        return;
      }

      final stopwatch = Stopwatch()..start();
      _directOllamaSub = _ollamaService
          .streamChat(history: state.messages, prompt: prompt)
          .listen(
        (chunk) {
          _updateAssistantMessage(
            assistantMsgId,
            (msg) => msg.copyWith(
              content: msg.content + chunk,
              status: MessageStatus.streaming,
            ),
          );
        },
        onError: (err) {
          _isDirectOllamaActive = false;
          _directOllamaSub = null;
          _updateAssistantMessage(
            assistantMsgId,
            (msg) => msg.copyWith(
              status: MessageStatus.error,
              errorMessage: 'Ollama local inference error: $err',
            ),
          );
          state = state.copyWith(isStreaming: false);
        },
        onDone: () {
          _isDirectOllamaActive = false;
          _directOllamaSub = null;
          stopwatch.stop();
          _updateAssistantMessage(
            assistantMsgId,
            (msg) => msg.copyWith(
              status: MessageStatus.done,
              modelUsed: 'qwen3:1.7b',
              latencyMs: stopwatch.elapsedMilliseconds,
            ),
          );
          state = state.copyWith(isStreaming: false);
        },
        cancelOnError: true,
      );
    } catch (e) {
      _isDirectOllamaActive = false;
      _directOllamaSub = null;
      _updateAssistantMessage(
        assistantMsgId,
        (msg) => msg.copyWith(
          status: MessageStatus.error,
          errorMessage: 'Failed to stream from local Ollama: $e',
        ),
      );
      state = state.copyWith(isStreaming: false);
    }
  }

  void _updateAssistantMessage(String id, ChatMessage Function(ChatMessage) updater) {
    if (state.messages.isEmpty) return;
    final list = List<ChatMessage>.from(state.messages);
    final idx = list.indexWhere((m) => m.id == id);
    if (idx != -1) {
      list[idx] = updater(list[idx]);
      state = state.copyWith(messages: list);
    }
  }

  @visibleForTesting
  void testHandleMessage(WsMessage msg) => _handleIncomingMessage(msg);

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
        final stepsRaw = msg.payload['steps'] as List<dynamic>?;
        if (stepsRaw != null && stepsRaw.isNotEmpty) {
          final steps = stepsRaw.map((s) => PlanStep.fromJson(s as Map<String, dynamic>)).toList();
          state = state.copyWith(activePlanSteps: steps);
          if (state.messages.isNotEmpty) {
            final last = state.messages.last;
            if (last.role == MessageRole.assistant) {
              final list = List<ChatMessage>.from(state.messages);
              list[list.length - 1] = last.copyWith(planSteps: steps);
              state = state.copyWith(messages: list);
            }
          }
        } else if (msg.payload.containsKey('step_index') && msg.payload.containsKey('status')) {
          final stepIdx = msg.payload['step_index'] as int?;
          final statusStr = msg.payload['status'] as String?;
          final label = msg.payload['label'] as String? ?? '';
          if (stepIdx != null && statusStr != null) {
            final updatedSteps = List<PlanStep>.from(state.activePlanSteps);
            while (updatedSteps.length <= stepIdx) {
              updatedSteps.add(PlanStep(
                index: updatedSteps.length,
                label: label.isNotEmpty ? label : 'Step ${updatedSteps.length + 1}',
                status: PlanStepStatus.pending,
              ));
            }
            updatedSteps[stepIdx] = updatedSteps[stepIdx].copyWith(
              label: label.isNotEmpty ? label : updatedSteps[stepIdx].label,
              status: PlanStepStatus.fromString(statusStr),
            );
            state = state.copyWith(activePlanSteps: updatedSteps);
            if (state.messages.isNotEmpty) {
              final last = state.messages.last;
              if (last.role == MessageRole.assistant) {
                final list = List<ChatMessage>.from(state.messages);
                list[list.length - 1] = last.copyWith(planSteps: updatedSteps);
                state = state.copyWith(messages: list);
              }
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
              activePlanSteps: [],
            );
          }
        } else {
          state = state.copyWith(isStreaming: false, activeTool: null, activePlanSteps: []);
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
            state = state.copyWith(messages: list, isStreaming: false, activeTool: null, activePlanSteps: []);
          }
        } else {
          state = state.copyWith(isStreaming: false, activeTool: null, activePlanSteps: []);
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
            state = state.copyWith(messages: list, isStreaming: false, activeTool: null, activePlanSteps: []);
          }
        } else {
          state = state.copyWith(isStreaming: false, activeTool: null, activePlanSteps: []);
        }
        break;

      case WsMessageType.permissionRequest:
        final reqId = msg.payload['request_id'] as String?;
        if (reqId != null) {
          _socketService.send(WsMessage(
            type: WsMessageType.permissionResponse,
            sessionId: state.sessionId,
            projectId: state.selectedProjectId,
            payload: {
              'request_id': reqId,
              'granted': true,
            },
          ));
        }
        break;

      default:
        break;
    }
  }
}

final chatProvider = StateNotifierProvider<ChatNotifier, ChatState>((ref) {
  final socketService = ref.watch(socketServiceProvider);
  final ollamaService = ref.watch(ollamaDirectServiceProvider);
  return ChatNotifier(socketService, ollamaService);
});
