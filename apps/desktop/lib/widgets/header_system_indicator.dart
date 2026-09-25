import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../core/theme/app_theme.dart';
import '../state/system_metrics_state.dart';
import 'system_details_modal.dart';

/// Compact top-right system indicator showing live CPU and RAM (Req 17).
/// Isolated consumer widget so only its text values rebuild, never the whole app shell.
class HeaderSystemIndicator extends ConsumerWidget {
  const HeaderSystemIndicator({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final state = ref.watch(systemMetricsProvider);
    final metrics = state.metrics;
    final c = AppTheme.colors(context);

    // Indicator color based on system load
    Color dotColor = c.success;
    if (metrics.isHeavyLoad || metrics.cpu.percent >= 90.0 || metrics.memory.percent >= 90.0) {
      dotColor = c.error;
    } else if (metrics.cpu.percent >= 75.0 || metrics.memory.percent >= 80.0) {
      dotColor = c.warning;
    }

    final cpuText = '${metrics.cpu.percent.toStringAsFixed(0)}%';
    final ramText = '${metrics.memory.percent.toStringAsFixed(0)}%';

    return Material(
      color: Colors.transparent,
      child: InkWell(
        onTap: () => showDialog(
          context: context,
          builder: (_) => SystemDetailsModal(metrics: metrics),
        ),
        borderRadius: BorderRadius.circular(20),
        hoverColor: c.surfaceHighlight,
        child: Container(
          padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 5),
          decoration: BoxDecoration(
            color: c.surfaceHighlight,
            borderRadius: BorderRadius.circular(20),
            border: Border.all(color: c.borderSubtle),
          ),
          child: Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              Container(
                width: 7,
                height: 7,
                decoration: BoxDecoration(
                  color: dotColor,
                  shape: BoxShape.circle,
                ),
              ),
              const SizedBox(width: 7),
              Text(
                'CPU ',
                style: TextStyle(
                  fontSize: 11,
                  fontWeight: FontWeight.w600,
                  color: c.textMuted,
                ),
              ),
              Text(
                cpuText,
                style: TextStyle(
                  fontSize: 11,
                  fontWeight: FontWeight.w700,
                  color: c.textPrimary,
                ),
              ),
              const SizedBox(width: 8),
              Text(
                'RAM ',
                style: TextStyle(
                  fontSize: 11,
                  fontWeight: FontWeight.w600,
                  color: c.textMuted,
                ),
              ),
              Text(
                ramText,
                style: TextStyle(
                  fontSize: 11,
                  fontWeight: FontWeight.w700,
                  color: c.textPrimary,
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
