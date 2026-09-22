import 'dart:convert';
import 'package:http/http.dart' as http;
import '../config/app_config.dart';

class ApiException implements Exception {
  final String message;
  final int? statusCode;

  ApiException(this.message, [this.statusCode]);

  @override
  String toString() => 'ApiException: $message (Status: $statusCode)';
}

/// HTTP API Client for Kora Desktop backend communication
class ApiClient {
  final AppConfig config;
  final http.Client _client;

  ApiClient({
    this.config = const AppConfig(),
    http.Client? client,
  }) : _client = client ?? http.Client();

  Future<Map<String, dynamic>> get(String path, [Map<String, dynamic>? queryParams]) async {
    final uri = Uri.parse('${config.httpBaseUrl}$path').replace(
      queryParameters: queryParams?.map((k, v) => MapEntry(k, v.toString())),
    );

    try {
      final res = await _client.get(uri).timeout(config.requestTimeout);
      return _handleResponse(res);
    } catch (e) {
      if (e is ApiException) rethrow;
      throw ApiException('GET $path failed: $e');
    }
  }

  Future<Map<String, dynamic>> post(String path, Map<String, dynamic> body) async {
    final uri = Uri.parse('${config.httpBaseUrl}$path');

    try {
      final res = await _client.post(
        uri,
        headers: {'Content-Type': 'application/json'},
        body: jsonEncode(body),
      ).timeout(config.requestTimeout);
      return _handleResponse(res);
    } catch (e) {
      if (e is ApiException) rethrow;
      throw ApiException('POST $path failed: $e');
    }
  }

  Future<Map<String, dynamic>> patch(String path, Map<String, dynamic> body) async {
    final uri = Uri.parse('${config.httpBaseUrl}$path');

    try {
      final res = await _client.patch(
        uri,
        headers: {'Content-Type': 'application/json'},
        body: jsonEncode(body),
      ).timeout(config.requestTimeout);
      return _handleResponse(res);
    } catch (e) {
      if (e is ApiException) rethrow;
      throw ApiException('PATCH $path failed: $e');
    }
  }

  Future<Map<String, dynamic>> put(String path, Map<String, dynamic> body) async {
    final uri = Uri.parse('${config.httpBaseUrl}$path');

    try {
      final res = await _client.put(
        uri,
        headers: {'Content-Type': 'application/json'},
        body: jsonEncode(body),
      ).timeout(config.requestTimeout);
      return _handleResponse(res);
    } catch (e) {
      if (e is ApiException) rethrow;
      throw ApiException('PUT $path failed: $e');
    }
  }

  Future<Map<String, dynamic>> delete(String path) async {
    final uri = Uri.parse('${config.httpBaseUrl}$path');

    try {
      final res = await _client.delete(uri).timeout(config.requestTimeout);
      return _handleResponse(res);
    } catch (e) {
      if (e is ApiException) rethrow;
      throw ApiException('DELETE $path failed: $e');
    }
  }

  Map<String, dynamic> _handleResponse(http.Response res) {
    if (res.statusCode >= 200 && res.statusCode < 300) {
      if (res.body.isEmpty) return {};
      return jsonDecode(res.body) as Map<String, dynamic>;
    }
    throw ApiException('Request failed with status ${res.statusCode}: ${res.body}', res.statusCode);
  }

  void close() {
    _client.close();
  }
}
