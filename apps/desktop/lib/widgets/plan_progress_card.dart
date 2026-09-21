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

    final isDark = Theme.of(context).brightness == Brightness.dark;
    final cardBg = isDark ? const Color(0xFF1E293B) : const Color(0xFFF1F5F9);
    final borderColor = isDark ? const Color(0xFF334155) : const Color(0xFFCBD5E1);

    return Container(
      margin: const EdgeInsets.only(bottom: 8),
      padding: const EdgeInsets.all(10),
      decoration: BoxDecoration(
        color: cardBg,
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: borderColor, width: 1),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              const Icon(Icons.account_tree_outlined, size: 14, color: AppTheme.primary),
              const SizedBox(width: 6),
              Text(
                'Execution Plan (${steps.where((s) => s.status == PlanStepStatus.done).length}/${steps.length})',
                style: const TextStyle(
                  fontSize: 12,
                  fontWeight: FontWeight.w600,
                  color: AppTheme.primary,
                ),
              ),
            ],
          ),
          const SizedBox(height: 8),
          ...steps.map((step) {
            final (icon, iconColor) = switch (step.status) {
              PlanStepStatus.done    => (Icons.check_circle, AppTheme.success),
              PlanStepStatus.running => (Icons.motion_photos_on, AppTheme.warning),
              PlanStepStatus.failed  => (Icons.error, AppTheme.error),
              PlanStepStatus.pending => (Icons.radio_button_unchecked, Colors.grey),
            };

            return Padding(
              padding: const EdgeInsets.symmetric(vertical: 2.5),
              child: Row(
                children: [
                  Icon(icon, size: 13, color: iconColor),
                  const SizedBox(width: 8),
                  Expanded(
                    child: Text(
                      step.label,
                      style: TextStyle(
                        fontSize: 11,
                        color: step.status == PlanStepStatus.done
                            ? Colors.grey
                            : (isDark ? AppTheme.textPrimaryDark : AppTheme.textPrimaryLight),
                        decoration: step.status == PlanStepStatus.done
                            ? TextDecoration.lineThrough
                            : null,
                      ),
                    ),
                  ),
                ],
              ),
            );
          }),
        ],
      ),
    );
  }
}
