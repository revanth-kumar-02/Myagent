import 'dart:async';
import 'dart:convert';
import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:http/http.dart' as http;
import '../models/chat_message.dart';

/// Direct Ollama Client for offline chat when the Python/FastAPI backend is not running.
class OllamaDirectService {
  final String baseUrl;
  final String defaultModel;

  OllamaDirectService({
    this.baseUrl = 'http://127.0.0.1:11434',
    this.defaultModel = 'qwen3:1.7b',
  });

  /// Check if Ollama is accessible.
  Future<bool> isAvailable() async {
    try {
      final res = await http.get(Uri.parse('$baseUrl/api/tags')).timeout(const Duration(seconds: 2));
      return res.statusCode == 200;
    } catch (_) {
      return false;
    }
  }

  /// Discover available models from Ollama daemon.
  Future<List<String>> getModels() async {
    try {
      final res = await http.get(Uri.parse('$baseUrl/api/tags')).timeout(const Duration(seconds: 2));
      if (res.statusCode == 200) {
        final data = jsonDecode(res.body) as Map<String, dynamic>;
        final models = data['models'] as List<dynamic>?;
        if (models != null) {
          return models.map((m) => (m['name'] ?? m['model']).toString()).toList();
        }
      }
    } catch (_) {}
    return [defaultModel];
  }

  /// Stream chat completion directly from Ollama.
  Stream<String> streamChat({
    required List<ChatMessage> history,
    required String prompt,
    String? modelOverride,
  }) async* {
    final client = http.Client();
    final modelName = modelOverride ?? defaultModel;

    try {
      final messages = <Map<String, String>>[];
      // Include recent conversation context (last 8 turns)
      for (final m in history.take(8)) {
        if (m.content.isNotEmpty && (m.role == MessageRole.user || m.role == MessageRole.assistant)) {
          messages.add({
            'role': m.role == MessageRole.user ? 'user' : 'assistant',
            'content': m.content,
          });
        }
      }
      messages.add({'role': 'user', 'content': prompt});

      final request = http.Request('POST', Uri.parse('$baseUrl/api/chat'));
      request.headers['Content-Type'] = 'application/json';
      request.body = jsonEncode({
        'model': modelName,
        'messages': messages,
        'stream': true,
      });

      debugPrint('[OllamaDirectService] Streaming chat from Ollama ($modelName)...');
      final response = await client.send(request);
      if (response.statusCode != 200) {
        final body = await response.stream.bytesToString();
        throw Exception('Ollama error (${response.statusCode}): $body');
      }

      await for (final line in response.stream.transform(utf8.decoder).transform(const LineSplitter())) {
        if (line.trim().isEmpty) continue;
        try {
          final data = jsonDecode(line) as Map<String, dynamic>;
          final msg = data['message'] as Map<String, dynamic>?;
          final content = msg?['content'] as String?;
          if (content != null && content.isNotEmpty) {
            yield content;
          }
        } catch (_) {}
      }
    } finally {
      client.close();
    }
  }
}

final ollamaDirectServiceProvider = Provider<OllamaDirectService>((ref) {
  return OllamaDirectService();
});
