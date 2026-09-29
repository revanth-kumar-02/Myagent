import 'citation.dart';
import 'plan_step.dart';

enum MessageRole { user, assistant, system }

enum MessageStatus { sending, streaming, done, error, cancelled }

class ChatMessage {
  final String id;
  final MessageRole role;
  final String content;
  final MessageStatus status;
  final List<RagSource> sources;
  final List<WebSource> webSources;
  final List<PlanStep> planSteps;
  final String? activeTool;
  final String? modelUsed;
  final int? inputTokens;
  final int? outputTokens;
  final int? latencyMs;
  final String? errorMessage;
  final DateTime timestamp;

  ChatMessage({
    required this.id,
    required this.role,
    required this.content,
    this.status = MessageStatus.done,
    this.sources = const [],
    this.webSources = const [],
    this.planSteps = const [],
    this.activeTool,
    this.modelUsed,
    this.inputTokens,
    this.outputTokens,
    this.latencyMs,
    this.errorMessage,
    DateTime? timestamp,
  }) : timestamp = timestamp ?? DateTime.now();

  static const Object _sentinel = Object();

  ChatMessage copyWith({
    String? id,
    MessageRole? role,
    String? content,
    MessageStatus? status,
    List<RagSource>? sources,
    List<WebSource>? webSources,
    List<PlanStep>? planSteps,
    Object? activeTool = _sentinel,
    Object? modelUsed = _sentinel,
    int? inputTokens,
    int? outputTokens,
    int? latencyMs,
    Object? errorMessage = _sentinel,
    DateTime? timestamp,
  }) {
    return ChatMessage(
      id: id ?? this.id,
      role: role ?? this.role,
      content: content ?? this.content,
      status: status ?? this.status,
      sources: sources ?? this.sources,
      webSources: webSources ?? this.webSources,
      planSteps: planSteps ?? this.planSteps,
      activeTool: identical(activeTool, _sentinel)
          ? this.activeTool
          : (activeTool as String?),
      modelUsed: identical(modelUsed, _sentinel)
          ? this.modelUsed
          : (modelUsed as String?),
      inputTokens: inputTokens ?? this.inputTokens,
      outputTokens: outputTokens ?? this.outputTokens,
      latencyMs: latencyMs ?? this.latencyMs,
      errorMessage: identical(errorMessage, _sentinel)
          ? this.errorMessage
          : (errorMessage as String?),
      timestamp: timestamp ?? this.timestamp,
    );
  }
}
