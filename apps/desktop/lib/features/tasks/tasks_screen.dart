import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/theme/app_theme.dart';
import '../../core/utils/date_formatter.dart';
import '../../models/automation_model.dart';
import '../../state/tasks_state.dart';

class TasksScreen extends ConsumerStatefulWidget {
  const TasksScreen({super.key});

  @override
  ConsumerState<TasksScreen> createState() => _TasksScreenState();
}

class _TasksScreenState extends ConsumerState<TasksScreen> {
  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      ref.read(tasksProvider.notifier).loadAutomations();
    });
  }

  @override
  Widget build(BuildContext context) {
    final state = ref.watch(tasksProvider);
    final c = AppTheme.colors(context);

    return Container(
      color: c.bg,
      padding: const EdgeInsets.symmetric(horizontal: 28, vertical: 24),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // ── Header ────────────────────────────────────────────────────────
          Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      'Kora Automation Center',
                      style: TextStyle(
                        fontSize: 22,
                        fontWeight: FontWeight.w800,
                        letterSpacing: -0.4,
                        color: c.textPrimary,
                      ),
                    ),
                    const SizedBox(height: 4),
                    Text(
                      'Autonomous background workflows, scheduled triggers, and dynamic agent jobs.',
                      style: TextStyle(fontSize: 13, color: c.textSecondary),
                    ),
                  ],
                ),
              ),
              OutlinedButton.icon(
                icon: const Icon(Icons.refresh_rounded, size: 16),
                label: const Text('Refresh'),
                style: OutlinedButton.styleFrom(
                  foregroundColor: c.textPrimary,
                  side: BorderSide(color: c.border),
                  padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
                  shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
                ),
                onPressed: () => ref.read(tasksProvider.notifier).loadAutomations(),
              ),
              const SizedBox(width: 10),
              ElevatedButton.icon(
                icon: const Icon(Icons.add_rounded, size: 18),
                label: const Text('+ New Automation'),
                style: ElevatedButton.styleFrom(
                  backgroundColor: c.primary,
                  foregroundColor: Colors.white,
                  padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
                  shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
                  elevation: 0,
                ),
                onPressed: () => _openNewAutomationDialog(context),
              ),
            ],
          ),
          const SizedBox(height: 20),

          // ── Summary Metrics Bar ──────────────────────────────────────────
          _buildMetricsBar(state, c),
          const SizedBox(height: 16),

          // ── Filter Chips ─────────────────────────────────────────────────
          _buildFilterBar(state, c),
          const SizedBox(height: 16),

          // ── Automations List or Empty State ──────────────────────────────
          Expanded(
            child: state.isLoading && state.automations.isEmpty
                ? Center(child: CircularProgressIndicator(color: c.primary))
                : state.filteredAutomations.isEmpty
                    ? _buildEmptyState(state, c)
                    : ListView.builder(
                        itemCount: state.filteredAutomations.length,
                        itemBuilder: (context, index) {
                          final auto = state.filteredAutomations[index];
                          return _buildAutomationCard(auto, c);
                        },
                      ),
          ),
        ],
      ),
    );
  }

  // ── Metrics Bar ───────────────────────────────────────────────────────────
  Widget _buildMetricsBar(TasksState state, KoraColors c) {
    final s = state.summary;
    return Row(
      children: [
        _buildMetricCard('Active', s['active'] ?? 0, c.successLight, c.statusCompleted, Icons.play_circle_outline_rounded, 'ACTIVE'),
        const SizedBox(width: 12),
        _buildMetricCard('Running', s['running'] ?? 0, c.primaryLight, c.primary, Icons.motion_photos_on_rounded, 'RUNNING'),
        const SizedBox(width: 12),
        _buildMetricCard('Scheduled', s['scheduled'] ?? 0, c.surfaceHighlight, c.textPrimary, Icons.schedule_rounded, 'SCHEDULED'),
        const SizedBox(width: 12),
        _buildMetricCard('Failed', s['failed'] ?? 0, c.errorLight, c.error, Icons.error_outline_rounded, 'FAILED'),
        const SizedBox(width: 12),
        _buildMetricCard('Completed', s['completed'] ?? 0, c.secondaryLight, c.secondary, Icons.check_circle_outline_rounded, 'COMPLETED'),
      ],
    );
  }

  Widget _buildMetricCard(String label, int count, Color bg, Color fg, IconData icon, String filterKey) {
    final isSelected = ref.watch(tasksProvider).activeFilter == filterKey;
    final c = AppTheme.colors(context);

    return Expanded(
      child: InkWell(
        onTap: () => ref.read(tasksProvider.notifier).setFilter(isSelected ? 'ALL' : filterKey),
        borderRadius: BorderRadius.circular(10),
        child: Container(
          padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 10),
          decoration: BoxDecoration(
            color: isSelected ? bg : c.surface,
            borderRadius: BorderRadius.circular(10),
            border: Border.all(
              color: isSelected ? fg.withValues(alpha: 0.6) : c.border,
              width: isSelected ? 1.5 : 1,
            ),
          ),
          child: Row(
            children: [
              Container(
                padding: const EdgeInsets.all(6),
                decoration: BoxDecoration(color: bg, borderRadius: BorderRadius.circular(6)),
                child: Icon(icon, color: fg, size: 16),
              ),
              const SizedBox(width: 8),
              Flexible(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Text(
                      count.toString(),
                      style: TextStyle(
                        fontSize: 15,
                        fontWeight: FontWeight.w800,
                        color: c.textPrimary,
                      ),
                    ),
                    Text(
                      label,
                      style: TextStyle(fontSize: 10.5, color: c.textSecondary, fontWeight: FontWeight.w600),
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                    ),
                  ],
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  // ── Filter Bar ────────────────────────────────────────────────────────────
  Widget _buildFilterBar(TasksState state, KoraColors c) {
    const filters = ['ALL', 'ACTIVE', 'RUNNING', 'SCHEDULED', 'PAUSED', 'COMPLETED', 'FAILED'];
    return SingleChildScrollView(
      scrollDirection: Axis.horizontal,
      child: Row(
        children: filters.map((f) {
          final isSelected = state.activeFilter == f;
          return Padding(
            padding: const EdgeInsets.only(right: 8),
            child: FilterChip(
              label: Text(f),
              selected: isSelected,
              onSelected: (_) => ref.read(tasksProvider.notifier).setFilter(f),
              backgroundColor: c.surface,
              selectedColor: c.primaryLight,
              checkmarkColor: c.primary,
              labelStyle: TextStyle(
                fontSize: 11.5,
                fontWeight: isSelected ? FontWeight.w700 : FontWeight.w500,
                color: isSelected ? c.primary : c.textSecondary,
              ),
              side: BorderSide(color: isSelected ? c.primary.withValues(alpha: 0.4) : c.border),
              shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(6)),
            ),
          );
        }).toList(),
      ),
    );
  }

  // ── Automation Card ───────────────────────────────────────────────────────
  Widget _buildAutomationCard(AutomationItem auto, KoraColors c) {
    final (statusBg, statusFg, statusIcon, statusText) = _resolveStatus(auto.status, c);

    return Container(
      margin: const EdgeInsets.only(bottom: 12),
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
      child: InkWell(
        onTap: () => _openDetailDialog(context, auto),
        borderRadius: BorderRadius.circular(12),
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              // Top Row: Title, Trigger Badge, Status Badge
              Row(
                children: [
                  Container(
                    padding: const EdgeInsets.all(8),
                    decoration: BoxDecoration(
                      color: statusBg,
                      borderRadius: BorderRadius.circular(8),
                    ),
                    child: Icon(statusIcon, color: statusFg, size: 18),
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Row(
                          children: [
                            Text(
                              auto.name,
                              style: TextStyle(
                                fontSize: 14.5,
                                fontWeight: FontWeight.w700,
                                color: c.textPrimary,
                              ),
                            ),
                            const SizedBox(width: 8),
                            Container(
                              padding: const EdgeInsets.symmetric(horizontal: 7, vertical: 2),
                              decoration: BoxDecoration(
                                color: c.surfaceHighlight,
                                borderRadius: BorderRadius.circular(4),
                                border: Border.all(color: c.border),
                              ),
                              child: Text(
                                auto.scheduleLabel,
                                style: TextStyle(fontSize: 10.5, fontWeight: FontWeight.w600, color: c.textSecondary),
                              ),
                            ),
                          ],
                        ),
                        if (auto.description.isNotEmpty) ...[
                          const SizedBox(height: 2),
                          Text(
                            auto.description,
                            style: TextStyle(fontSize: 12, color: c.textSecondary),
                            maxLines: 1,
                            overflow: TextOverflow.ellipsis,
                          ),
                        ],
                      ],
                    ),
                  ),
                  // Status Badge
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
              const SizedBox(height: 12),

              // Goal box
              Container(
                width: double.infinity,
                padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
                decoration: BoxDecoration(
                  color: c.surfaceHighlight.withValues(alpha: 0.5),
                  borderRadius: BorderRadius.circular(6),
                ),
                child: Text(
                  'Goal: ${auto.goal}',
                  style: TextStyle(fontSize: 11.5, color: c.textPrimary, fontStyle: FontStyle.italic),
                  maxLines: 2,
                  overflow: TextOverflow.ellipsis,
                ),
              ),
              const SizedBox(height: 10),

              // Timings & Tools
              Row(
                children: [
                  if (auto.allowedTools.isNotEmpty) ...[
                    Wrap(
                      spacing: 4,
                      children: auto.allowedTools.map((t) {
                        return Container(
                          padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                          decoration: BoxDecoration(
                            color: c.surfaceTertiary,
                            borderRadius: BorderRadius.circular(4),
                          ),
                          child: Text(
                            t,
                            style: TextStyle(fontSize: 10, fontWeight: FontWeight.w600, color: c.textSecondary),
                          ),
                        );
                      }).toList(),
                    ),
                    const SizedBox(width: 12),
                  ],
                  if (auto.nextRunAt != null) ...[
                    Icon(Icons.timer_outlined, size: 13, color: c.textMuted),
                    const SizedBox(width: 4),
                    Text(
                      'Next run: ${DateFormatter.formatIso(auto.nextRunAt!)}',
                      style: TextStyle(fontSize: 11, color: c.textSecondary),
                    ),
                    const SizedBox(width: 12),
                  ],
                  if (auto.lastRunAt != null) ...[
                    Icon(Icons.history_rounded, size: 13, color: c.textMuted),
                    const SizedBox(width: 4),
                    Text(
                      'Last run: ${DateFormatter.formatIso(auto.lastRunAt!)}',
                      style: TextStyle(fontSize: 11, color: c.textSecondary),
                    ),
                  ],
                  const Spacer(),

                  // Actions
                  IconButton(
                    icon: const Icon(Icons.play_arrow_rounded, size: 18),
                    tooltip: 'Run now',
                    color: c.primary,
                    onPressed: () => ref.read(tasksProvider.notifier).runAutomation(auto.id),
                  ),
                  if (auto.status.toLowerCase() == 'paused')
                    IconButton(
                      icon: const Icon(Icons.play_circle_outline_rounded, size: 18),
                      tooltip: 'Resume',
                      color: c.statusCompleted,
                      onPressed: () => ref.read(tasksProvider.notifier).resumeAutomation(auto.id),
                    )
                  else
                    IconButton(
                      icon: const Icon(Icons.pause_circle_outline_rounded, size: 18),
                      tooltip: 'Pause',
                      color: c.warning,
                      onPressed: () => ref.read(tasksProvider.notifier).pauseAutomation(auto.id),
                    ),
                  IconButton(
                    icon: const Icon(Icons.info_outline_rounded, size: 18),
                    tooltip: 'View Trace & History',
                    color: c.textSecondary,
                    onPressed: () => _openDetailDialog(context, auto),
                  ),
                  IconButton(
                    icon: const Icon(Icons.delete_outline_rounded, size: 18),
                    tooltip: 'Delete',
                    color: c.error,
                    onPressed: () => _confirmDelete(context, auto),
                  ),
                ],
              ),
            ],
          ),
        ),
      ),
    );
  }

  // ── Empty State ───────────────────────────────────────────────────────────
  Widget _buildEmptyState(TasksState state, KoraColors c) {
    return Center(
      child: SingleChildScrollView(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Container(
              padding: const EdgeInsets.all(18),
              decoration: BoxDecoration(
                color: c.surfaceHighlight,
                shape: BoxShape.circle,
              ),
              child: Icon(Icons.auto_awesome_motion_rounded, size: 36, color: c.primary),
            ),
            const SizedBox(height: 14),
            Text(
              'No automations yet.',
              style: TextStyle(fontSize: 17, fontWeight: FontWeight.w700, color: c.textPrimary),
            ),
            const SizedBox(height: 6),
            ConstrainedBox(
              constraints: const BoxConstraints(maxWidth: 420),
              child: Text(
                'Create an autonomous job that Kora can execute repeatedly, on schedule, or conditionally without manual intervention.',
                textAlign: TextAlign.center,
                style: TextStyle(fontSize: 12.5, color: c.textSecondary),
              ),
            ),
            const SizedBox(height: 20),
            ElevatedButton.icon(
              icon: const Icon(Icons.add_rounded, size: 16),
              label: const Text('+ New Automation'),
              style: ElevatedButton.styleFrom(
                backgroundColor: c.primary,
                foregroundColor: Colors.white,
                padding: const EdgeInsets.symmetric(horizontal: 18, vertical: 12),
                shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
              ),
              onPressed: () => _openNewAutomationDialog(context),
            ),
            const SizedBox(height: 28),

            // Starter Template suggestions
            if (state.templates.isNotEmpty) ...[
              Text(
                'OR START WITH A TEMPLATE',
                style: TextStyle(fontSize: 11, fontWeight: FontWeight.w700, letterSpacing: 0.8, color: c.textMuted),
              ),
              const SizedBox(height: 14),
              Wrap(
                spacing: 10,
                runSpacing: 10,
                alignment: WrapAlignment.center,
                children: state.templates.take(3).map((tpl) {
                  return ActionChip(
                    avatar: Icon(Icons.bookmark_border_rounded, size: 14, color: c.primary),
                    label: Text(tpl.name),
                    backgroundColor: c.surface,
                    side: BorderSide(color: c.border),
                    onPressed: () => _applyTemplateAndOpen(context, tpl),
                  );
                }).toList(),
              ),
            ],
          ],
        ),
      ),
    );
  }

  // ── Detail & Live Trace Dialog ────────────────────────────────────────────
  void _openDetailDialog(BuildContext context, AutomationItem item) {
    ref.read(tasksProvider.notifier).selectAutomation(item);

    showDialog(
      context: context,
      builder: (ctx) => _AutomationDetailModal(automationId: item.id),
    );
  }

  void _confirmDelete(BuildContext context, AutomationItem auto) {
    final c = AppTheme.colors(context);
    showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        backgroundColor: c.surface,
        title: Text('Delete Automation?', style: TextStyle(color: c.textPrimary, fontSize: 16, fontWeight: FontWeight.w700)),
        content: Text('Are you sure you want to delete "${auto.name}"? This removes the schedule and all execution history.', style: TextStyle(color: c.textSecondary, fontSize: 13)),
        actions: [
          TextButton(
            child: const Text('Cancel'),
            onPressed: () => Navigator.pop(ctx),
          ),
          ElevatedButton(
            style: ElevatedButton.styleFrom(backgroundColor: c.error, foregroundColor: Colors.white),
            child: const Text('Delete'),
            onPressed: () {
              Navigator.pop(ctx);
              ref.read(tasksProvider.notifier).deleteAutomation(auto.id);
            },
          ),
        ],
      ),
    );
  }

  void _openNewAutomationDialog(BuildContext context) {
    showDialog(
      context: context,
      builder: (ctx) => const _NewAutomationModal(),
    );
  }

  void _applyTemplateAndOpen(BuildContext context, AutomationTemplate tpl) {
    showDialog(
      context: context,
      builder: (ctx) => _NewAutomationModal(initialTemplate: tpl),
    );
  }

  (Color, Color, IconData, String) _resolveStatus(String status, KoraColors c) {
    final s = status.toLowerCase();
    if (s == 'active') {
      return (c.successLight, c.statusCompleted, Icons.check_circle_outline_rounded, 'ACTIVE');
    }
    if (s == 'running') {
      return (c.primaryLight, c.statusThinking, Icons.motion_photos_on_rounded, 'RUNNING');
    }
    if (s == 'paused') {
      return (c.warningLight, c.warning, Icons.pause_circle_outline_rounded, 'PAUSED');
    }
    if (s == 'completed') {
      return (c.secondaryLight, c.secondary, Icons.task_alt_rounded, 'COMPLETED');
    }
    if (s == 'failed') {
      return (c.errorLight, c.error, Icons.error_outline_rounded, 'FAILED');
    }
    return (c.surfaceHighlight, c.textMuted, Icons.access_time_rounded, 'PENDING');
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// Automation Detail Modal with Realtime Execution Trace
// ─────────────────────────────────────────────────────────────────────────────

class _AutomationDetailModal extends ConsumerWidget {
  final String automationId;
  const _AutomationDetailModal({required this.automationId});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final state = ref.watch(tasksProvider);
    final c = AppTheme.colors(context);
    final auto = state.selectedAutomation ?? state.automations.where((a) => a.id == automationId).firstOrNull;

    if (auto == null) {
      return AlertDialog(
        backgroundColor: c.surface,
        content: const Text('Automation not found.'),
      );
    }

    final latestExecution = state.liveExecution ?? auto.executionHistory.firstOrNull;

    return Dialog(
      backgroundColor: c.surface,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14)),
      child: Container(
        width: 780,
        height: 640,
        padding: const EdgeInsets.all(24),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // Header
            Row(
              children: [
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Row(
                        children: [
                          Text(
                            auto.name,
                            style: TextStyle(fontSize: 18, fontWeight: FontWeight.w800, color: c.textPrimary),
                          ),
                          const SizedBox(width: 8),
                          Container(
                            padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                            decoration: BoxDecoration(
                              color: c.surfaceHighlight,
                              borderRadius: BorderRadius.circular(4),
                              border: Border.all(color: c.border),
                            ),
                            child: Text(
                              auto.scheduleLabel,
                              style: TextStyle(fontSize: 10.5, fontWeight: FontWeight.w600, color: c.textSecondary),
                            ),
                          ),
                        ],
                      ),
                      const SizedBox(height: 4),
                      Text(
                        auto.goal,
                        style: TextStyle(fontSize: 12, color: c.textSecondary, fontStyle: FontStyle.italic),
                      ),
                    ],
                  ),
                ),
                IconButton(
                  icon: const Icon(Icons.close_rounded),
                  onPressed: () => Navigator.pop(context),
                ),
              ],
            ),
            const SizedBox(height: 16),
            Divider(height: 1, color: c.border),
            const SizedBox(height: 16),

            // Model info and live status bar
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
              decoration: BoxDecoration(
                color: c.surfaceHighlight.withValues(alpha: 0.6),
                borderRadius: BorderRadius.circular(8),
                border: Border.all(color: c.border),
              ),
              child: Row(
                children: [
                  Icon(Icons.psychology_rounded, size: 16, color: c.primary),
                  const SizedBox(width: 8),
                  Text(
                    'Model: ${latestExecution?.modelUsed ?? "Local AI (qwen3:1.7b)"}',
                    style: TextStyle(fontSize: 11.5, fontWeight: FontWeight.w700, color: c.textPrimary),
                  ),
                  const Spacer(),
                  if (latestExecution != null) ...[
                    Text(
                      'Run #${latestExecution.runNumber} • ${latestExecution.durationMs}ms',
                      style: TextStyle(fontSize: 11, color: c.textSecondary),
                    ),
                    const SizedBox(width: 8),
                    Container(
                      padding: const EdgeInsets.symmetric(horizontal: 7, vertical: 2),
                      decoration: BoxDecoration(
                        color: latestExecution.status == 'completed' ? c.successLight : c.primaryLight,
                        borderRadius: BorderRadius.circular(4),
                      ),
                      child: Text(
                        latestExecution.status.toUpperCase(),
                        style: TextStyle(
                          fontSize: 10,
                          fontWeight: FontWeight.w700,
                          color: latestExecution.status == 'completed' ? c.statusCompleted : c.primary,
                        ),
                      ),
                    ),
                  ],
                ],
              ),
            ),
            const SizedBox(height: 16),

            // Execution steps & output
            Text(
              'EXECUTION PLAN & STEPS',
              style: TextStyle(fontSize: 11, fontWeight: FontWeight.w700, letterSpacing: 0.5, color: c.textMuted),
            ),
            const SizedBox(height: 8),

            Expanded(
              child: latestExecution == null || latestExecution.steps.isEmpty
                  ? Center(
                      child: Text(
                        'No executions recorded yet. Click "Run Now" to trigger.',
                        style: TextStyle(fontSize: 12.5, color: c.textMuted),
                      ),
                    )
                  : ListView(
                      children: [
                        ...latestExecution.steps.map((step) {
                          return _buildStepTraceItem(step, c);
                        }),
                        if (latestExecution.result != null) ...[
                          const SizedBox(height: 12),
                          Container(
                            padding: const EdgeInsets.all(12),
                            decoration: BoxDecoration(
                              color: c.surfaceHighlight,
                              borderRadius: BorderRadius.circular(8),
                              border: Border.all(color: c.border),
                            ),
                            child: Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                Row(
                                  children: [
                                    Icon(Icons.check_circle_outline_rounded, size: 14, color: c.statusCompleted),
                                    const SizedBox(width: 6),
                                    Text(
                                      'Final Output',
                                      style: TextStyle(fontSize: 11.5, fontWeight: FontWeight.w700, color: c.textPrimary),
                                    ),
                                  ],
                                ),
                                const SizedBox(height: 6),
                                SelectableText(
                                  latestExecution.result.toString(),
                                  style: TextStyle(fontSize: 11.5, color: c.textPrimary, height: 1.4),
                                ),
                              ],
                            ),
                          ),
                        ],
                      ],
                    ),
            ),

            const SizedBox(height: 12),
            Divider(height: 1, color: c.border),
            const SizedBox(height: 12),

            // Bottom Actions
            Row(
              children: [
                OutlinedButton.icon(
                  icon: const Icon(Icons.play_arrow_rounded, size: 16),
                  label: const Text('Run Now'),
                  style: OutlinedButton.styleFrom(
                    foregroundColor: c.primary,
                    side: BorderSide(color: c.primary),
                  ),
                  onPressed: () {
                    ref.read(tasksProvider.notifier).runAutomation(auto.id);
                  },
                ),
                const Spacer(),
                TextButton(
                  child: const Text('Close'),
                  onPressed: () => Navigator.pop(context),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildStepTraceItem(AutomationStep step, KoraColors c) {
    final isDone = step.status == 'completed';
    final isRunning = step.status == 'running';

    return Container(
      margin: const EdgeInsets.only(bottom: 8),
      padding: const EdgeInsets.all(10),
      decoration: BoxDecoration(
        color: c.surface,
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: isRunning ? c.primary.withValues(alpha: 0.5) : c.border),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              if (isRunning)
                SizedBox(
                  width: 14,
                  height: 14,
                  child: CircularProgressIndicator(strokeWidth: 2, color: c.primary),
                )
              else if (isDone)
                Icon(Icons.check_circle_rounded, size: 16, color: c.statusCompleted)
              else
                Icon(Icons.radio_button_unchecked_rounded, size: 16, color: c.textMuted),
              const SizedBox(width: 8),
              Expanded(
                child: Text(
                  'Step ${step.stepIndex}: ${step.goal}',
                  style: TextStyle(
                    fontSize: 12.5,
                    fontWeight: FontWeight.w700,
                    color: c.textPrimary,
                  ),
                ),
              ),
              if (step.toolName != null) ...[
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                  decoration: BoxDecoration(color: c.surfaceTertiary, borderRadius: BorderRadius.circular(4)),
                  child: Text(
                    step.toolName!,
                    style: TextStyle(fontSize: 10, fontWeight: FontWeight.w600, color: c.textSecondary),
                  ),
                ),
                const SizedBox(width: 8),
              ],
              Text(
                '${step.durationMs}ms',
                style: TextStyle(fontSize: 11, color: c.textMuted),
              ),
            ],
          ),
          if (step.output != null) ...[
            const SizedBox(height: 6),
            Container(
              width: double.infinity,
              padding: const EdgeInsets.all(8),
              decoration: BoxDecoration(
                color: c.surfaceHighlight.withValues(alpha: 0.5),
                borderRadius: BorderRadius.circular(6),
              ),
              child: SelectableText(
                step.output.toString(),
                style: TextStyle(fontSize: 10.5, fontFamily: 'monospace', color: c.textSecondary),
              ),
            ),
          ],
        ],
      ),
    );
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// + New Automation Dialog (Natural Language, Custom Builder, Starter Templates)
// ─────────────────────────────────────────────────────────────────────────────

