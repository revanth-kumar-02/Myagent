import '../core/networking/api_client.dart';
import '../models/activity_log.dart';
import '../models/automation_model.dart';
import '../models/memory_item.dart';
import '../models/model_info.dart';
import '../models/project.dart';
import '../models/research_result.dart';
import '../models/task_item.dart';
import '../models/tool_command.dart';
import '../models/system_metrics_model.dart';

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

  /// List tasks (backwards compatible)
  Future<List<TaskItem>> getTasks() async {
    final res = await _client.get('/api/tasks');
    final list = res['tasks'] as List<dynamic>? ?? [];
    return list.map((e) => TaskItem.fromJson(e as Map<String, dynamic>)).toList();
  }

  /// List automations with real metrics
  Future<Map<String, dynamic>> getAutomations({String? status}) async {
    final params = status != null ? {'status': status} : null;
    return await _client.get('/api/automations', params);
  }

  /// Create an automation
  Future<AutomationItem> createAutomation(Map<String, dynamic> data) async {
    final res = await _client.post('/api/automations', data);
    return AutomationItem.fromJson(res);
  }

  /// Update an automation
  Future<AutomationItem> updateAutomation(String id, Map<String, dynamic> data) async {
    final res = await _client.put('/api/automations/$id', data);
    return AutomationItem.fromJson(res);
  }

  /// Delete an automation
  Future<void> deleteAutomation(String id) async {
    await _client.delete('/api/automations/$id');
  }

  /// Trigger execution now
  Future<void> runAutomation(String id) async {
    await _client.post('/api/automations/$id/run', {});
  }

  /// Pause an automation schedule
  Future<void> pauseAutomation(String id) async {
    await _client.post('/api/automations/$id/pause', {});
  }

  /// Resume a paused automation
  Future<void> resumeAutomation(String id) async {
    await _client.post('/api/automations/$id/resume', {});
  }

  /// Get single automation details with execution history
  Future<AutomationItem> getAutomationDetail(String id) async {
    final res = await _client.get('/api/automations/$id');
    return AutomationItem.fromJson(res);
  }

  /// Interpret natural language prompt into structured automation
  Future<Map<String, dynamic>> interpretAutomationPrompt(String prompt) async {
    return await _client.post('/api/automations/interpret', {'prompt': prompt});
  }

  /// Retrieve curated starter templates
  Future<List<AutomationTemplate>> getAutomationTemplates() async {
    final res = await _client.get('/api/automations/templates');
    final list = res['templates'] as List<dynamic>? ?? [];
    return list.map((e) => AutomationTemplate.fromJson(e as Map<String, dynamic>)).toList();
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

  /// Update / correct memory
  Future<MemoryItem> updateMemory(
    String memoryId, {
    String? content,
    String? type,
    double? confidence,
    double? importance,
    String? status,
  }) async {
    final res = await _client.patch('/api/memory/$memoryId', {
      if (content != null) 'content': content,
      if (type != null) 'type': type,
      if (confidence != null) 'confidence': confidence,
      if (importance != null) 'importance': importance,
      if (status != null) 'status': status,
    });
    return MemoryItem.fromJson(res);
  }

  /// Toggle memory active / archived status
  Future<MemoryItem> toggleMemoryStatus(String memoryId) async {
    final res = await _client.post('/api/memory/$memoryId/toggle', {});
    return MemoryItem.fromJson(res);
  }

  /// Delete / forget memory
  Future<void> deleteMemory(String memoryId) async {
    await _client.delete('/api/memory/$memoryId');
  }

  /// Fetch Knowledge Graph entities and relationships
  Future<Map<String, dynamic>> getKnowledgeGraph({String? projectId}) async {
    return await _client.get('/api/memory/graph', projectId != null ? {'project_id': projectId} : null);
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

  /// List registered tools and slash commands
  Future<List<ToolCommand>> getTools() async {
    try {
      final res = await _client.get('/api/tools');
      final list = res['tools'] as List<dynamic>? ?? [];
      if (list.isEmpty) return defaultToolCommands;
      return list.map((e) => ToolCommand.fromJson(e as Map<String, dynamic>)).toList();
    } catch (_) {
      return defaultToolCommands;
    }
  }

  /// Fetch real-time host system resource metrics
  Future<SystemMetrics> getSystemMetrics() async {
    final res = await _client.get('/api/system/metrics');
    return SystemMetrics.fromJson(res);
  }

  /// Query host system load state
  Future<Map<String, dynamic>> getSystemLoad() async {
    return await _client.get('/api/system/load');
  }
}
