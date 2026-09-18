/// Project domain entity.
class Project {
  final String id;
  final String name;
  final String rootPath;
  final DateTime createdAt;
  final bool isIndexing;

  const Project({
    required this.id,
    required this.name,
    required this.rootPath,
    required this.createdAt,
    this.isIndexing = false,
  });

  Project copyWith({String? name, String? rootPath, bool? isIndexing}) => Project(
        id: id,
        name: name ?? this.name,
        rootPath: rootPath ?? this.rootPath,
        createdAt: createdAt,
        isIndexing: isIndexing ?? this.isIndexing,
      );

  factory Project.fromJson(Map<String, dynamic> json) => Project(
        id: json['id'] as String,
        name: json['name'] as String,
        rootPath: json['root_path'] as String,
        createdAt: DateTime.parse(json['created_at'] as String),
      );

  Map<String, dynamic> toJson() => {
        'id': id,
        'name': name,
        'root_path': rootPath,
        'created_at': createdAt.toIso8601String(),
      };
}
