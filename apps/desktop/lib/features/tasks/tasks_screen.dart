import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/theme/app_theme.dart';
import '../../core/utils/date_formatter.dart';
import '../../models/task_item.dart';
import '../../state/tasks_state.dart';

class TasksScreen extends ConsumerWidget {
  const TasksScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final state = ref.watch(tasksProvider);
    final c = AppTheme.colors(context);

    return Container(
      color: c.bg,
      padding: const EdgeInsets.symmetric(horizontal: 28, vertical: 24),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      'Autonomous Task Board',
                      style: TextStyle(
                        fontSize: 20,
                        fontWeight: FontWeight.w800,
                        letterSpacing: -0.4,
                        color: c.textPrimary,
                      ),
                    ),
                    const SizedBox(height: 4),
                    Text(
                      'Monitor multi-step agent plans, background execution, and tool workflows.',
                      style: TextStyle(fontSize: 13, color: c.textSecondary),
                    ),
                  ],
                ),
              ),
              OutlinedButton.icon(
                icon: const Icon(Icons.refresh_rounded, size: 16),
                label: const Text('Refresh'),
                onPressed: () => ref.read(tasksProvider.notifier).loadTasks(),
              ),
            ],
          ),
          const SizedBox(height: 20),

          Expanded(
            child: state.isLoading
                ? Center(child: CircularProgressIndicator(color: c.primary))
                : state.tasks.isEmpty
                    ? Center(
                        child: Text(
                          'No background tasks currently recorded.',
                          style: TextStyle(fontSize: 13, color: c.textMuted),
                        ),
                      )
                    : ListView.builder(
                        itemCount: state.tasks.length,
                        itemBuilder: (context, index) {
                          final task = state.tasks[index];
                          final (statusBg, statusFg, icon, statusText) = _resolveTaskBadge(task.status, c);

                          return Container(
                            margin: const EdgeInsets.only(bottom: 12),
                            padding: const EdgeInsets.all(16),
                            decoration: BoxDecoration(
                              color: c.surface,
                              borderRadius: BorderRadius.circular(12),
                              border: Border.all(color: c.border, width: 1),
                              boxShadow: [
                                BoxShadow(
                                  color: Colors.black.withValues(alpha: 0.02),
                                  blurRadius: 6,
                                  offset: const Offset(0, 2),
                                ),
                              ],
                            ),
                            child: Row(
                              children: [
                                Container(
                                  padding: const EdgeInsets.all(10),
                                  decoration: BoxDecoration(
                                    color: statusBg,
                                    borderRadius: BorderRadius.circular(8),
                                  ),
                                  child: Icon(icon, color: statusFg, size: 20),
                                ),
                                const SizedBox(width: 14),
                                Expanded(
                                  child: Column(
                                    crossAxisAlignment: CrossAxisAlignment.start,
                                    children: [
                                      Text(
                                        task.title,
                                        style: TextStyle(
                                          fontSize: 14,
                                          fontWeight: FontWeight.w700,
                                          color: c.textPrimary,
                                        ),
                                      ),
                                      const SizedBox(height: 4),
                                      Text(
                                        'Category: ${task.category} • Duration: ${task.durationMs}ms • Created: ${DateFormatter.formatIso(task.createdAt)}',
                                        style: TextStyle(fontSize: 11.5, color: c.textSecondary),
                                      ),
                                    ],
                                  ),
                                ),
                                Container(
                                  padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                                  decoration: BoxDecoration(
                                    color: statusBg,
                                    borderRadius: BorderRadius.circular(6),
                                    border: Border.all(color: statusFg.withValues(alpha: 0.3)),
                                  ),
                                  child: Text(
                                    statusText,
                                    style: TextStyle(
                                      fontSize: 11,
                                      fontWeight: FontWeight.w700,
                                      color: statusFg,
                                    ),
                                  ),
                                ),
                              ],
                            ),
                          );
                        },
                      ),
          ),
        ],
      ),
    );
  }

  (Color, Color, IconData, String) _resolveTaskBadge(String status, KoraColors c) {
    final s = status.toLowerCase();
    if (s == 'completed' || s == 'done') {
      return (c.successLight, c.statusCompleted, Icons.check_circle_rounded, 'COMPLETED');
    }
    if (s == 'running' || s == 'executing') {
      return (c.primaryLight, c.statusThinking, Icons.motion_photos_on_rounded, 'RUNNING');
    }
    if (s == 'searching') {
      return (c.warningLight, c.statusSearching, Icons.travel_explore_rounded, 'SEARCHING');
    }
    if (s == 'reading') {
      return (c.primaryLight, c.statusReading, Icons.auto_stories_rounded, 'READING');
    }
    if (s == 'verifying') {
      return (c.secondaryLight, c.statusVerifying, Icons.verified_rounded, 'VERIFYING');
    }
    if (s == 'failed' || s == 'error') {
      return (c.errorLight, c.error, Icons.cancel_rounded, 'FAILED');
    }
    return (c.surfaceHighlight, c.textSecondary, Icons.schedule_rounded, s.toUpperCase());
  }
}
