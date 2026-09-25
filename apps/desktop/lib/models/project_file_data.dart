import '../services/project/file_type_detector.dart';

/// Real filesystem file representation for preview and inspection.
class ProjectFileData {
  final String name;
  final String relativePath;
  final String absolutePath;
  final String extension;
  final FileCategory category;
  final String mimeType;
  final int sizeBytes;
  final String? content;
  final bool truncated;
  final int lineCount;
  final String? rawContentUrl;

  const ProjectFileData({
    required this.name,
    required this.relativePath,
    required this.absolutePath,
    required this.extension,
    required this.category,
    required this.mimeType,
    required this.sizeBytes,
    this.content,
    this.truncated = false,
    this.lineCount = 0,
    this.rawContentUrl,
  });

  factory ProjectFileData.fromJson(Map<String, dynamic> json, {String? rawContentUrl}) {
    final catStr = json['category'] as String? ?? 'binary';
    final category = switch (catStr) {
      'text' => FileCategory.text,
      'image' => FileCategory.image,
      'pdf' => FileCategory.pdf,
      _ => FileCategory.binary,
    };

    return ProjectFileData(
      name: json['name'] as String? ?? '',
      relativePath: json['relative_path'] as String? ?? '',
      absolutePath: json['absolute_path'] as String? ?? '',
      extension: json['extension'] as String? ?? '',
      category: category,
      mimeType: json['mime_type'] as String? ?? 'application/octet-stream',
      sizeBytes: json['size_bytes'] as int? ?? 0,
      content: json['content'] as String?,
      truncated: json['truncated'] as bool? ?? false,
      lineCount: json['line_count'] as int? ?? 0,
      rawContentUrl: rawContentUrl,
    );
  }

  Map<String, dynamic> toJson() => {
    'name': name,
    'relative_path': relativePath,
    'absolute_path': absolutePath,
    'extension': extension,
    'category': category.name,
    'mime_type': mimeType,
    'size_bytes': sizeBytes,
    'content': content,
    'truncated': truncated,
    'line_count': lineCount,
    'raw_content_url': rawContentUrl,
  };
}
