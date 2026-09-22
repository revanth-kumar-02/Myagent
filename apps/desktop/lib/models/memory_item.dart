/// Memory & Knowledge Graph models for Kora Desktop

class MemoryItem {
  final String id;
  final String content;
  final String type;
  final double confidence;
  final double importance;
  final String source;
  final String status;
  final String createdAt;
  final String? updatedAt;
  final String? projectId;
  final Map<String, dynamic> metadata;

  const MemoryItem({
    required this.id,
    required this.content,
    required this.type,
    this.confidence = 1.0,
    this.importance = 0.5,
    this.source = 'user_explicit',
    this.status = 'active',
    required this.createdAt,
    this.updatedAt,
    this.projectId,
    this.metadata = const {},
  });

  bool get isActive => status == 'active';
  bool get isArchived => status == 'archived';

  factory MemoryItem.fromJson(Map<String, dynamic> json) {
    return MemoryItem(
      id: json['id'] as String? ?? '',
      content: json['content'] as String? ?? '',
      type: json['type'] as String? ?? 'user_preference',
      confidence: (json['confidence'] as num?)?.toDouble() ?? 1.0,
      importance: (json['importance'] as num?)?.toDouble() ?? 0.5,
      source: json['source'] as String? ?? 'user_explicit',
      status: json['status'] as String? ?? 'active',
      createdAt: json['created_at'] as String? ?? '',
      updatedAt: json['updated_at'] as String?,
      projectId: json['project_id'] as String?,
      metadata: json['metadata'] as Map<String, dynamic>? ?? {},
    );
  }

  Map<String, dynamic> toJson() => {
    'id': id,
    'content': content,
    'type': type,
    'confidence': confidence,
    'importance': importance,
    'source': source,
    'status': status,
    'created_at': createdAt,
    'updated_at': updatedAt,
    'project_id': projectId,
    'metadata': metadata,
  };
}

class GraphEntityItem {
  final String id;
  final String name;
  final String type;
  final String label;

  const GraphEntityItem({
    required this.id,
    required this.name,
    required this.type,
    required this.label,
  });

  factory GraphEntityItem.fromJson(Map<String, dynamic> json) {
    return GraphEntityItem(
      id: json['id'] as String? ?? '',
      name: json['name'] as String? ?? '',
      type: json['type'] as String? ?? 'concept',
      label: json['label'] as String? ?? '',
    );
  }
}

class GraphRelationshipItem {
  final String source;
  final String target;
  final String type;
  final double confidence;
  final String? memoryId;

  const GraphRelationshipItem({
    required this.source,
    required this.target,
    required this.type,
    this.confidence = 1.0,
    this.memoryId,
  });

  factory GraphRelationshipItem.fromJson(Map<String, dynamic> json) {
    return GraphRelationshipItem(
      source: json['source'] as String? ?? '',
      target: json['target'] as String? ?? '',
      type: json['type'] as String? ?? 'related_to',
      confidence: (json['confidence'] as num?)?.toDouble() ?? 1.0,
      memoryId: json['memory_id'] as String?,
    );
  }
}
