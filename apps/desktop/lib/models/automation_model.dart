/// Automation Models for Kora Automation Center

class AutomationItem {
  final String id;
  final String name;
  final String description;
  final String goal;
  final String status;
  final String priority;
  final String triggerType;
  final Map<String, dynamic> triggerConfig;
  final List<String> allowedTools;
  final Map<String, dynamic> permissionScope;
  final String? nextRunAt;
  final String? lastRunAt;
  final String? lastResult;
  final String? lastError;
  final String createdAt;
  final String updatedAt;
  final int executionCount;
  final List<AutomationExecution> executionHistory;

  const AutomationItem({
    required this.id,
    required this.name,
    this.description = '',
    required this.goal,
    this.status = 'pending',
    this.priority = 'normal',
    this.triggerType = 'manual',
    this.triggerConfig = const {},
    this.allowedTools = const [],
    this.permissionScope = const {},
    this.nextRunAt,
    this.lastRunAt,
    this.lastResult,
    this.lastError,
    required this.createdAt,
    this.updatedAt = '',
    this.executionCount = 0,
    this.executionHistory = const [],
  });

  factory AutomationItem.fromJson(Map<String, dynamic> json) {
    final historyList = (json['execution_history'] as List<dynamic>? ?? [])
        .map((e) => AutomationExecution.fromJson(e as Map<String, dynamic>))
        .toList();

    return AutomationItem(
      id: json['id'] as String? ?? json['task_id'] as String? ?? '',
      name: json['name'] as String? ?? json['title'] as String? ?? 'Untitled Automation',
      description: json['description'] as String? ?? '',
      goal: json['goal'] as String? ?? '',
      status: json['status'] as String? ?? 'pending',
      priority: json['priority'] as String? ?? 'normal',
      triggerType: json['trigger_type'] as String? ??
          (json['trigger'] is Map ? (json['trigger']['trigger_type'] as String? ?? 'manual') : 'manual'),
      triggerConfig: json['trigger'] is Map
          ? Map<String, dynamic>.from(json['trigger'] as Map)
          : (json['trigger_config'] is Map
              ? Map<String, dynamic>.from(json['trigger_config'] as Map)
              : {}),
      allowedTools: (json['allowed_tools'] as List<dynamic>? ?? []).map((e) => e.toString()).toList(),
      permissionScope: json['permission_scope'] is Map
          ? Map<String, dynamic>.from(json['permission_scope'] as Map)
          : {},
      nextRunAt: json['next_run_at'] as String?,
      lastRunAt: json['last_run_at'] as String?,
      lastResult: json['last_result'] as String?,
      lastError: json['last_error'] as String?,
      createdAt: json['created_at'] as String? ?? '',
      updatedAt: json['updated_at'] as String? ?? '',
      executionCount: json['execution_count'] as int? ?? historyList.length,
      executionHistory: historyList,
    );
  }

  Map<String, dynamic> toJson() => {
    'id': id,
    'name': name,
    'description': description,
    'goal': goal,
    'status': status,
    'priority': priority,
    'trigger_type': triggerType,
    'trigger_config': triggerConfig,
    'allowed_tools': allowedTools,
    'permission_scope': permissionScope,
    'next_run_at': nextRunAt,
    'last_run_at': lastRunAt,
    'last_result': lastResult,
    'last_error': lastError,
    'created_at': createdAt,
    'updated_at': updatedAt,
    'execution_count': executionCount,
  };

  String get scheduleLabel {
    if (triggerConfig.containsKey('schedule_label') && triggerConfig['schedule_label'] != null) {
      return triggerConfig['schedule_label'].toString();
    }
    final tt = triggerType.toLowerCase();
    if (tt == 'interval') {
      final sec = triggerConfig['interval_seconds'] as int? ?? 60;
      if (sec >= 3600) {
        return 'Every ${sec ~/ 3600}h';
      } else if (sec >= 60) {
        return 'Every ${sec ~/ 60}m';
      }
      return 'Every ${sec}s';
    } else if (tt == 'cron') {
      final expr = triggerConfig['cron_expr']?.toString() ?? 'Daily';
      return 'Schedule: $expr';
    } else if (tt == 'event') {
      final evt = triggerConfig['event_name']?.toString() ?? 'event';
      return 'On: $evt';
    } else if (tt == 'condition') {
      return 'Conditional Trigger';
    }
    return 'Manual Trigger';
  }
}

class AutomationStep {
  final String stepId;
  final int stepIndex;
  final String goal;
  final String? toolName;
  final Map<String, dynamic> toolParams;
  final String status;
  final dynamic output;
  final String? error;
  final int durationMs;
  final bool verified;
  final String? verificationFeedback;

