import 'package:uuid/uuid.dart';

// ── Chat Domain Entities ──────────────────────────────────────────────────────

enum MessageRole { user, assistant }

class ChatSource {
  final String chunkId;
  final String filePath;
  final int? startLine;
  final int? endLine;

  const ChatSource({
    required this.chunkId,
    required this.filePath,
    this.startLine,
    this.endLine,
  });

  factory ChatSource.fromJson(Map<String, dynamic> json) => ChatSource(
        chunkId: json['chunk_id'] as String,
        filePath: json['file_path'] as String,
        startLine: json['start_line'] as int?,
        endLine: json['end_line'] as int?,
      );
}

class WebSource {
  final String url;
  final String title;
  final String snippet;

  const WebSource({required this.url, required this.title, required this.snippet});

  factory WebSource.fromJson(Map<String, dynamic> json) => WebSource(
        url: json['url'] as String,
        title: json['title'] as String,
        snippet: json['snippet'] as String,
      );
}

class ChatMessage {
  final String id;
  final MessageRole role;
  final String content;
  final List<ChatSource> sources;
  final List<WebSource> webSources;
  final DateTime timestamp;
  final bool isStreaming;

  ChatMessage({
    String? id,
    required this.role,
    required this.content,
    this.sources = const [],
    this.webSources = const [],
    DateTime? timestamp,
    this.isStreaming = false,
  })  : id = id ?? const Uuid().v4(),
        timestamp = timestamp ?? DateTime.now();

  ChatMessage copyWith({
    String? content,
    List<ChatSource>? sources,
    List<WebSource>? webSources,
    bool? isStreaming,
  }) =>
      ChatMessage(
        id: id,
        role: role,
        content: content ?? this.content,
        sources: sources ?? this.sources,
        webSources: webSources ?? this.webSources,
        timestamp: timestamp,
        isStreaming: isStreaming ?? this.isStreaming,
      );
}
