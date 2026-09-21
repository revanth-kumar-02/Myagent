/// Project model for Kora Desktop

class Project {
  final String id;
  final String name;
  final String description;
  final String rootPath;
  final String createdAt;
  final int fileCount;
  final int chunkCount;

  const Project({
    required this.id,
    required this.name,
    required this.description,
    required this.rootPath,
    required this.createdAt,
    this.fileCount = 0,
    this.chunkCount = 0,
  });

  factory Project.fromJson(Map<String, dynamic> json) {
    return Project(
      id: json['id'] as String? ?? '',
      name: json['name'] as String? ?? 'Untitled Project',
      description: json['description'] as String? ?? '',
      rootPath: json['root_path'] as String? ?? '',
      createdAt: json['created_at'] as String? ?? '',
      fileCount: json['file_count'] as int? ?? 0,
      chunkCount: json['chunk_count'] as int? ?? 0,
    );
  }

  Map<String, dynamic> toJson() => {
    'id': id,
    'name': name,
    'description': description,
    'root_path': rootPath,
    'created_at': createdAt,
    'file_count': fileCount,
    'chunk_count': chunkCount,
  };
}
