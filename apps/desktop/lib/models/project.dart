/// Project model for Kora Desktop
///
/// Represents a real directory on the user's local filesystem.

class Project {
  final String id;
  final String name;
  final String description;
  final String rootPath;
  final String relativePath;
  final bool exists;
  final bool isDirectory;
  final int fileCount;
  final int folderCount;
  final List<String> detectedLanguages;
  final List<String> topLevelFolders;
  final String gitStatus;
  final String lastModified;
  final String projectType;
  final List<String> frameworks;
  final int chunkCount;
  final String createdAt;

  const Project({
    required this.id,
    required this.name,
    this.description = '',
    required this.rootPath,
    this.relativePath = '',
    this.exists = true,
    this.isDirectory = true,
    this.fileCount = 0,
    this.folderCount = 0,
    this.detectedLanguages = const [],
    this.topLevelFolders = const [],
    this.gitStatus = 'Not a Git repository',
    this.lastModified = '',
    this.projectType = 'Generic Project',
    this.frameworks = const [],
    this.chunkCount = 0,
    this.createdAt = '',
  });

  factory Project.fromJson(Map<String, dynamic> json) {
    return Project(
      id: json['id'] as String? ?? (json['root_path'] as String? ?? json['name'] as String? ?? ''),
      name: json['name'] as String? ?? 'Untitled Project',
      description: json['description'] as String? ?? '',
      rootPath: json['root_path'] as String? ?? '',
      relativePath: json['relative_path'] as String? ?? '',
      exists: json['exists'] as bool? ?? true,
      isDirectory: json['is_directory'] as bool? ?? true,
      fileCount: json['file_count'] as int? ?? 0,
      folderCount: json['folder_count'] as int? ?? 0,
      detectedLanguages: (json['detected_languages'] as List<dynamic>?)?.map((e) => e.toString()).toList() ?? [],
      topLevelFolders: (json['top_level_folders'] as List<dynamic>?)?.map((e) => e.toString()).toList() ?? [],
      gitStatus: json['git_status'] as String? ?? 'Not a Git repository',
      lastModified: json['last_modified'] as String? ?? '',
      projectType: json['project_type'] as String? ?? 'Generic Project',
      frameworks: (json['frameworks'] as List<dynamic>?)?.map((e) => e.toString()).toList() ?? [],
      chunkCount: json['chunk_count'] as int? ?? 0,
      createdAt: json['created_at'] as String? ?? '',
    );
  }

  Map<String, dynamic> toJson() => {
    'id': id,
    'name': name,
    'description': description,
    'root_path': rootPath,
    'relative_path': relativePath,
    'exists': exists,
    'is_directory': isDirectory,
    'file_count': fileCount,
    'folder_count': folderCount,
    'detected_languages': detectedLanguages,
    'top_level_folders': topLevelFolders,
    'git_status': gitStatus,
    'last_modified': lastModified,
    'project_type': projectType,
    'frameworks': frameworks,
    'chunk_count': chunkCount,
    'created_at': createdAt,
  };
}
