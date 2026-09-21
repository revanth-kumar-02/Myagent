/// DuckDuckGo web research result model

class ResearchResult {
  final String title;
  final String url;
  final String snippet;
  final double score;

  const ResearchResult({
    required this.title,
    required this.url,
    required this.snippet,
    this.score = 1.0,
  });

  factory ResearchResult.fromJson(Map<String, dynamic> json) {
    return ResearchResult(
      title: json['title'] as String? ?? '',
      url: json['url'] as String? ?? '',
      snippet: json['snippet'] as String? ?? '',
      score: (json['score'] as num?)?.toDouble() ?? 1.0,
    );
  }

  Map<String, dynamic> toJson() => {
    'title': title,
    'url': url,
    'snippet': snippet,
    'score': score,
  };
}
