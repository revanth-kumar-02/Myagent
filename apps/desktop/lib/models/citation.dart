/// Citation models for RAG files and external web research

class RagSource {
  final String chunkId;
  final String filePath;
  final int? startLine;
  final int? endLine;

  const RagSource({
    required this.chunkId,
    required this.filePath,
    this.startLine,
    this.endLine,
  });

  factory RagSource.fromJson(Map<String, dynamic> json) {
    return RagSource(
      chunkId: json['chunk_id'] as String? ?? '',
      filePath: json['file_path'] as String? ?? '',
      startLine: json['start_line'] as int?,
      endLine: json['end_line'] as int?,
    );
  }

  Map<String, dynamic> toJson() => {
    'chunk_id': chunkId,
    'file_path': filePath,
    'start_line': startLine,
    'end_line': endLine,
  };
}

class WebSource {
  final String url;
  final String title;
  final String snippet;
  final double score;

  const WebSource({
    required this.url,
    required this.title,
    required this.snippet,
    this.score = 1.0,
  });

  factory WebSource.fromJson(Map<String, dynamic> json) {
    return WebSource(
      url: json['url'] as String? ?? '',
      title: json['title'] as String? ?? '',
      snippet: json['snippet'] as String? ?? '',
      score: (json['score'] as num?)?.toDouble() ?? 1.0,
    );
  }

  Map<String, dynamic> toJson() => {
    'url': url,
    'title': title,
    'snippet': snippet,
    'score': score,
  };
}