  const AutomationStep({
    required this.stepId,
    required this.stepIndex,
    required this.goal,
    this.toolName,
    this.toolParams = const {},
    this.status = 'pending',
    this.output,
    this.error,
    this.durationMs = 0,
    this.verified = false,
    this.verificationFeedback,
  });

  factory AutomationStep.fromJson(Map<String, dynamic> json) {
    return AutomationStep(
      stepId: json['step_id'] as String? ?? '',
      stepIndex: json['step_index'] as int? ?? 0,
      goal: json['goal'] as String? ?? '',
      toolName: json['tool_name'] as String?,
      toolParams: json['tool_params'] is Map ? Map<String, dynamic>.from(json['tool_params'] as Map) : {},
      status: json['status'] as String? ?? 'pending',
      output: json['output'],
      error: json['error'] as String?,
      durationMs: json['duration_ms'] as int? ?? 0,
      verified: json['verified'] as bool? ?? false,
      verificationFeedback: json['verification_feedback'] as String?,
    );
  }
}

class AutomationExecution {
  final String runId;
  final String taskId;
  final int runNumber;
  final String status;
  final String startedAt;
  final String? completedAt;
  final int durationMs;
  final int stepsCompleted;
  final int retriesCount;
  final int replanCount;
  final String? error;
  final String triggerSource;
  final String modelUsed;
  final List<Map<String, dynamic>> plan;
  final dynamic result;
  final List<AutomationStep> steps;

  const AutomationExecution({
    required this.runId,
    required this.taskId,
    this.runNumber = 1,
    this.status = 'pending',
    required this.startedAt,
    this.completedAt,
    this.durationMs = 0,
    this.stepsCompleted = 0,
    this.retriesCount = 0,
    this.replanCount = 0,
    this.error,
    this.triggerSource = 'manual',
    this.modelUsed = 'Local AI: qwen3:1.7b',
    this.plan = const [],
    this.result,
    this.steps = const [],
  });

  factory AutomationExecution.fromJson(Map<String, dynamic> json) {
    final stepsList = (json['steps'] as List<dynamic>? ?? [])
        .map((e) => AutomationStep.fromJson(e as Map<String, dynamic>))
        .toList();

    final rawPlan = json['plan'] as List<dynamic>? ?? [];
    final planList = rawPlan
        .whereType<Map>()
        .map((e) => Map<String, dynamic>.from(e))
        .toList();

    return AutomationExecution(
      runId: json['run_id'] as String? ?? '',
      taskId: json['task_id'] as String? ?? '',
      runNumber: json['run_number'] as int? ?? 1,
      status: json['status'] as String? ?? 'pending',
      startedAt: json['started_at'] as String? ?? '',
      completedAt: json['completed_at'] as String?,
      durationMs: json['duration_ms'] as int? ?? 0,
      stepsCompleted: json['steps_completed'] as int? ?? stepsList.length,
      retriesCount: json['retries_count'] as int? ?? 0,
      replanCount: json['replan_count'] as int? ?? 0,
      error: json['error'] as String?,
      triggerSource: json['trigger_source'] as String? ?? 'manual',
      modelUsed: json['model_used'] as String? ?? 'Local AI: qwen3:1.7b',
      plan: planList,
      result: json['result'],
      steps: stepsList,
    );
  }
}

class AutomationTemplate {
  final String id;
  final String category;
  final String name;
  final String description;
  final String goal;
  final String triggerType;
  final Map<String, dynamic> triggerConfig;
  final List<String> allowedTools;
  final List<String> plannedActions;

  const AutomationTemplate({
    required this.id,
    required this.category,
    required this.name,
    required this.description,
    required this.goal,
    required this.triggerType,
    required this.triggerConfig,
    required this.allowedTools,
    required this.plannedActions,
  });

  factory AutomationTemplate.fromJson(Map<String, dynamic> json) {
    return AutomationTemplate(
      id: json['id'] as String? ?? '',
      category: json['category'] as String? ?? 'GENERAL',
      name: json['name'] as String? ?? '',
      description: json['description'] as String? ?? '',
      goal: json['goal'] as String? ?? '',
      triggerType: json['trigger_type'] as String? ?? 'manual',
      triggerConfig: json['trigger_config'] is Map ? Map<String, dynamic>.from(json['trigger_config'] as Map) : {},
      allowedTools: (json['allowed_tools'] as List<dynamic>? ?? []).map((e) => e.toString()).toList(),
      plannedActions: (json['planned_actions'] as List<dynamic>? ?? []).map((e) => e.toString()).toList(),
    );
  }
}
