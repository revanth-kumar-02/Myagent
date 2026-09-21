import 'package:flutter/material.dart';

class WorkflowRunnerWidget extends StatelessWidget {
  final Map<String, dynamic>? currentWorkflow;
  final bool isRunning;
  final int currentStepIndex;
  final List<Map<String, dynamic>> executionLogs;
  final VoidCallback onRunWorkflow;
  final VoidCallback onCancelWorkflow;

  const WorkflowRunnerWidget({
    super.key,
    required this.currentWorkflow,
    required this.isRunning,
    required this.currentStepIndex,
    required this.executionLogs,
    required this.onRunWorkflow,
    required this.onCancelWorkflow,
  });

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    return Card(
      elevation: 0,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(12),
        side: BorderSide(color: theme.colorScheme.outlineVariant),
      ),
      child: Padding(
        padding: const EdgeInsets.all(16.0),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                Row(
                  children: [
                    Icon(Icons.play_circle_outline, color: theme.colorScheme.primary),
                    const SizedBox(width: 8),
                    Text(
                      'Workflow Runner & Replay',
                      style: theme.textTheme.titleMedium?.copyWith(fontWeight: FontWeight.bold),
                    ),
                  ],
                ),
                Row(
                  children: [
                    if (isRunning)
                      ElevatedButton.icon(
                        style: ElevatedButton.styleFrom(
                          backgroundColor: Colors.red.withValues(alpha: 0.1),
                          foregroundColor: Colors.red,
                        ),
                        onPressed: onCancelWorkflow,
                        icon: const Icon(Icons.stop, size: 16),
                        label: const Text('Cancel'),
                      )
                    else
                      ElevatedButton.icon(
                        onPressed: currentWorkflow != null ? onRunWorkflow : null,
                        icon: const Icon(Icons.play_arrow, size: 16),
                        label: const Text('Execute Workflow'),
                      ),
                  ],
                ),
              ],
            ),
            const SizedBox(height: 12),
            if (isRunning)
              LinearProgressIndicator(
                value: (currentWorkflow?['steps'] as List<dynamic>?)?.isNotEmpty == true
                    ? (currentStepIndex + 1) / (currentWorkflow!['steps'] as List<dynamic>).length
                    : null,
              ),
            const SizedBox(height: 12),
            Text(
              'Live Execution Logs',
              style: theme.textTheme.bodySmall?.copyWith(fontWeight: FontWeight.bold),
            ),
            const SizedBox(height: 8),
            Expanded(
              child: Container(
                padding: const EdgeInsets.all(12),
                decoration: BoxDecoration(
                  color: theme.colorScheme.surfaceContainerHighest.withValues(alpha: 0.3),
                  borderRadius: BorderRadius.circular(8),
                ),
                child: executionLogs.isEmpty
                    ? Center(
                        child: Text(
                          'No active execution logs.',
                          style: theme.textTheme.bodySmall?.copyWith(
                            color: theme.colorScheme.onSurfaceVariant,
                          ),
                        ),
                      )
                    : ListView.builder(
                        itemCount: executionLogs.length,
                        itemBuilder: (context, index) {
                          final log = executionLogs[index];
                          final isSuccess = log['verification_status'] == 'success';

                          return Padding(
                            padding: const EdgeInsets.symmetric(vertical: 4.0),
                            child: Row(
                              children: [
                                Icon(
                                  isSuccess ? Icons.check_circle : Icons.info_outline,
                                  size: 14,
                                  color: isSuccess ? Colors.green : Colors.blue,
                                ),
                                const SizedBox(width: 8),
                                Expanded(
                                  child: Text(
                                    log['message'] ?? 'Step executed',
                                    style: const TextStyle(fontFamily: 'monospace', fontSize: 11),
                                  ),
                                ),
                              ],
                            ),
                          );
                        },
                      ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
