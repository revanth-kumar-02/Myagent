/// Registered model information model (no secrets)

class ModelInfo {
  final String name;
  final String provider;
  final List<String> capabilities;
  final int contextWindow;
  final int? dimension;

  const ModelInfo({
    required this.name,
    required this.provider,
    required this.capabilities,
    required this.contextWindow,
    this.dimension,
  });

  factory ModelInfo.fromJson(Map<String, dynamic> json) {
    return ModelInfo(
      name: json['name'] as String? ?? '',
      provider: json['provider'] as String? ?? 'huggingface',
      capabilities: (json['capabilities'] as List<dynamic>?)?.map((e) => e.toString()).toList() ?? [],
      contextWindow: json['context_window'] as int? ?? 4096,
      dimension: json['dimension'] as int?,
    );
  }

  Map<String, dynamic> toJson() => {
    'name': name,
    'provider': provider,
    'capabilities': capabilities,
    'context_window': contextWindow,
    'dimension': dimension,
  };
}
