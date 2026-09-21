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
      margin: const EdgeInsets.only(bottom: 12),
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: AppTheme.surfaceHighlightLight,
        borderRadius: BorderRadius.circular(10),
        border: Border.all(color: AppTheme.borderLight, width: 1),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              const Icon(Icons.account_tree_rounded, size: 14, color: AppTheme.primary),
              const SizedBox(width: 6),
              Text(
                'Autonomous Plan ($completedCount/${steps.length} Steps)',
                style: const TextStyle(
                  fontSize: 12,
                  fontWeight: FontWeight.w700,
                  color: AppTheme.textPrimaryLight,
                ),
              ),
              const Spacer(),
              if (completedCount == steps.length)
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
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
                ),
            ],
          ),
          const SizedBox(height: 10),
          ...steps.map((step) {
            final (icon, iconColor, bgChip, semanticLabel) = _resolveStepSemantic(step);

            return Container(
              margin: const EdgeInsets.symmetric(vertical: 2.5),
              padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 5),
              decoration: BoxDecoration(
                color: step.status == PlanStepStatus.running ? bgChip : Colors.transparent,
                borderRadius: BorderRadius.circular(6),
              ),
              child: Row(
                children: [
                  Icon(icon, size: 14, color: iconColor),
                  const SizedBox(width: 8),
                  Expanded(
                    child: Text(
                      step.label,
                      style: TextStyle(
                        fontSize: 12,
                        color: step.status == PlanStepStatus.done
                            ? AppTheme.textMuted
                            : AppTheme.textPrimaryLight,
                        fontWeight: step.status == PlanStepStatus.running
                            ? FontWeight.w600
                            : FontWeight.w400,
                        decoration: step.status == PlanStepStatus.done
                            ? TextDecoration.lineThrough
                            : null,
                      ),
                    ),
                  ),
                  if (semanticLabel != null) ...[
                    const SizedBox(width: 6),
                    Container(
                      padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                      decoration: BoxDecoration(
                        color: bgChip,
                        borderRadius: BorderRadius.circular(4),
                      ),
                      child: Text(
                        semanticLabel,
                        style: TextStyle(
                          fontSize: 10,
                          fontWeight: FontWeight.w600,
                          color: iconColor,
                        ),
                      ),
                    ),
                  ],
                ],
              ),
            );
          }),
        ],
      ),
    );
  }

  (IconData, Color, Color, String?) _resolveStepSemantic(PlanStep step) {
    if (step.status == PlanStepStatus.done) {
      return (Icons.check_circle_rounded, AppTheme.statusCompleted, AppTheme.successLight, null);
    }
    if (step.status == PlanStepStatus.failed) {
      return (Icons.cancel_rounded, AppTheme.error, AppTheme.errorLight, 'Failed');
    }
    if (step.status == PlanStepStatus.pending) {
      return (Icons.radio_button_unchecked, AppTheme.textMuted, Colors.transparent, null);
    }

    // Step is currently running — classify semantic action
    final labelLower = step.label.toLowerCase();
    if (labelLower.contains('search') || labelLower.contains('web')) {
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

