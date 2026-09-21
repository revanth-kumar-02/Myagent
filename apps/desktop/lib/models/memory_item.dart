/// Memory Item model for Kora Desktop

class MemoryItem {
  final String id;
  final String content;
  final String type;
  final double confidence;
  final String createdAt;
  final String? projectId;

  const MemoryItem({
    required this.id,
    required this.content,
    required this.type,
    this.confidence = 1.0,
    required this.createdAt,
    this.projectId,
  });

  factory MemoryItem.fromJson(Map<String, dynamic> json) {
    return MemoryItem(
      id: json['id'] as String? ?? '',
      content: json['content'] as String? ?? '',
      type: json['type'] as String? ?? 'fact',
      confidence: (json['confidence'] as num?)?.toDouble() ?? 1.0,
      createdAt: json['created_at'] as String? ?? '',
      projectId: json['project_id'] as String?,
    );
  }

  Map<String, dynamic> toJson() => {
    'id': id,
    'content': content,
    'type': type,
    'confidence': confidence,
    'created_at': createdAt,
    'project_id': projectId,
  };
}
