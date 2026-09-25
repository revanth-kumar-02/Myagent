import 'dart:async';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../models/automation_model.dart';
import '../models/task_item.dart';
import '../services/kora_api_service.dart';
import '../services/kora_socket_service.dart';
import '../shared/protocol/message_types.dart';
import '../shared/protocol/ws_message.dart';
import 'connection_state.dart';

class TasksState {
  final List<AutomationItem> automations;
  final List<TaskItem> tasks;
  final Map<String, int> summary;
  final AutomationItem? selectedAutomation;
  final AutomationExecution? liveExecution;
  final List<AutomationTemplate> templates;
  final String activeFilter;
  final bool isInterpreting;
  final Map<String, dynamic>? interpretedDraft;
  final bool isLoading;
  final String? errorMessage;

  const TasksState({
    this.automations = const [],
    this.tasks = const [],
    this.summary = const {
      'total': 0,
      'active': 0,
      'running': 0,
      'scheduled': 0,
      'failed': 0,
      'completed': 0,
    },
    this.selectedAutomation,
    this.liveExecution,
    this.templates = const [],
    this.activeFilter = 'ALL',
    this.isInterpreting = false,
    this.interpretedDraft,
    this.isLoading = false,
    this.errorMessage,
  });

  TasksState copyWith({
    List<AutomationItem>? automations,
    List<TaskItem>? tasks,
    Map<String, int>? summary,
    AutomationItem? selectedAutomation,
    bool clearSelectedAutomation = false,
    AutomationExecution? liveExecution,
    bool clearLiveExecution = false,
    List<AutomationTemplate>? templates,
    String? activeFilter,
    bool? isInterpreting,
    Map<String, dynamic>? interpretedDraft,
    bool clearInterpretedDraft = false,
    bool? isLoading,
    String? errorMessage,
  }) {
    return TasksState(
      automations: automations ?? this.automations,
      tasks: tasks ?? this.tasks,
      summary: summary ?? this.summary,
      selectedAutomation: clearSelectedAutomation ? null : (selectedAutomation ?? this.selectedAutomation),
      liveExecution: clearLiveExecution ? null : (liveExecution ?? this.liveExecution),
      templates: templates ?? this.templates,
      activeFilter: activeFilter ?? this.activeFilter,
      isInterpreting: isInterpreting ?? this.isInterpreting,
      interpretedDraft: clearInterpretedDraft ? null : (interpretedDraft ?? this.interpretedDraft),
      isLoading: isLoading ?? this.isLoading,
      errorMessage: errorMessage ?? this.errorMessage,
    );
  }

  List<AutomationItem> get filteredAutomations {
    switch (activeFilter.toUpperCase()) {
      case 'ACTIVE':
        return automations.where((a) => a.status.toLowerCase() == 'active' || a.status.toLowerCase() == 'pending').toList();
      case 'RUNNING':
        return automations.where((a) => a.status.toLowerCase() == 'running').toList();
      case 'SCHEDULED':
        return automations.where((a) => a.nextRunAt != null && a.status.toLowerCase() != 'paused').toList();
      case 'COMPLETED':
        return automations.where((a) => a.status.toLowerCase() == 'completed').toList();
      case 'PAUSED':
        return automations.where((a) => a.status.toLowerCase() == 'paused').toList();
      case 'FAILED':
        return automations.where((a) => a.status.toLowerCase() == 'failed').toList();
      default:
        return automations;
    }
  }
}

class TasksNotifier extends StateNotifier<TasksState> {
  final KoraApiService _apiService;
  final KoraSocketService? _socketService;
  StreamSubscription<WsMessage>? _socketSubscription;

  TasksNotifier(this._apiService, [this._socketService]) : super(const TasksState()) {
    loadAutomations();
    loadTemplates();
    _initSocketListener();
  }

  void _initSocketListener() {
    if (_socketService == null) return;
    _socketSubscription = _socketService!.messages.listen(_handleWebSocketMessage);
  }

  @override
  void dispose() {
    _socketSubscription?.cancel();
    super.dispose();
  }

