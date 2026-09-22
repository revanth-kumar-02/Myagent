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

    final c = AppTheme.colors(context);
    final completedCount = steps.where((s) => s.status == PlanStepStatus.done).length;

    return Container(
      margin: const EdgeInsets.only(bottom: 14),
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: c.surface,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: c.border, width: 1),
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
              Icon(Icons.account_tree_rounded, size: 15, color: c.primary),
              const SizedBox(width: 8),
              Text(
                'Autonomous Plan ($completedCount/${steps.length} Steps)',
                style: TextStyle(
                  fontSize: 12.5,
                  fontWeight: FontWeight.w700,
                  color: c.textPrimary,
                ),
              ),
              const Spacer(),
              if (completedCount == steps.length)
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
                  decoration: BoxDecoration(
                    color: c.successLight,
                    borderRadius: BorderRadius.circular(4),
                  ),
                  child: Text(
                    'Plan Completed',
                    style: TextStyle(
                      fontSize: 10,
                      fontWeight: FontWeight.w700,
                      color: c.success,
                    ),
                  ),
                )
              else
                Text(
                  'Step ${completedCount + 1} of ${steps.length} active',
                  style: TextStyle(fontSize: 11, color: c.textMuted),
                ),
            ],
          ),
          const SizedBox(height: 12),
          // Stepper Grid
          LayoutBuilder(
            builder: (context, constraints) {
              return Wrap(
                spacing: 8,
                runSpacing: 8,
                children: steps.map((step) {
                  final isRunning = step.status == PlanStepStatus.running;
                  final isDone = step.status == PlanStepStatus.done;
                  final (icon, iconColor, bgChip, semanticLabel) = _resolveStepSemantic(step, c);

                  return Container(
                    constraints: const BoxConstraints(minWidth: 120, maxWidth: 170),
                    padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 8),
                    decoration: BoxDecoration(
                      color: isRunning
                          ? (semanticLabel == 'Using Tool' ? c.accentLight : c.primaryLight)
                          : isDone
                              ? c.secondaryLight.withValues(alpha: 0.5)
                              : c.surfaceHighlight.withValues(alpha: 0.6),
                      borderRadius: BorderRadius.circular(8),
                      border: Border.all(
                        color: isRunning
                            ? (semanticLabel == 'Using Tool' ? c.accent : c.primary)
                            : isDone
                                ? c.secondary.withValues(alpha: 0.3)
                                : c.border,
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
                                  color: isRunning ? iconColor : (isDone ? c.textPrimary : c.textMuted),
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
                            color: isDone ? c.textMuted : c.textSecondary,
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

  (IconData, Color, Color, String?) _resolveStepSemantic(PlanStep step, KoraColors c) {
    if (step.status == PlanStepStatus.done) {
      return (Icons.check_circle_rounded, c.statusCompleted, c.successLight, 'Done');
    }
    if (step.status == PlanStepStatus.failed) {
      return (Icons.cancel_rounded, c.error, c.errorLight, 'Failed');
    }
    if (step.status == PlanStepStatus.pending) {
      return (Icons.radio_button_unchecked, c.textMuted, Colors.transparent, 'Queued');
    }

    // Step is currently running — classify semantic action
    final labelLower = step.label.toLowerCase();
    if (labelLower.contains('search') || labelLower.contains('web') || labelLower.contains('duck')) {
      return (Icons.travel_explore_rounded, c.statusSearching, c.warningLight, 'Searching');
    }
    if (labelLower.contains('read') || labelLower.contains('doc') || labelLower.contains('rag')) {
      return (Icons.auto_stories_rounded, c.statusReading, c.primaryLight, 'Reading');
    }
    if (labelLower.contains('tool') || labelLower.contains('exec') || labelLower.contains('bash')) {
      return (Icons.construction_rounded, c.statusUsingTool, c.accentLight, 'Using Tool');
    }
    if (labelLower.contains('verif') || labelLower.contains('check')) {
      return (Icons.verified_rounded, c.statusVerifying, c.secondaryLight, 'Verifying');
    }

    return (Icons.psychology_rounded, c.statusThinking, c.primaryLight, 'Thinking');
  }
}
