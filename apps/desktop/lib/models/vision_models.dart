/// vision_models.dart — Data classes for the Vision workspace
///
/// Maps to the backend api/vision.py JSON contracts.
/// No mock data: all fields come from the backend.

class VisionCapabilities {
  final bool visionModelAvailable;
  final List<Map<String, dynamic>> visionModels;
  final bool screenCaptureAvailable;
  final String? screenCaptureError;
  final List<String> supportedOperations;

  const VisionCapabilities({
    required this.visionModelAvailable,
    required this.visionModels,
    required this.screenCaptureAvailable,
    this.screenCaptureError,
    required this.supportedOperations,
  });

  factory VisionCapabilities.fromJson(Map<String, dynamic> json) {
    return VisionCapabilities(
      visionModelAvailable: json['vision_model_available'] as bool? ?? false,
      visionModels: (json['vision_models'] as List<dynamic>? ?? [])
          .map((e) => e as Map<String, dynamic>)
          .toList(),
      screenCaptureAvailable: json['screen_capture_available'] as bool? ?? false,
      screenCaptureError: json['screen_capture_error'] as String?,
      supportedOperations: (json['supported_operations'] as List<dynamic>? ?? [])
          .map((e) => e.toString())
          .toList(),
    );
  }

  bool get canAnalyze => visionModelAvailable;
  bool get canCapture => screenCaptureAvailable;
  bool get canAsk => visionModelAvailable;
}

class DetectedElement {
  final String elementId;
  final String elementType;
  final String label;
  final double confidence;
  final bool isClickable;
  final Map<String, dynamic> boundingBox;

  const DetectedElement({
    required this.elementId,
    required this.elementType,
    required this.label,
    required this.confidence,
    required this.isClickable,
    required this.boundingBox,
  });

  factory DetectedElement.fromJson(Map<String, dynamic> json) {
    return DetectedElement(
      elementId: json['element_id'] as String? ?? '',
      elementType: json['element_type'] as String? ?? 'custom',
      label: json['label'] as String? ?? '',
      confidence: (json['confidence'] as num?)?.toDouble() ?? 1.0,
      isClickable: json['is_clickable'] as bool? ?? true,
      boundingBox: json['bounding_box'] as Map<String, dynamic>? ?? {},
    );
  }
}

class VisionAnalysisResult {
  final String analysisId;
  final String summary;
  final String description;
  final List<DetectedElement> detectedElements;
  final List<String> detectedText;
  final String? activeWindow;
  final List<String> errorMessages;
  final double confidence;
  final String modelUsed;
  final String timestamp;
  // Set after successful API call — the full image URL for preview
  final String? imageUrl;

  const VisionAnalysisResult({
    required this.analysisId,
    required this.summary,
    required this.description,
    required this.detectedElements,
    required this.detectedText,
    this.activeWindow,
    required this.errorMessages,
    required this.confidence,
    required this.modelUsed,
    required this.timestamp,
    this.imageUrl,
  });

  factory VisionAnalysisResult.fromJson(Map<String, dynamic> json, {String? imageUrl}) {
    final elems = (json['detected_elements'] as List<dynamic>? ?? [])
        .map((e) => DetectedElement.fromJson(e as Map<String, dynamic>))
        .toList();
    final texts = (json['detected_text'] as List<dynamic>? ?? [])
        .map((e) => e.toString())
        .toList();
    final errors = (json['error_messages'] as List<dynamic>? ?? [])
        .map((e) => e.toString())
        .toList();

    return VisionAnalysisResult(
      analysisId: json['analysis_id'] as String? ?? '',
      summary: json['summary'] as String? ?? '',
      description: json['description'] as String? ?? '',
      detectedElements: elems,
      detectedText: texts,
      activeWindow: json['active_window'] as String?,
      errorMessages: errors,
      confidence: (json['confidence'] as num?)?.toDouble() ?? 1.0,
      modelUsed: json['model_used'] as String? ?? '',
      timestamp: json['timestamp'] as String? ?? '',
      imageUrl: imageUrl,
    );
  }
}

class RecentVisionItem {
  final String analysisId;
  final String summary;
  final String modelUsed;
  final int elementCount;
  final int ocrTextCount;
  final String timestamp;
  final double confidence;

  const RecentVisionItem({
    required this.analysisId,
    required this.summary,
    required this.modelUsed,
    required this.elementCount,
    required this.ocrTextCount,
    required this.timestamp,
    required this.confidence,
  });

  factory RecentVisionItem.fromJson(Map<String, dynamic> json) {
    return RecentVisionItem(
      analysisId: json['analysis_id'] as String? ?? '',
      summary: json['summary'] as String? ?? '',
      modelUsed: json['model_used'] as String? ?? '',
      elementCount: json['element_count'] as int? ?? 0,
      ocrTextCount: json['ocr_text_count'] as int? ?? 0,
      timestamp: json['timestamp'] as String? ?? '',
      confidence: (json['confidence'] as num?)?.toDouble() ?? 1.0,
    );
  }
}

class VisionContextResult {
  final String analysisId;
  final String contextString;
  final String summary;
  final String elementsSummary;
  final String activeWindow;
  final double confidence;
  final String usageHint;

  const VisionContextResult({
    required this.analysisId,
    required this.contextString,
    required this.summary,
    required this.elementsSummary,
    required this.activeWindow,
    required this.confidence,
    required this.usageHint,
  });

  factory VisionContextResult.fromJson(Map<String, dynamic> json) {
    return VisionContextResult(
      analysisId: json['analysis_id'] as String? ?? '',
      contextString: json['context_string'] as String? ?? '',
      summary: json['summary'] as String? ?? '',
      elementsSummary: json['elements_summary'] as String? ?? '',
      activeWindow: json['active_window'] as String? ?? '',
      confidence: (json['confidence'] as num?)?.toDouble() ?? 1.0,
      usageHint: json['usage_hint'] as String? ?? '',
    );
  }
}
