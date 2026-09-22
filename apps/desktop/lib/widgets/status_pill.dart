import 'package:flutter/material.dart';
import '../core/theme/app_theme.dart';
import '../state/connection_state.dart';

class StatusPill extends StatelessWidget {
  final BackendStatus status;
  final VoidCallback? onTap;

  const StatusPill({
    super.key,
    required this.status,
    this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    final c = AppTheme.colors(context);

    final (color, label, icon) = switch (status) {
      BackendStatus.online     => (c.success, 'Connected', Icons.check_circle_rounded),
      BackendStatus.connecting => (c.warning, 'Connecting...', Icons.sync_rounded),
      BackendStatus.offline    => (c.error, 'Offline', Icons.cloud_off_rounded),
    };

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
              label,
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
