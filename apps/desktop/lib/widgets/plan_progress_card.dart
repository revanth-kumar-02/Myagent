import 'package:flutter/material.dart';
import '../core/theme/app_theme.dart';
import '../models/plan_step.dart';

class PlanProgressCard extends StatelessWidget {
  final List<PlanStep> steps;

  const PlanProgressCard({
    super.key,
    required this.steps,
  });

  @override
  Widget build(BuildContext context) {
    if (steps.isEmpty) return const SizedBox.shrink();

    final completedCount = steps.where((s) => s.status == PlanStepStatus.done).length;

    return Container(
      margin: const EdgeInsets.only(bottom: 14),
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: AppTheme.surfaceLight,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: AppTheme.borderLight, width: 1),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withValues(alpha: 0.02),
            blurRadius: 4,
            offset: const Offset(0, 2),
          ),
        ],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              const Icon(Icons.account_tree_rounded, size: 15, color: AppTheme.primary),
              const SizedBox(width: 8),
              Text(
                'Autonomous Plan ($completedCount/${steps.length} Steps)',
                style: const TextStyle(
                  fontSize: 12.5,
                  fontWeight: FontWeight.w700,
                  color: AppTheme.textPrimaryLight,
                ),
              ),
              const Spacer(),
              if (completedCount == steps.length)
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
                  decoration: BoxDecoration(
                    color: AppTheme.successLight,
                    borderRadius: BorderRadius.circular(4),
                  ),
                  child: const Text(
                    'Plan Completed',
                    style: TextStyle(
                      fontSize: 10,
                      fontWeight: FontWeight.w700,
                      color: AppTheme.success,
                    ),
                  ),
                )
              else
                Text(
                  'Step ${completedCount + 1} of ${steps.length} active',
                  style: const TextStyle(fontSize: 11, color: AppTheme.textMuted),
                ),
            ],
          ),
          const SizedBox(height: 12),
          // Stepper Grid / Flow matching Stitch design
          LayoutBuilder(
            builder: (context, constraints) {
              return Wrap(
                spacing: 8,
                runSpacing: 8,
                children: steps.map((step) {
                  final isRunning = step.status == PlanStepStatus.running;
                  final isDone = step.status == PlanStepStatus.done;
                  final isFailed = step.status == PlanStepStatus.failed;
                  final (icon, iconColor, bgChip, semanticLabel) = _resolveStepSemantic(step);

                  return Container(
                    constraints: const BoxConstraints(minWidth: 120, maxWidth: 170),
                    padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 8),
                    decoration: BoxDecoration(
                      color: isRunning
                          ? (semanticLabel == 'Using Tool' ? AppTheme.accentLight : AppTheme.primaryLight)
                          : isDone
                              ? AppTheme.secondaryLight.withValues(alpha: 0.5)
                              : AppTheme.surfaceHighlightLight.withValues(alpha: 0.6),
                      borderRadius: BorderRadius.circular(8),
                      border: Border.all(
                        color: isRunning
                            ? (semanticLabel == 'Using Tool' ? AppTheme.accent : AppTheme.primary)
                            : isDone
                                ? AppTheme.secondary.withValues(alpha: 0.3)
                                : AppTheme.borderLight,
                        width: isRunning ? 1.5 : 1,
                      ),
                    ),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        Row(
                          children: [
                            Icon(icon, size: 14, color: iconColor),
                            const SizedBox(width: 6),
                            Expanded(
                              child: Text(
                                semanticLabel ?? step.label,
                                style: TextStyle(
                                  fontSize: 11,
                                  fontWeight: isRunning ? FontWeight.w700 : FontWeight.w600,
                                  color: isRunning ? iconColor : (isDone ? AppTheme.textPrimaryLight : AppTheme.textMuted),
                                ),
                                overflow: TextOverflow.ellipsis,
                              ),
                            ),
                          ],
                        ),
                        const SizedBox(height: 3),
                        Text(
                          step.label,
                          style: TextStyle(
                            fontSize: 10,
                            color: isDone ? AppTheme.textMuted : AppTheme.textSecondaryLight,
                            decoration: isDone ? TextDecoration.lineThrough : null,
                          ),
                          maxLines: 1,
                          overflow: TextOverflow.ellipsis,
                        ),
                      ],
                    ),
                  );
                }).toList(),
              );
            },
          ),
        ],
      ),
    );
  }

  (IconData, Color, Color, String?) _resolveStepSemantic(PlanStep step) {
    if (step.status == PlanStepStatus.done) {
      return (Icons.check_circle_rounded, AppTheme.statusCompleted, AppTheme.successLight, 'Done');
    }
    if (step.status == PlanStepStatus.failed) {
      return (Icons.cancel_rounded, AppTheme.error, AppTheme.errorLight, 'Failed');
    }
    if (step.status == PlanStepStatus.pending) {
      return (Icons.radio_button_unchecked, AppTheme.textMuted, Colors.transparent, 'Queued');
    }

    // Step is currently running — classify semantic action
    final labelLower = step.label.toLowerCase();
    if (labelLower.contains('search') || labelLower.contains('web') || labelLower.contains('duck')) {
      return (Icons.travel_explore_rounded, AppTheme.statusSearching, AppTheme.warningLight, 'Searching');
    }
    if (labelLower.contains('read') || labelLower.contains('doc') || labelLower.contains('rag')) {
      return (Icons.auto_stories_rounded, AppTheme.statusReading, AppTheme.primaryLight, 'Reading');
    }
    if (labelLower.contains('tool') || labelLower.contains('exec') || labelLower.contains('bash')) {
      return (Icons.construction_rounded, AppTheme.statusUsingTool, AppTheme.accentLight, 'Using Tool');
    }
    if (labelLower.contains('verif') || labelLower.contains('check')) {
      return (Icons.verified_rounded, AppTheme.statusVerifying, AppTheme.secondaryLight, 'Verifying');
    }

    return (Icons.psychology_rounded, AppTheme.statusThinking, AppTheme.primaryLight, 'Thinking');
  }
}

