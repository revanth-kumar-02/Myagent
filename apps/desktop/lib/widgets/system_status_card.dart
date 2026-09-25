import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../core/theme/app_theme.dart';
import '../state/system_metrics_state.dart';
import 'system_details_modal.dart';

/// Compact "System" / "Machine" status card matching Kora aesthetics (Req 16).
class SystemStatusCard extends ConsumerWidget {
  final bool showHeader;

  const SystemStatusCard({
    super.key,
    this.showHeader = true,
  });

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final state = ref.watch(systemMetricsProvider);
    final metrics = state.metrics;
    final c = AppTheme.colors(context);

    return Material(
      color: Colors.transparent,
      child: InkWell(
        onTap: () => showDialog(
          context: context,
          builder: (_) => SystemDetailsModal(metrics: metrics),
        ),
        borderRadius: BorderRadius.circular(12),
        hoverColor: c.surfaceHighlight,
        child: Container(
          padding: const EdgeInsets.all(16),
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
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            mainAxisSize: MainAxisSize.min,
            children: [
              if (showHeader) ...[
                Row(
                  children: [
                    Container(
                      padding: const EdgeInsets.all(6),
                      decoration: BoxDecoration(
                        color: c.primaryLight,
                        borderRadius: BorderRadius.circular(6),
                      ),
                      child: Icon(Icons.memory_rounded, size: 16, color: c.primary),
                    ),
                    const SizedBox(width: 8),
                    Text(
                      'SYSTEM / HOST MACHINE',
                      style: TextStyle(
                        fontSize: 11,
                        fontWeight: FontWeight.w700,
                        letterSpacing: 0.6,
                        color: c.textSecondary,
                      ),
                    ),
                    const Spacer(),
                    Container(
                      padding: const EdgeInsets.symmetric(horizontal: 7, vertical: 2.5),
                      decoration: BoxDecoration(
                        color: state.isLiveStreaming
                            ? c.success.withValues(alpha: 0.12)
                            : c.textMuted.withValues(alpha: 0.12),
                        borderRadius: BorderRadius.circular(10),
                      ),
                      child: Row(
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          Container(
                            width: 6,
                            height: 6,
                            decoration: BoxDecoration(
                              color: state.isLiveStreaming ? c.success : c.textMuted,
                              shape: BoxShape.circle,
                            ),
                          ),
                          const SizedBox(width: 5),
                          Text(
                            state.isLiveStreaming ? 'LIVE' : 'SYNCING',
                            style: TextStyle(
                              fontSize: 9.5,
                              fontWeight: FontWeight.w700,
                              color: state.isLiveStreaming ? c.success : c.textMuted,
                            ),
                          ),
                        ],
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 14),
              ],

              // 4 Metrics Grid: CPU, MEMORY, DISK, NETWORK
              Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  // CPU Metric
                  Expanded(
                    child: _buildMetricItem(
                      label: 'CPU',
                      percent: metrics.cpu.percent,
                      ratio: metrics.cpu.normalizedRatio,
                      detail: '${metrics.cpu.coresLogical} cores',
                      c: c,
                    ),
                  ),
                  const SizedBox(width: 12),

                  // MEMORY Metric
                  Expanded(
                    child: _buildMetricItem(
                      label: 'MEMORY',
                      percent: metrics.memory.percent,
                      ratio: metrics.memory.normalizedRatio,
                      detail: '${metrics.memory.usedGb} / ${metrics.memory.totalGb} GB',
                      c: c,
                    ),
                  ),
                  const SizedBox(width: 12),

                  // DISK Metric
                  Expanded(
                    child: _buildMetricItem(
                      label: 'DISK',
                      percent: metrics.disk.percent,
                      ratio: metrics.disk.normalizedRatio,
                      detail: '${metrics.disk.usedGb} / ${metrics.disk.totalGb} GB',
                      c: c,
                    ),
                  ),
                  const SizedBox(width: 12),

                  // NETWORK Metric
                  Expanded(
                    child: _buildNetworkItem(
                      down: metrics.network.downloadRateFormatted,
                      up: metrics.network.uploadRateFormatted,
                      c: c,
                    ),
                  ),
                ],
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildMetricItem({
    required String label,
    required double percent,
    required double ratio,
    required String detail,
    required KoraColors c,
  }) {
    Color barColor = c.primary;
    if (percent >= 90.0) {
      barColor = c.error;
    } else if (percent >= 75.0) {
      barColor = c.warning;
    }

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          mainAxisAlignment: MainAxisAlignment.spaceBetween,
          children: [
            Text(
              label,
              style: TextStyle(
                fontSize: 10.5,
                fontWeight: FontWeight.w700,
                letterSpacing: 0.4,
                color: c.textMuted,
              ),
            ),
            Text(
              '${percent.toStringAsFixed(0)}%',
              style: TextStyle(
                fontSize: 12,
                fontWeight: FontWeight.w700,
                color: c.textPrimary,
              ),
            ),
          ],
        ),
        const SizedBox(height: 5),
        ClipRRect(
          borderRadius: BorderRadius.circular(3),
          child: LinearProgressIndicator(
            value: ratio,
            minHeight: 6,
            backgroundColor: c.borderSubtle,
            valueColor: AlwaysStoppedAnimation<Color>(barColor),
          ),
        ),
        const SizedBox(height: 4),
        Text(
          detail,
          style: TextStyle(
            fontSize: 10,
            color: c.textSecondary,
            fontWeight: FontWeight.w500,
          ),
          maxLines: 1,
          overflow: TextOverflow.ellipsis,
        ),
      ],
    );
  }

  Widget _buildNetworkItem({
    required String down,
    required String up,
    required KoraColors c,
  }) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          'NETWORK',
          style: TextStyle(
            fontSize: 10.5,
            fontWeight: FontWeight.w700,
            letterSpacing: 0.4,
            color: c.textMuted,
          ),
        ),
        const SizedBox(height: 4),
        Row(
          children: [
            Icon(Icons.arrow_downward_rounded, size: 11, color: c.success),
            const SizedBox(width: 3),
            Flexible(
              child: Text(
                down,
                style: TextStyle(
                  fontSize: 11,
                  fontWeight: FontWeight.w600,
                  color: c.textPrimary,
                ),
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
              ),
            ),
          ],
        ),
        const SizedBox(height: 2),
        Row(
          children: [
            Icon(Icons.arrow_upward_rounded, size: 11, color: c.secondary),
            const SizedBox(width: 3),
            Flexible(
              child: Text(
                up,
                style: TextStyle(
                  fontSize: 11,
                  fontWeight: FontWeight.w600,
                  color: c.textPrimary,
                ),
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
              ),
            ),
          ],
        ),
      ],
    );
  }
}