  void _handleWebSocketMessage(WsMessage msg) {
    final payload = msg.payload;
    final taskId = payload['task_id']?.toString() ?? payload['taskId']?.toString();

    switch (msg.type) {
      case WsMessageType.automationStarted:
        final runId = payload['run_id']?.toString() ?? '';
        final modelUsed = payload['model_used']?.toString() ?? 'qwen3:1.7b';
        final startedAt = payload['started_at']?.toString() ?? DateTime.now().toIso8601String();

        // Update list status to running
        if (taskId != null) {
          final updated = state.automations.map((a) {
            if (a.id == taskId) {
              return AutomationItem.fromJson({
                ...a.toJson(),
                'status': 'running',
              });
            }
            return a;
          }).toList();

          state = state.copyWith(
            automations: updated,
            liveExecution: AutomationExecution(
              runId: runId,
              taskId: taskId,
              status: 'running',
              startedAt: startedAt,
              modelUsed: modelUsed,
            ),
          );
        }
        break;

      case WsMessageType.automationPlan:
        if (state.liveExecution != null && taskId == state.liveExecution!.taskId) {
          final rawSteps = payload['steps'] as List<dynamic>? ?? [];
          final planList = rawSteps.whereType<Map>().map((e) => Map<String, dynamic>.from(e)).toList();
          state = state.copyWith(
            liveExecution: AutomationExecution(
              runId: state.liveExecution!.runId,
              taskId: state.liveExecution!.taskId,
              status: state.liveExecution!.status,
              startedAt: state.liveExecution!.startedAt,
              modelUsed: state.liveExecution!.modelUsed,
              plan: planList,
              steps: state.liveExecution!.steps,
            ),
          );
        }
        break;

      case WsMessageType.automationStepStart:
        if (state.liveExecution != null && taskId == state.liveExecution!.taskId) {
          final stepIndex = payload['step_index'] as int? ?? (state.liveExecution!.steps.length + 1);
          final stepGoal = payload['goal']?.toString() ?? 'Executing step';
          final toolName = payload['tool_name']?.toString();

          final currentSteps = List<AutomationStep>.from(state.liveExecution!.steps);
          currentSteps.add(AutomationStep(
            stepId: 'step-$stepIndex',
            stepIndex: stepIndex,
            goal: stepGoal,
            toolName: toolName,
            status: 'running',
          ));

          state = state.copyWith(
            liveExecution: AutomationExecution(
              runId: state.liveExecution!.runId,
              taskId: state.liveExecution!.taskId,
              status: state.liveExecution!.status,
              startedAt: state.liveExecution!.startedAt,
              modelUsed: state.liveExecution!.modelUsed,
              plan: state.liveExecution!.plan,
              steps: currentSteps,
            ),
          );
        }
        break;

      case WsMessageType.automationStepFinish:
        if (state.liveExecution != null && taskId == state.liveExecution!.taskId) {
          final stepIndex = payload['step_index'] as int? ?? 1;
          final status = payload['status']?.toString() ?? 'completed';
          final output = payload['output'];
          final error = payload['error']?.toString();
          final durationMs = payload['duration_ms'] as int? ?? 0;

          final updatedSteps = state.liveExecution!.steps.map((s) {
            if (s.stepIndex == stepIndex) {
              return AutomationStep(
                stepId: s.stepId,
                stepIndex: s.stepIndex,
                goal: s.goal,
                toolName: s.toolName,
                toolParams: s.toolParams,
                status: status,
                output: output,
                error: error,
                durationMs: durationMs,
                verified: status == 'completed',
              );
            }
            return s;
          }).toList();

          state = state.copyWith(
            liveExecution: AutomationExecution(
              runId: state.liveExecution!.runId,
              taskId: state.liveExecution!.taskId,
              status: state.liveExecution!.status,
              startedAt: state.liveExecution!.startedAt,
              modelUsed: state.liveExecution!.modelUsed,
              plan: state.liveExecution!.plan,
              steps: updatedSteps,
            ),
          );
        }
        break;

      case WsMessageType.automationCompleted:
      case WsMessageType.automationFailed:
        final status = msg.type == WsMessageType.automationCompleted ? 'completed' : 'failed';
        final result = payload['result'];
        final error = payload['error']?.toString();
        final durationMs = payload['duration_ms'] as int? ?? 0;

        if (state.liveExecution != null && taskId == state.liveExecution!.taskId) {
          state = state.copyWith(
            liveExecution: AutomationExecution(
              runId: state.liveExecution!.runId,
              taskId: state.liveExecution!.taskId,
              status: status,
              startedAt: state.liveExecution!.startedAt,
              completedAt: DateTime.now().toIso8601String(),
              durationMs: durationMs,
              modelUsed: state.liveExecution!.modelUsed,
              plan: state.liveExecution!.plan,
              result: result,
              error: error,
              steps: state.liveExecution!.steps,
            ),
          );
        }

        // Refresh automations list silently to reflect real persistent DB state
        loadAutomations(silent: true);
        break;

      default:
        break;
    }
  }

