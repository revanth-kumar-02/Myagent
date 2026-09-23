import 'package:flutter/material.dart';
import '../core/theme/app_theme.dart';
import '../state/connection_state.dart';

class StatusPill extends StatelessWidget {
  final BackendStatus status;
  final String? label;
  final VoidCallback? onTap;

  const StatusPill({
    super.key,
    required this.status,
    this.label,
    this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    final c = AppTheme.colors(context);

    final displayLabel = label ?? switch (status) {
      BackendStatus.online     => 'Connected',
      BackendStatus.connecting => 'Connecting...',
      BackendStatus.offline    => 'Offline',
    };

    final (color, icon) = () {
      if (status == BackendStatus.connecting) {
        return (c.warning, Icons.sync_rounded);
      }
      if (status == BackendStatus.offline) {
        return (c.error, Icons.cloud_off_rounded);
      }
      final l = displayLabel.toLowerCase();
      if (l.contains('unavailable') || l.contains('no provider')) {
        return (c.error, Icons.error_outline_rounded);
      }
      if (l.contains('local') || l.contains('ollama')) {
        return (const Color(0xFFF59E0B), Icons.memory_rounded);
      }
      if (l.contains('cloud') || l.contains('online')) {
        return (c.success, Icons.cloud_done_rounded);
      }
      return (c.success, Icons.check_circle_rounded);
    }();

    return InkWell(
      onTap: onTap,
      borderRadius: BorderRadius.circular(16),
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
        decoration: BoxDecoration(
          color: color.withValues(alpha: 0.12),
          borderRadius: BorderRadius.circular(16),
          border: Border.all(color: color.withValues(alpha: 0.3), width: 1),
        ),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(icon, size: 12, color: color),
            const SizedBox(width: 6),
            Text(
              displayLabel,
              style: TextStyle(
                color: color,
                fontSize: 11,
                fontWeight: FontWeight.w600,
              ),
            ),
          ],
        ),
      ),
    );
  }
}

