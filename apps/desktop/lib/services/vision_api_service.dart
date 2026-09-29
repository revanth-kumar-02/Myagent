import 'dart:convert';
import 'dart:io';
import 'package:http/http.dart' as http;
import 'package:http_parser/http_parser.dart';

import '../core/config/app_config.dart';
import '../models/vision_models.dart';

/// VisionApiService — HTTP client for all /api/vision/* endpoints.
///
/// Kept separate from KoraApiService because image uploads require
/// multipart/form-data which the generic ApiClient does not support.
/// All other methods reuse the same HTTP base URL from AppConfig.
class VisionApiService {
  final AppConfig _config;
  final http.Client _client;

  VisionApiService({
    AppConfig config = const AppConfig(),
    http.Client? client,
  })  : _config = config,
        _client = client ?? http.Client();

  String get _base => _config.httpBaseUrl;

  // ── Capabilities ────────────────────────────────────────────────────────────

  /// Fetch honest capability metadata from the backend.
  Future<VisionCapabilities> getCapabilities() async {
    final res = await _client
        .get(Uri.parse('$_base/api/vision/capabilities'))
        .timeout(_config.requestTimeout);
    _checkStatus(res, '/api/vision/capabilities');
    final json = jsonDecode(res.body) as Map<String, dynamic>;
    return VisionCapabilities.fromJson(json);
  }

  // ── Analyze Uploaded Image ──────────────────────────────────────────────────

  /// Upload a local image file for analysis.
  /// Returns a [VisionAnalysisResult] with a pre-populated imageUrl.
  Future<VisionAnalysisResult> analyzeImage(
    String filePath, {
    String? customPrompt,
  }) async {
    final file = File(filePath);
    if (!file.existsSync()) {
      throw Exception('Image file not found: $filePath');
    }

    final ext = filePath.split('.').last.toLowerCase();
    final mimeMap = {
      'png': 'image/png',
      'jpg': 'image/jpeg',
      'jpeg': 'image/jpeg',
      'webp': 'image/webp',
      'bmp': 'image/bmp',
      'gif': 'image/gif',
    };
    final mimeType = mimeMap[ext] ?? 'image/png';

    final request = http.MultipartRequest('POST', Uri.parse('$_base/api/vision/analyze'));
    request.files.add(await http.MultipartFile.fromPath(
      'file',
      filePath,
      contentType: MediaType.parse(mimeType),
    ));
    if (customPrompt != null && customPrompt.isNotEmpty) {
      request.fields['custom_prompt'] = customPrompt;
    }

    final streamed = await _client.send(request).timeout(_config.requestTimeout * 3);
    final res = await http.Response.fromStream(streamed);
    _checkStatus(res, '/api/vision/analyze');

    final json = jsonDecode(res.body) as Map<String, dynamic>;
    final analysisId = json['analysis_id'] as String? ?? '';
    final imageUrl = '$_base/api/vision/image/$analysisId';
    return VisionAnalysisResult.fromJson(json, imageUrl: imageUrl);
  }

  // ── Analyze from Bytes (paste / clipboard) ──────────────────────────────────

  /// Upload raw image bytes (e.g. from clipboard) for analysis.
  Future<VisionAnalysisResult> analyzeBytes(
    List<int> bytes,
    String mimeType, {
    String? customPrompt,
  }) async {
    final request = http.MultipartRequest('POST', Uri.parse('$_base/api/vision/analyze'));
    request.files.add(http.MultipartFile.fromBytes(
      'file',
      bytes,
      filename: 'pasted_image.png',
      contentType: MediaType.parse(mimeType),
    ));
    if (customPrompt != null && customPrompt.isNotEmpty) {
      request.fields['custom_prompt'] = customPrompt;
    }

    final streamed = await _client.send(request).timeout(_config.requestTimeout * 3);
    final res = await http.Response.fromStream(streamed);
    _checkStatus(res, '/api/vision/analyze');

    final json = jsonDecode(res.body) as Map<String, dynamic>;
    final analysisId = json['analysis_id'] as String? ?? '';
    final imageUrl = '$_base/api/vision/image/$analysisId';
    return VisionAnalysisResult.fromJson(json, imageUrl: imageUrl);
  }

  // ── Screen Capture ─────────────────────────────────────────────────────────

