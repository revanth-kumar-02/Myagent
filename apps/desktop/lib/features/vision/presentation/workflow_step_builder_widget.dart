import 'package:flutter/material.dart';

class WorkflowStepBuilderWidget extends StatelessWidget {
  final List<Map<String, dynamic>> steps;
  final Function(Map<String, dynamic> step)? onAddStep;
  final Function(int index)? onRemoveStep;

  const WorkflowStepBuilderWidget({
    super.key,
    required this.steps,
    this.onAddStep,
    this.onRemoveStep,
  });

  Color _getActionColor(String actionType) {
    switch (actionType.toLowerCase()) {
      case 'click':
      case 'double_click':
      case 'right_click':
        return Colors.blue;
      case 'type':
      case 'key_press':
        return Colors.orange;
      case 'window_switch':
        return Colors.purple;
      case 'scroll':
      case 'drag':
        return Colors.teal;
      default:
        return Colors.grey;
    }
  }

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
                    Icon(Icons.list_alt, color: theme.colorScheme.primary),
                    const SizedBox(width: 8),
                    Text(
                      'Workflow Steps (${steps.length})',
                      style: theme.textTheme.titleMedium?.copyWith(fontWeight: FontWeight.bold),
                    ),
                  ],
                ),
                TextButton.icon(
                  onPressed: () {
                    if (onAddStep != null) {
                      onAddStep!({
                        'step_id': 'step_${steps.length + 1}',
                        'name': 'Click Action',
                        'action_type': 'click',
                        'target_query': 'Submit',
                      });
                    }
                  },
                  icon: const Icon(Icons.add, size: 16),
                  label: const Text('Add Step'),
                ),
              ],
            ),
            const SizedBox(height: 12),
            if (steps.isEmpty)
              Expanded(
                child: Center(
                  child: Text(
                    'No steps in workflow. Click "Add Step" to begin building.',
                    style: theme.textTheme.bodyMedium?.copyWith(
                      color: theme.colorScheme.onSurfaceVariant,
                    ),
                  ),
                ),
              )
            else
              Expanded(
                child: ListView.separated(
                  itemCount: steps.length,
                  separatorBuilder: (context, index) => const Divider(height: 8),
                  itemBuilder: (context, index) {
                    final step = steps[index];
                    final stepName = step['name'] ?? 'Step ${index + 1}';
                    final actionType = step['action_type'] ?? 'click';
                    final target = step['target_query'] ?? step['input_text'] ?? 'Action Target';

                    return ListTile(
                      dense: true,
                      contentPadding: EdgeInsets.zero,
                      leading: CircleAvatar(
                        radius: 12,
                        backgroundColor: _getActionColor(actionType).withValues(alpha: 0.15),
                        child: Text(
                          '${index + 1}',
                          style: TextStyle(
                            fontSize: 10,
                            fontWeight: FontWeight.bold,
                            color: _getActionColor(actionType),
                          ),
                        ),
                      ),
                      title: Text(
                        stepName,
                        style: theme.textTheme.bodyMedium?.copyWith(fontWeight: FontWeight.w600),
                      ),
                      subtitle: Text(
                        '${actionType.toUpperCase()}: "$target"',
                        style: theme.textTheme.bodySmall?.copyWith(
                          color: theme.colorScheme.onSurfaceVariant,
                        ),
                      ),
                      trailing: IconButton(
                        icon: const Icon(Icons.delete_outline, size: 18),
                        onPressed: onRemoveStep != null ? () => onRemoveStep!(index) : null,
                      ),
                    );
                  },
                ),
              ),
          ],
        ),
      ),
    );
  }
}
