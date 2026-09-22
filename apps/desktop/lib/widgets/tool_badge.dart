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
    final c = AppTheme.colors(context);
    final bgColor = isExecuting ? c.accentLight : c.primaryLight;
    final fgColor = isExecuting ? c.accent : c.primary;
    final borderColor = isExecuting ? c.accent.withValues(alpha: 0.3) : c.primary.withValues(alpha: 0.25);

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 9, vertical: 3.5),
      decoration: BoxDecoration(
        color: bgColor,
        borderRadius: BorderRadius.circular(6),
        border: Border.all(
          color: borderColor,
          width: 1,
        ),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          if (isExecuting) ...[
            SizedBox(
              width: 10,
              height: 10,
              child: CircularProgressIndicator(
                strokeWidth: 1.5,
                color: fgColor,
              ),
            ),
            const SizedBox(width: 6),
          ] else ...[
            Icon(Icons.construction_rounded, size: 12, color: fgColor),
            const SizedBox(width: 5),
          ],
          Text(
            toolName,
            style: TextStyle(
              fontSize: 11,
              fontWeight: FontWeight.w600,
              fontFamily: 'monospace',
              color: fgColor,
            ),
          ),
        ],
      ),
    );
  }
}
