import 'dart:convert';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

import 'package:kora_desktop/core/config/app_config.dart';
import 'package:kora_desktop/core/networking/api_client.dart';
import 'package:kora_desktop/services/kora_api_service.dart';

void main() {
  group('ApiClient & KoraApiService Tests', () {
    test('Health check parses successfully', () async {
      final mockClient = MockClient((request) async {
        expect(request.url.path, '/api/health');
        return http.Response(
          jsonEncode({
            'status': 'ok',
            'version': '0.1.0',
            'uptime_seconds': 42.5,
            'models_available': 6,
          }),
          200,
        );
      });

      final apiClient = ApiClient(
        config: const AppConfig(httpBaseUrl: 'http://localhost:8765'),
        client: mockClient,
      );
      final apiService = KoraApiService(client: apiClient);

      final health = await apiService.checkHealth();
      expect(health['status'], 'ok');
      expect(health['models_available'], 6);
    });

    test('getModels parses ModelInfo records', () async {
      final mockClient = MockClient((request) async {
        expect(request.url.path, '/api/models');
        return http.Response(
          jsonEncode({
            'models': [
              {
                'name': 'qwen-chat',
                'provider': 'huggingface',
                'capabilities': ['chat'],
                'context_window': 32768,
              },
              {
                'name': 'gemma-vision',
                'provider': 'huggingface',
                'capabilities': ['vision'],
                'context_window': 131072,
              }
            ]
          }),
          200,
        );
      });

      final apiClient = ApiClient(client: mockClient);
      final apiService = KoraApiService(client: apiClient);

      final models = await apiService.getModels();
      expect(models.length, 2);
      expect(models[0].name, 'qwen-chat');
      expect(models[0].capabilities, ['chat']);
      expect(models[1].name, 'gemma-vision');
    });

    test('DuckDuckGo Web Research parses results', () async {
      final mockClient = MockClient((request) async {
        expect(request.url.path, '/api/research');
        return http.Response(
          jsonEncode({
            'query': 'Flutter Desktop',
            'results': [
              {
                'title': 'Flutter Desktop Support',
                'url': 'https://flutter.dev/desktop',
                'snippet': 'Build desktop apps with Flutter.',
                'score': 0.98,
              }
            ],
            'count': 1,
          }),
          200,
        );
      });

      final apiClient = ApiClient(client: mockClient);
      final apiService = KoraApiService(client: apiClient);

      final results = await apiService.searchWeb(query: 'Flutter Desktop');
      expect(results.length, 1);
      expect(results[0].title, 'Flutter Desktop Support');
      expect(results[0].url, 'https://flutter.dev/desktop');
    });
  });
}