class _NewAutomationModal extends ConsumerStatefulWidget {
  final AutomationTemplate? initialTemplate;
  const _NewAutomationModal({this.initialTemplate});

  @override
  ConsumerState<_NewAutomationModal> createState() => _NewAutomationModalState();
}

class _NewAutomationModalState extends ConsumerState<_NewAutomationModal> with SingleTickerProviderStateMixin {
  late TabController _tabController;

  // Natural Language Tab
  final _nlController = TextEditingController(
    text: 'I want Kora to check my GitHub project every morning and tell me if anything important changed.',
  );

  // Custom Builder Tab
  final _nameController = TextEditingController();
  final _descController = TextEditingController();
  final _goalController = TextEditingController();
  String _triggerType = 'interval';
  final _intervalMinutesController = TextEditingController(text: '60');
  final _cronExprController = TextEditingController(text: '0 8 * * *');
  final Set<String> _selectedTools = {'web_search'};

  @override
  void initState() {
    super.initState();
    _tabController = TabController(length: 3, vsync: this);

    if (widget.initialTemplate != null) {
      _applyTemplate(widget.initialTemplate!);
      _tabController.index = 1; // Custom builder
    }
  }

  void _applyTemplate(AutomationTemplate tpl) {
    setState(() {
      _nameController.text = tpl.name;
      _descController.text = tpl.description;
      _goalController.text = tpl.goal;
      _triggerType = tpl.triggerType;
      _selectedTools.clear();
      _selectedTools.addAll(tpl.allowedTools);
      if (tpl.triggerConfig.containsKey('cron_expr')) {
        _cronExprController.text = tpl.triggerConfig['cron_expr'].toString();
      }
      if (tpl.triggerConfig.containsKey('interval_seconds')) {
        final sec = tpl.triggerConfig['interval_seconds'] as int;
        _intervalMinutesController.text = (sec ~/ 60).toString();
      }
    });
  }

