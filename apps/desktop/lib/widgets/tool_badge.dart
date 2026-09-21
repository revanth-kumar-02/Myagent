import 'package:flutter/material.dart';
import '../core/theme/app_theme.dart';

class ToolBadge extends StatelessWidget {
  final String toolName;
  final bool isExecuting;

  const ToolBadge({
    super.key,
    required this.toolName,
    this.isExecuting = false,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
      decoration: BoxDecoration(
        color: AppTheme.primary.withValues(alpha: 0.12),
        borderRadius: BorderRadius.circular(6),
        border: Border.all(
          color: AppTheme.primary.withValues(alpha: 0.35),
          width: 1,
        ),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          if (isExecuting) ...[
            const SizedBox(
              width: 10,
              height: 10,
              child: CircularProgressIndicator(
                strokeWidth: 1.5,
                color: AppTheme.primary,
              ),
            ),
            const SizedBox(width: 6),
          ] else ...[
            const Icon(Icons.build_circle_outlined, size: 12, color: AppTheme.primary),
            const SizedBox(width: 5),
          ],
          Text(
            toolName,
            style: const TextStyle(
              fontSize: 11,
              fontWeight: FontWeight.w600,
              color: AppTheme.primary,
            ),
          ),
        ],
      ),
    );
  }
}
