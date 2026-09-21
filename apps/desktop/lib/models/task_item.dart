/// Task item model for Kora Desktop

class TaskItem {
  final String id;
  final String title;
  final String status;
  final String category;
  final int durationMs;
  final String createdAt;
  final String? projectId;

  const TaskItem({
    required this.id,
    required this.title,
    required this.status,
    this.category = 'General',
    this.durationMs = 0,
    required this.createdAt,
    this.projectId,
  });

  factory TaskItem.fromJson(Map<String, dynamic> json) {
    return TaskItem(
      id: json['id'] as String? ?? '',
      title: json['title'] as String? ?? 'Untitled Task',
      status: json['status'] as String? ?? 'pending',
      category: json['category'] as String? ?? 'General',
      durationMs: json['duration_ms'] as int? ?? 0,
      createdAt: json['created_at'] as String? ?? '',
      projectId: json['project_id'] as String?,
    );
  }

  Map<String, dynamic> toJson() => {
    'id': id,
    'title': title,
    'status': status,
    'category': category,
    'duration_ms': durationMs,
    'created_at': createdAt,
    'project_id': projectId,
  };
}