  @override
  void dispose() {
    _tabController.dispose();
    _nlController.dispose();
    _nameController.dispose();
    _descController.dispose();
    _goalController.dispose();
    _intervalMinutesController.dispose();
    _cronExprController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final state = ref.watch(tasksProvider);
    final c = AppTheme.colors(context);

    return Dialog(
      backgroundColor: c.surface,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14)),
      child: Container(
        width: 740,
        height: 600,
        padding: const EdgeInsets.all(24),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // Top Bar
            Row(
              children: [
                Icon(Icons.auto_awesome_rounded, color: c.primary, size: 20),
                const SizedBox(width: 8),
                Text(
                  'Create Autonomous Automation',
                  style: TextStyle(fontSize: 18, fontWeight: FontWeight.w800, color: c.textPrimary),
                ),
                const Spacer(),
                IconButton(
                  icon: const Icon(Icons.close_rounded),
                  onPressed: () => Navigator.pop(context),
                ),
              ],
            ),
            const SizedBox(height: 12),

            // Tab Bar
            TabBar(
              controller: _tabController,
              labelColor: c.primary,
              unselectedLabelColor: c.textSecondary,
              indicatorColor: c.primary,
              tabs: const [
                Tab(text: 'Natural Language'),
                Tab(text: 'Custom Builder'),
                Tab(text: 'Starter Templates'),
              ],
            ),
            const SizedBox(height: 16),

            // Tab Content
            Expanded(
              child: TabBarView(
                controller: _tabController,
                children: [
                  _buildNaturalLanguageTab(state, c),
                  _buildCustomBuilderTab(state, c),
                  _buildTemplatesTab(state, c),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }

  // ── Tab 1: Natural Language ───────────────────────────────────────────────
  Widget _buildNaturalLanguageTab(TasksState state, KoraColors c) {
    final draft = state.interpretedDraft;

    return SingleChildScrollView(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            'Describe what you want Kora to automate in natural language:',
            style: TextStyle(fontSize: 12.5, fontWeight: FontWeight.w600, color: c.textPrimary),
          ),
          const SizedBox(height: 8),
          TextField(
            controller: _nlController,
            maxLines: 3,
            decoration: InputDecoration(
              hintText: 'e.g., "Research latest AI model releases every morning and compile a brief."',
              filled: true,
              fillColor: c.surfaceHighlight.withValues(alpha: 0.5),
              border: OutlineInputBorder(borderRadius: BorderRadius.circular(8), borderSide: BorderSide(color: c.border)),
              enabledBorder: OutlineInputBorder(borderRadius: BorderRadius.circular(8), borderSide: BorderSide(color: c.border)),
            ),
            style: TextStyle(fontSize: 13, color: c.textPrimary),
          ),
          const SizedBox(height: 12),
          ElevatedButton.icon(
            icon: state.isInterpreting
                ? SizedBox(width: 14, height: 14, child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white))
                : const Icon(Icons.auto_awesome_rounded, size: 16),
            label: Text(state.isInterpreting ? 'Interpreting...' : 'Interpret with Kora'),
            style: ElevatedButton.styleFrom(
              backgroundColor: c.primary,
              foregroundColor: Colors.white,
              padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
              shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
            ),
            onPressed: state.isInterpreting ? null : () => ref.read(tasksProvider.notifier).interpretPrompt(_nlController.text),
          ),
          const SizedBox(height: 16),

          // Interpretation Card
          if (draft != null) ...[
            Container(
              padding: const EdgeInsets.all(14),
              decoration: BoxDecoration(
                color: c.surfaceHighlight,
                borderRadius: BorderRadius.circular(10),
                border: Border.all(color: c.primary.withValues(alpha: 0.4)),
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      Icon(Icons.check_circle_rounded, size: 16, color: c.primary),
                      const SizedBox(width: 8),
                      Text(
                        'Kora Understood:',
                        style: TextStyle(fontSize: 13, fontWeight: FontWeight.w700, color: c.textPrimary),
                      ),
                    ],
                  ),
                  const SizedBox(height: 10),
                  Text('Name: ${draft['name']}', style: TextStyle(fontSize: 12.5, fontWeight: FontWeight.w700, color: c.textPrimary)),
                  const SizedBox(height: 4),
                  Text('Trigger: ${draft['schedule_label']}', style: TextStyle(fontSize: 12, color: c.textSecondary)),
                  const SizedBox(height: 4),
                  Text('Goal: ${draft['goal']}', style: TextStyle(fontSize: 12, color: c.textSecondary)),
                  const SizedBox(height: 10),
                  Text('Planned Steps:', style: TextStyle(fontSize: 11.5, fontWeight: FontWeight.w700, color: c.textMuted)),
                  const SizedBox(height: 4),
                  ...((draft['planned_actions'] as List<dynamic>? ?? []).map((step) {
                    return Padding(
                      padding: const EdgeInsets.only(bottom: 2),
                      child: Row(
                        children: [
                          Icon(Icons.arrow_right_rounded, size: 16, color: c.primary),
                          Expanded(
                            child: Text(step.toString(), style: TextStyle(fontSize: 11.5, color: c.textPrimary)),
                          ),
                        ],
                      ),
                    );
                  })),
                  const SizedBox(height: 14),
                  Row(
                    children: [
                      ElevatedButton.icon(
                        icon: const Icon(Icons.check_rounded, size: 16),
                        label: const Text('Activate Automation'),
                        style: ElevatedButton.styleFrom(
                          backgroundColor: c.primary,
                          foregroundColor: Colors.white,
                          padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 8),
                        ),
                        onPressed: () async {
                          await ref.read(tasksProvider.notifier).createAutomation({
                            'name': draft['name'],
                            'description': draft['description'],
                            'goal': draft['goal'],
                            'trigger_type': draft['trigger_type'],
                            'trigger_config': draft['trigger_config'],
                            'allowed_tools': draft['allowed_tools'],
                            'permission_scope': draft['permission_scope'],
                          });
                          if (context.mounted) Navigator.pop(context);
                        },
                      ),
                      const SizedBox(width: 8),
                      OutlinedButton(
                        child: const Text('Edit in Builder'),
                        onPressed: () {
                          _nameController.text = draft['name']?.toString() ?? '';
                          _descController.text = draft['description']?.toString() ?? '';
                          _goalController.text = draft['goal']?.toString() ?? '';
                          _triggerType = draft['trigger_type']?.toString() ?? 'interval';
                          _selectedTools.clear();
                          _selectedTools.addAll((draft['allowed_tools'] as List<dynamic>? ?? []).map((e) => e.toString()));
                          _tabController.index = 1;
                        },
                      ),
                    ],
                  ),
                ],
              ),
            ),
          ],
        ],
      ),
    );
  }

  // ── Tab 2: Custom Builder ─────────────────────────────────────────────────
  Widget _buildCustomBuilderTab(TasksState state, KoraColors c) {
    return SingleChildScrollView(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text('Automation Name', style: TextStyle(fontSize: 12, fontWeight: FontWeight.w700, color: c.textPrimary)),
                    const SizedBox(height: 4),
                    TextField(
                      controller: _nameController,
                      decoration: InputDecoration(
                        hintText: 'e.g. Daily AI Briefing',
                        filled: true,
                        fillColor: c.surfaceHighlight.withValues(alpha: 0.5),
                        border: OutlineInputBorder(borderRadius: BorderRadius.circular(8)),
                      ),
                      style: const TextStyle(fontSize: 13),
                    ),
                  ],
                ),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text('Trigger Type', style: TextStyle(fontSize: 12, fontWeight: FontWeight.w700, color: c.textPrimary)),
                    const SizedBox(height: 4),
                    DropdownButtonFormField<String>(
                      value: _triggerType,
                      decoration: InputDecoration(
                        filled: true,
                        fillColor: c.surfaceHighlight.withValues(alpha: 0.5),
                        border: OutlineInputBorder(borderRadius: BorderRadius.circular(8)),
                      ),
                      items: const [
                        DropdownMenuItem(value: 'interval', child: Text('Interval (Every X min)')),
                        DropdownMenuItem(value: 'cron', child: Text('Daily / Cron Schedule')),
                        DropdownMenuItem(value: 'event', child: Text('Event Trigger (On File Change)')),
                        DropdownMenuItem(value: 'manual', child: Text('Manual (Run on Demand)')),
                      ],
                      onChanged: (v) => setState(() => _triggerType = v ?? 'interval'),
                    ),
                  ],
                ),
              ),
            ],
          ),
          const SizedBox(height: 12),

          // Schedule field based on type
          if (_triggerType == 'interval') ...[
            Text('Repeat Interval (Minutes)', style: TextStyle(fontSize: 12, fontWeight: FontWeight.w700, color: c.textPrimary)),
            const SizedBox(height: 4),
            TextField(
              controller: _intervalMinutesController,
              keyboardType: TextInputType.number,
              decoration: InputDecoration(
                hintText: 'e.g. 60',
                filled: true,
                fillColor: c.surfaceHighlight.withValues(alpha: 0.5),
                border: OutlineInputBorder(borderRadius: BorderRadius.circular(8)),
              ),
              style: const TextStyle(fontSize: 13),
            ),
            const SizedBox(height: 12),
          ] else if (_triggerType == 'cron') ...[
            Text('Cron Expression (minute hour day month day-of-week)', style: TextStyle(fontSize: 12, fontWeight: FontWeight.w700, color: c.textPrimary)),
            const SizedBox(height: 4),
            TextField(
              controller: _cronExprController,
              decoration: InputDecoration(
                hintText: '0 8 * * * (Every morning at 08:00)',
                filled: true,
                fillColor: c.surfaceHighlight.withValues(alpha: 0.5),
                border: OutlineInputBorder(borderRadius: BorderRadius.circular(8)),
              ),
              style: const TextStyle(fontSize: 13),
            ),
            const SizedBox(height: 12),
          ],

          Text('Goal', style: TextStyle(fontSize: 12, fontWeight: FontWeight.w700, color: c.textPrimary)),
          const SizedBox(height: 4),
          TextField(
            controller: _goalController,
            maxLines: 2,
            decoration: InputDecoration(
              hintText: 'What should Kora accomplish during execution?',
              filled: true,
              fillColor: c.surfaceHighlight.withValues(alpha: 0.5),
              border: OutlineInputBorder(borderRadius: BorderRadius.circular(8)),
            ),
            style: const TextStyle(fontSize: 13),
          ),
          const SizedBox(height: 14),

          // Tool permissions
          Text('Allowed Tools & Permission Scope', style: TextStyle(fontSize: 12, fontWeight: FontWeight.w700, color: c.textPrimary)),
          const SizedBox(height: 6),
          Wrap(
            spacing: 8,
            children: [
              _buildToolFilterChip('web_search', 'DuckDuckGo Search', c),
              _buildToolFilterChip('git_ops', 'Git Operations', c),
              _buildToolFilterChip('directory_ops', 'Directory Ops', c),
              _buildToolFilterChip('file_read', 'File Read', c),
              _buildToolFilterChip('system_info', 'System Info', c),
            ],
          ),
          const SizedBox(height: 20),

          ElevatedButton.icon(
            icon: const Icon(Icons.check_rounded, size: 16),
            label: const Text('Create Automation'),
            style: ElevatedButton.styleFrom(
              backgroundColor: c.primary,
              foregroundColor: Colors.white,
              padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 12),
              shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
            ),
            onPressed: () async {
              final name = _nameController.text.trim();
              final goal = _goalController.text.trim();
              if (name.isEmpty || goal.isEmpty) return;

              Map<String, dynamic> trigCfg = {};
              if (_triggerType == 'interval') {
                final mins = int.tryParse(_intervalMinutesController.text) ?? 60;
                trigCfg = {'interval_seconds': mins * 60, 'schedule_label': 'Every ${mins}m'};
              } else if (_triggerType == 'cron') {
                trigCfg = {'cron_expr': _cronExprController.text.trim(), 'schedule_label': 'Cron ${_cronExprController.text}'};
              }

              await ref.read(tasksProvider.notifier).createAutomation({
                'name': name,
                'description': _descController.text.trim(),
                'goal': goal,
                'trigger_type': _triggerType,
                'trigger_config': trigCfg,
                'allowed_tools': _selectedTools.toList(),
                'permission_scope': {
                  'allowed_tools': _selectedTools.toList(),
                  'network_access': _selectedTools.contains('web_search'),
                },
              });
              if (context.mounted) Navigator.pop(context);
            },
          ),
        ],
      ),
    );
  }

  Widget _buildToolFilterChip(String toolKey, String label, KoraColors c) {
    final isSelected = _selectedTools.contains(toolKey);
    return FilterChip(
      label: Text(label),
      selected: isSelected,
      onSelected: (val) {
        setState(() {
          if (val) {
            _selectedTools.add(toolKey);
          } else {
            _selectedTools.remove(toolKey);
          }
        });
      },
      backgroundColor: c.surface,
      selectedColor: c.primaryLight,
      checkmarkColor: c.primary,
      labelStyle: TextStyle(
        fontSize: 11.5,
        fontWeight: isSelected ? FontWeight.w700 : FontWeight.w500,
        color: isSelected ? c.primary : c.textSecondary,
      ),
    );
  }

  // ── Tab 3: Starter Templates ──────────────────────────────────────────────
  Widget _buildTemplatesTab(TasksState state, KoraColors c) {
    if (state.templates.isEmpty) {
      return Center(
        child: Text('Loading templates...', style: TextStyle(color: c.textMuted)),
      );
    }

    return ListView.builder(
      itemCount: state.templates.length,
      itemBuilder: (context, idx) {
        final tpl = state.templates[idx];
        return Container(
          margin: const EdgeInsets.only(bottom: 10),
          padding: const EdgeInsets.all(12),
          decoration: BoxDecoration(
            color: c.surfaceHighlight.withValues(alpha: 0.5),
            borderRadius: BorderRadius.circular(8),
            border: Border.all(color: c.border),
          ),
          child: Row(
            children: [
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      children: [
                        Text(tpl.name, style: TextStyle(fontSize: 13.5, fontWeight: FontWeight.w700, color: c.textPrimary)),
                        const SizedBox(width: 8),
                        Container(
                          padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                          decoration: BoxDecoration(color: c.surfaceTertiary, borderRadius: BorderRadius.circular(4)),
                          child: Text(tpl.category, style: TextStyle(fontSize: 9.5, fontWeight: FontWeight.w700, color: c.textSecondary)),
                        ),
                      ],
                    ),
                    const SizedBox(height: 4),
                    Text(tpl.description, style: TextStyle(fontSize: 11.5, color: c.textSecondary)),
                  ],
                ),
              ),
              ElevatedButton(
                style: ElevatedButton.styleFrom(
                  backgroundColor: c.primary,
                  foregroundColor: Colors.white,
                  padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
                ),
                child: const Text('Use Template', style: TextStyle(fontSize: 11.5)),
                onPressed: () {
                  _applyTemplate(tpl);
                  _tabController.index = 1; // Switch to Custom Builder
                },
              ),
            ],
          ),
        );
      },
    );
  }
}
