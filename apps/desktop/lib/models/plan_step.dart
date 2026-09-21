/// Model for Planner steps in Kora Desktop

enum PlanStepStatus {
  pending,
  running,
  done,
  failed;

  static PlanStepStatus fromString(String? s) {
    return switch (s?.toLowerCase()) {
      'running' => PlanStepStatus.running,
      'done'    => PlanStepStatus.done,
      'failed'  => PlanStepStatus.failed,
      _         => PlanStepStatus.pending,
    };
  }
}

class PlanStep {
  final int index;
  final String label;
  final PlanStepStatus status;
  final String? tool;
  final String? result;

  const PlanStep({
    required this.index,
    required this.label,
    this.status = PlanStepStatus.pending,
    this.tool,
    this.result,
  });

  PlanStep copyWith({
    int? index,
    String? label,
    PlanStepStatus? status,
    String? tool,
    String? result,
  }) {
    return PlanStep(
      index: index ?? this.index,
      label: label ?? this.label,
      status: status ?? this.status,
      tool: tool ?? this.tool,
      result: result ?? this.result,
    );
  }

  factory PlanStep.fromJson(Map<String, dynamic> json) {
    return PlanStep(
      index: json['index'] as int? ?? (json['step_index'] as int? ?? 0),
      label: json['label'] as String? ?? 'Plan Step',
      status: PlanStepStatus.fromString(json['status'] as String?),
      tool: json['tool'] as String?,
      result: json['result'] as String?,
    );
  }

  Map<String, dynamic> toJson() => {
    'index': index,
    'label': label,
    'status': status.name,
    'tool': tool,
    'result': result,
  };
}
