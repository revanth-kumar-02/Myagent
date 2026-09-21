import '../core/networking/api_client.dart';
import '../models/activity_log.dart';
import '../models/memory_item.dart';
import '../models/model_info.dart';
import '../models/project.dart';
import '../models/research_result.dart';
import '../models/task_item.dart';

/// Concrete API Service for all Kora backend REST operations
class KoraApiService {
  final ApiClient _client;

  KoraApiService({ApiClient? client}) : _client = client ?? ApiClient();

  /// Health check
  Future<Map<String, dynamic>> checkHealth() async {
    return await _client.get('/api/health');
  }

  /// List registered models & capabilities
  Future<List<ModelInfo>> getModels() async {
    final res = await _client.get('/api/models');
    final list = res['models'] as List<dynamic>? ?? [];
    return list.map((e) => ModelInfo.fromJson(e as Map<String, dynamic>)).toList();
  }

  /// List projects
  Future<List<Project>> getProjects() async {
    final res = await _client.get('/api/projects');
    final list = res['projects'] as List<dynamic>? ?? [];
    return list.map((e) => Project.fromJson(e as Map<String, dynamic>)).toList();
  }

  /// Create project
  Future<Project> createProject({
    required String name,
    String description = '',
    String rootPath = '',
  }) async {
    final res = await _client.post('/api/projects', {
      'name': name,
      'description': description,
      'root_path': rootPath,
    });
    return Project.fromJson(res);
  }

  /// Delete project
  Future<void> deleteProject(String projectId) async {
    await _client.delete('/api/projects/$projectId');
  }

  /// List tasks
  Future<List<TaskItem>> getTasks() async {
    final res = await _client.get('/api/tasks');
    final list = res['tasks'] as List<dynamic>? ?? [];
    return list.map((e) => TaskItem.fromJson(e as Map<String, dynamic>)).toList();
  }

  /// List memories
  Future<List<MemoryItem>> getMemories({String? projectId}) async {
    final res = await _client.get('/api/memory', projectId != null ? {'project_id': projectId} : null);
    final list = res['memories'] as List<dynamic>? ?? [];
    return list.map((e) => MemoryItem.fromJson(e as Map<String, dynamic>)).toList();
  }

  /// Create memory
  Future<MemoryItem> createMemory({
    required String content,
    String type = 'fact',
    double confidence = 1.0,
    String? projectId,
  }) async {
    final res = await _client.post('/api/memory', {
      'content': content,
      'type': type,
      'confidence': confidence,
      if (projectId != null) 'project_id': projectId,
    });
    return MemoryItem.fromJson(res);
  }

  /// Delete memory
  Future<void> deleteMemory(String memoryId) async {
    await _client.delete('/api/memory/$memoryId');
  }

  /// Execute DuckDuckGo Web Research
  Future<List<ResearchResult>> searchWeb({required String query, int maxResults = 5}) async {
    final res = await _client.post('/api/research', {
      'query': query,
      'max_results': maxResults,
    });
    final list = res['results'] as List<dynamic>? ?? [];
    return list.map((e) => ResearchResult.fromJson(e as Map<String, dynamic>)).toList();
  }

  /// List activity logs
  Future<List<ActivityLog>> getActivityLogs() async {
    final res = await _client.get('/api/activity');
    final list = res['activity'] as List<dynamic>? ?? [];
    return list.map((e) => ActivityLog.fromJson(e as Map<String, dynamic>)).toList();
  }
}
