import 'package:flutter/material.dart';

class VisualActionHistoryWidget extends StatelessWidget {
  final List<Map<String, dynamic>> actions;

  const VisualActionHistoryWidget({
    super.key,
    required this.actions,
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
              children: [
                Icon(Icons.history, color: theme.colorScheme.primary),
                const SizedBox(width: 8),
                Text(
                  'Visual Action & Verification History',
                  style: theme.textTheme.titleMedium?.copyWith(fontWeight: FontWeight.bold),
                ),
              ],
            ),
            const SizedBox(height: 12),
            if (actions.isEmpty)
              Expanded(
                child: Center(
                  child: Text(
                    'No visual computer control actions executed yet.',
                    style: theme.textTheme.bodyMedium?.copyWith(
                      color: theme.colorScheme.onSurfaceVariant,
                    ),
                  ),
                ),
              )
            else
              Expanded(
                child: ListView.separated(
                  itemCount: actions.length,
                  separatorBuilder: (context, index) => const Divider(height: 8),
                  itemBuilder: (context, index) {
                    final act = actions[index];
                    final actionType = act['action_type'] ?? 'action';
                    final target = act['target_label'] ?? 'target';
                    final status = act['verification_status'] ?? 'unknown';
                    final coords = act['coordinates'] ?? [0, 0];
                    final isSuccess = status == 'success';

                    return ListTile(
                      dense: true,
                      contentPadding: EdgeInsets.zero,
                      leading: Icon(
                        isSuccess ? Icons.check_circle : Icons.error_outline,
                        color: isSuccess ? Colors.green : Colors.red,
                        size: 20,
                      ),
                      title: Text(
                        '${actionType.toUpperCase()} "$target" at (${coords[0]}, ${coords[1]})',
                        style: theme.textTheme.bodyMedium?.copyWith(fontWeight: FontWeight.w600),
                      ),
                      subtitle: Text(
                        'Verification: ${status.toUpperCase()}',
                        style: theme.textTheme.bodySmall?.copyWith(
                          color: isSuccess ? Colors.green : Colors.red,
                        ),
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
