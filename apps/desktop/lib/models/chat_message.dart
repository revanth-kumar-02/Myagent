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

  ChatMessage copyWith({
    String? id,
    MessageRole? role,
    String? content,
    MessageStatus? status,
    List<RagSource>? sources,
    List<WebSource>? webSources,
    List<PlanStep>? planSteps,
    String? activeTool,
    String? modelUsed,
    int? inputTokens,
    int? outputTokens,
    int? latencyMs,
    String? errorMessage,
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
      activeTool: activeTool ?? this.activeTool,
      modelUsed: modelUsed ?? this.modelUsed,
      inputTokens: inputTokens ?? this.inputTokens,
      outputTokens: outputTokens ?? this.outputTokens,
      latencyMs: latencyMs ?? this.latencyMs,
      errorMessage: errorMessage ?? this.errorMessage,
      timestamp: timestamp ?? this.timestamp,
    );
  }
}