  Future<void> loadAutomations({bool silent = false}) async {
    if (!silent) {
      state = state.copyWith(isLoading: true, errorMessage: null);
    }
    try {
      final res = await _apiService.getAutomations();
      final listRaw = res['automations'] as List<dynamic>? ?? [];
      final automations = listRaw.map((e) => AutomationItem.fromJson(e as Map<String, dynamic>)).toList();
      
      final summaryRaw = res['summary'] as Map<String, dynamic>? ?? {};
      final summary = {
        'total': summaryRaw['total'] as int? ?? automations.length,
        'active': summaryRaw['active'] as int? ?? 0,
        'running': summaryRaw['running'] as int? ?? 0,
        'scheduled': summaryRaw['scheduled'] as int? ?? 0,
        'failed': summaryRaw['failed'] as int? ?? 0,
        'completed': summaryRaw['completed'] as int? ?? 0,
      };

      // Compatibility tasks list
      final tasks = automations.map((a) => TaskItem(
        id: a.id,
        title: a.name,
        status: a.status,
        category: a.allowedTools.isNotEmpty ? a.allowedTools.first : 'General',
        durationMs: 0,
        createdAt: a.createdAt,
      )).toList();

      AutomationItem? updatedSelected = state.selectedAutomation;
      if (updatedSelected != null) {
        final match = automations.where((a) => a.id == updatedSelected!.id).firstOrNull;
        if (match != null) updatedSelected = match;
      }

      state = state.copyWith(
        automations: automations,
        tasks: tasks,
        summary: summary,
        selectedAutomation: updatedSelected,
        isLoading: false,
      );
    } catch (e) {
      state = state.copyWith(isLoading: false, errorMessage: e.toString());
    }
  }

  Future<void> loadTemplates() async {
    try {
      final templates = await _apiService.getAutomationTemplates();
      state = state.copyWith(templates: templates);
    } catch (_) {}
  }

  void setFilter(String filter) {
    state = state.copyWith(activeFilter: filter);
  }

  Future<void> selectAutomation(AutomationItem? item) async {
    if (item == null) {
      state = state.copyWith(clearSelectedAutomation: true, clearLiveExecution: true);
      return;
    }
    state = state.copyWith(selectedAutomation: item, clearLiveExecution: true);
    try {
      final detail = await _apiService.getAutomationDetail(item.id);
      state = state.copyWith(selectedAutomation: detail);
    } catch (_) {}
  }

  Future<AutomationItem?> createAutomation(Map<String, dynamic> data) async {
    state = state.copyWith(isLoading: true, errorMessage: null);
    try {
      final item = await _apiService.createAutomation(data);
      await loadAutomations(silent: true);
      state = state.copyWith(isLoading: false, clearInterpretedDraft: true);
      return item;
    } catch (e) {
      state = state.copyWith(isLoading: false, errorMessage: e.toString());
      return null;
    }
  }

  Future<void> deleteAutomation(String id) async {
    try {
      await _apiService.deleteAutomation(id);
      if (state.selectedAutomation?.id == id) {
        state = state.copyWith(clearSelectedAutomation: true, clearLiveExecution: true);
      }
      await loadAutomations(silent: true);
    } catch (e) {
      state = state.copyWith(errorMessage: e.toString());
    }
  }

  Future<void> runAutomation(String id) async {
    try {
      await _apiService.runAutomation(id);
      // Give backend a moment to transition to running
      await Future.delayed(const Duration(milliseconds: 150));
      await loadAutomations(silent: true);
    } catch (e) {
      state = state.copyWith(errorMessage: e.toString());
    }
  }

  Future<void> pauseAutomation(String id) async {
    try {
      await _apiService.pauseAutomation(id);
      await loadAutomations(silent: true);
    } catch (e) {
      state = state.copyWith(errorMessage: e.toString());
    }
  }

  Future<void> resumeAutomation(String id) async {
    try {
      await _apiService.resumeAutomation(id);
      await loadAutomations(silent: true);
    } catch (e) {
      state = state.copyWith(errorMessage: e.toString());
    }
  }

  Future<void> interpretPrompt(String prompt) async {
    state = state.copyWith(isInterpreting: true, errorMessage: null);
    try {
      final res = await _apiService.interpretAutomationPrompt(prompt);
      state = state.copyWith(
        isInterpreting: false,
        interpretedDraft: res,
      );
    } catch (e) {
      state = state.copyWith(isInterpreting: false, errorMessage: e.toString());
    }
  }

  void clearInterpretedDraft() {
    state = state.copyWith(clearInterpretedDraft: true);
  }

  // Backwards compatibility loadTasks
  Future<void> loadTasks() => loadAutomations();
}

final tasksProvider = StateNotifierProvider<TasksNotifier, TasksState>((ref) {
  final api = ref.watch(apiServiceProvider);
  final socket = ref.watch(socketServiceProvider);
  return TasksNotifier(api, socket);
});