  /// Trigger a server-side screen capture and (optionally) analyze it.
  Future<Map<String, dynamic>> captureScreen({
    String target = 'full_screen',
    int? monitorIndex,
    String? windowId,
    List<int>? region,
    bool analyze = true,
    String? customPrompt,
  }) async {
    final body = <String, dynamic>{
      'target': target,
      'analyze': analyze,
      if (monitorIndex != null) 'monitor_index': monitorIndex,
      if (windowId != null) 'window_id': windowId,
      if (region != null) 'region': region,
      if (customPrompt != null) 'custom_prompt': customPrompt,
    };

    final res = await _client
        .post(
          Uri.parse('$_base/api/vision/capture'),
          headers: {'Content-Type': 'application/json'},
          body: jsonEncode(body),
        )
        .timeout(_config.requestTimeout * 2);
    _checkStatus(res, '/api/vision/capture');
    final json = jsonDecode(res.body) as Map<String, dynamic>;

    // If analysis was done, decorate with imageUrl
    if (json.containsKey('analysis')) {
      final analysis = json['analysis'] as Map<String, dynamic>;
      final analysisId = analysis['analysis_id'] as String? ?? '';
      analysis['imageUrl'] = '$_base/api/vision/image/$analysisId';
    }
    return json;
  }

  // ── Visual Q&A ──────────────────────────────────────────────────────────────

  /// Ask a question about a previously analyzed image.
  Future<Map<String, dynamic>> askQuestion(
    String analysisId,
    String question,
  ) async {
    final res = await _client
        .post(
          Uri.parse('$_base/api/vision/ask'),
          headers: {'Content-Type': 'application/json'},
          body: jsonEncode({'analysis_id': analysisId, 'question': question}),
        )
        .timeout(_config.requestTimeout * 2);
    _checkStatus(res, '/api/vision/ask');
    return jsonDecode(res.body) as Map<String, dynamic>;
  }

  // ── Context for Chat ────────────────────────────────────────────────────────

  /// Build a prompt-ready context string from a prior analysis.
  /// The `context_string` can be prepended to a WS CHAT_REQUEST message.
  Future<VisionContextResult> buildContext(
    String analysisId, {
    bool includeElements = true,
    bool includeOcr = true,
  }) async {
    final res = await _client
        .post(
          Uri.parse('$_base/api/vision/context'),
          headers: {'Content-Type': 'application/json'},
          body: jsonEncode({
            'analysis_id': analysisId,
            'include_elements': includeElements,
            'include_ocr': includeOcr,
          }),
        )
        .timeout(_config.requestTimeout);
    _checkStatus(res, '/api/vision/context');
    final json = jsonDecode(res.body) as Map<String, dynamic>;
    return VisionContextResult.fromJson(json);
  }

  // ── Recent Analyses ─────────────────────────────────────────────────────────

  Future<List<RecentVisionItem>> getRecentAnalyses() async {
    final res = await _client
        .get(Uri.parse('$_base/api/vision/recent'))
        .timeout(_config.requestTimeout);
    _checkStatus(res, '/api/vision/recent');
    final json = jsonDecode(res.body) as Map<String, dynamic>;
    final list = json['recent'] as List<dynamic>? ?? [];
    return list.map((e) => RecentVisionItem.fromJson(e as Map<String, dynamic>)).toList();
  }

  Future<VisionAnalysisResult> getAnalysis(String analysisId) async {
    final res = await _client
        .get(Uri.parse('$_base/api/vision/recent/$analysisId'))
        .timeout(_config.requestTimeout);
    _checkStatus(res, '/api/vision/recent/$analysisId');
    final json = jsonDecode(res.body) as Map<String, dynamic>;
    final imageUrl = '$_base/api/vision/image/$analysisId';
    return VisionAnalysisResult.fromJson(json, imageUrl: imageUrl);
  }

  Future<void> deleteAnalysis(String analysisId) async {
    await _client
        .delete(Uri.parse('$_base/api/vision/recent/$analysisId'))
        .timeout(_config.requestTimeout);
  }

  /// Returns the URL for displaying the image directly (for Image.network).
  String imageUrl(String analysisId) => '$_base/api/vision/image/$analysisId';

  // ── Private ─────────────────────────────────────────────────────────────────

  void _checkStatus(http.Response res, String path) {
    if (res.statusCode < 200 || res.statusCode >= 300) {
      String detail = res.body;
      try {
        final parsed = jsonDecode(res.body) as Map<String, dynamic>;
        detail = parsed['detail']?.toString() ?? res.body;
      } catch (_) {}
      throw Exception('Vision API $path failed (${res.statusCode}): $detail');
    }
  }

  void dispose() => _client.close();
}
