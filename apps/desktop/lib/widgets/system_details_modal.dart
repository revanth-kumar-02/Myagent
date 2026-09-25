import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../core/theme/app_theme.dart';
import '../models/system_metrics_model.dart';
import '../state/system_metrics_state.dart';

/// Comprehensive host system telemetry modal dialog.
class SystemDetailsModal extends ConsumerWidget {
  final SystemMetrics metrics;

  const SystemDetailsModal({
    super.key,
    required this.metrics,
  });

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    // Watch live state so the dialog automatically updates live while open
    final liveState = ref.watch(systemMetricsProvider);
    final m = liveState.metrics;
    final c = AppTheme.colors(context);

    return Dialog(
      backgroundColor: c.surface,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(16),
        side: BorderSide(color: c.border),
      ),
      insetPadding: const EdgeInsets.symmetric(horizontal: 24, vertical: 24),
      child: ConstrainedBox(
        constraints: const BoxConstraints(maxWidth: 580, maxHeight: 680),
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              // Header
              Row(
                children: [
                  Container(
                    padding: const EdgeInsets.all(8),
                    decoration: BoxDecoration(
                      color: c.primaryLight,
                      borderRadius: BorderRadius.circular(8),
                    ),
                    child: Icon(Icons.speed_rounded, size: 20, color: c.primary),
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          'Host System Telemetry',
                          style: TextStyle(
                            fontSize: 17,
                            fontWeight: FontWeight.w700,
                            color: c.textPrimary,
                          ),
                          overflow: TextOverflow.ellipsis,
                        ),
                        const SizedBox(height: 2),
                        Text(
                          '${m.os} • ${m.osRelease} • ${m.processesCount} Processes',
                          style: TextStyle(fontSize: 12, color: c.textSecondary),
                          overflow: TextOverflow.ellipsis,
                        ),
                      ],
                    ),
                  ),
                  const SizedBox(width: 8),
                  Container(
                    padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                    decoration: BoxDecoration(
                      color: m.isHeavyLoad
                          ? c.error.withValues(alpha: 0.12)
                          : c.success.withValues(alpha: 0.12),
                      borderRadius: BorderRadius.circular(12),
                    ),
                    child: Text(
                      m.loadSummary,
                      style: TextStyle(
                        fontSize: 11,
                        fontWeight: FontWeight.w700,
                        color: m.isHeavyLoad ? c.error : c.success,
                      ),
                    ),
                  ),
                  const SizedBox(width: 8),
                  IconButton(
                    icon: Icon(Icons.close_rounded, size: 18, color: c.textMuted),
                    onPressed: () => Navigator.of(context).pop(),
                  ),
                ],
              ),
              const SizedBox(height: 18),
              const Divider(height: 1),
              const SizedBox(height: 16),

              // Scrollable detailed telemetry sections
              Flexible(
                child: SingleChildScrollView(
                  child: Column(
                    children: [
                      // CPU Card
                      _buildSection(
                        title: 'CPU Telemetry',
                        icon: Icons.memory_rounded,
                        percent: m.cpu.percent,
                        ratio: m.cpu.normalizedRatio,
                        c: c,
                        details: [
                          'Logical Cores: ${m.cpu.coresLogical}',
                          'Physical Cores: ${m.cpu.coresPhysical}',
                          if (m.cpu.frequencyMhz != null) 'Clock Speed: ${m.cpu.frequencyMhz} MHz',
                          if (m.cpu.temperatureC != null) 'Core Temp: ${m.cpu.temperatureC} °C',
                        ],
                      ),
                      const SizedBox(height: 14),

                      // Memory Card
                      _buildSection(
                        title: 'RAM / Virtual Memory',
                        icon: Icons.developer_board_rounded,
                        percent: m.memory.percent,
                        ratio: m.memory.normalizedRatio,
                        c: c,
                        details: [
                          'Used: ${m.memory.usedGb} GB (${m.memory.percent}%)',
                          'Available: ${m.memory.availableGb} GB',
                          'Total: ${m.memory.totalGb} GB',
                        ],
                      ),
                      const SizedBox(height: 14),

                      // Disk Card
                      _buildSection(
                        title: 'Storage & Disk Partition',
                        icon: Icons.storage_rounded,
                        percent: m.disk.percent,
                        ratio: m.disk.normalizedRatio,
                        c: c,
                        details: [
                          'Mount: ${m.disk.mountPoint}',
                          'Used: ${m.disk.usedGb} GB',
                          'Free: ${m.disk.availableGb} GB',
                          'Total Capacity: ${m.disk.totalGb} GB',
                        ],
                      ),
                      const SizedBox(height: 14),

                      // Network Card
                      Container(
                        padding: const EdgeInsets.all(14),
                        decoration: BoxDecoration(
                          color: c.surfaceHighlight,
                          borderRadius: BorderRadius.circular(10),
                          border: Border.all(color: c.borderSubtle),
                        ),
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Row(
                              children: [
                                Icon(Icons.wifi_tethering_rounded, size: 16, color: c.primary),
                                const SizedBox(width: 8),
                                Text(
                                  'Network Bandwidth & Traffic',
                                  style: TextStyle(
                                    fontSize: 13,
                                    fontWeight: FontWeight.w700,
                                    color: c.textPrimary,
                                  ),
                                ),
                              ],
                            ),
                            const SizedBox(height: 10),
                            Row(
                              children: [
                                Expanded(
                                  child: _buildRatePill(
                                    label: 'Download Speed',
                                    value: m.network.downloadRateFormatted,
                                    icon: Icons.arrow_downward_rounded,
                                    color: c.success,
                                    c: c,
                                  ),
                                ),
                                const SizedBox(width: 10),
                                Expanded(
                                  child: _buildRatePill(
                                    label: 'Upload Speed',
                                    value: m.network.uploadRateFormatted,
                                    icon: Icons.arrow_upward_rounded,
                                    color: c.secondary,
                                    c: c,
                                  ),
                                ),
                              ],
                            ),
                            const SizedBox(height: 8),
                            Text(
                              'Total transferred: ${(m.network.totalBytesRecv / (1024 * 1024)).toStringAsFixed(1)} MB received • ${(m.network.totalBytesSent / (1024 * 1024)).toStringAsFixed(1)} MB transmitted',
                              style: TextStyle(fontSize: 11, color: c.textMuted),
                            ),
                          ],
                        ),
                      ),
                      const SizedBox(height: 14),

                      // GPU Card
                      Container(
                        padding: const EdgeInsets.all(14),
                        decoration: BoxDecoration(
                          color: c.surfaceHighlight,
                          borderRadius: BorderRadius.circular(10),
                          border: Border.all(color: c.borderSubtle),
                        ),
                        child: Row(
                          children: [
                            Icon(Icons.videogame_asset_rounded, size: 16, color: c.primary),
                            const SizedBox(width: 8),
                            Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                Text(
                                  'GPU Acceleration',
                                  style: TextStyle(
                                    fontSize: 13,
                                    fontWeight: FontWeight.w700,
                                    color: c.textPrimary,
                                  ),
                                ),
                                const SizedBox(height: 2),
                                Text(
                                  m.gpu.available
                                      ? '${m.gpu.name} • ${m.gpu.utilizationPercent}% utilization'
                                      : 'Integrated / Standard Host Graphics',
                                  style: TextStyle(fontSize: 11.5, color: c.textSecondary),
                                ),
                              ],
                            ),
                          ],
                        ),
                      ),
                    ],
                  ),
                ),
              ),

              const SizedBox(height: 14),
              Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  Text(
                    liveState.isLiveStreaming
                        ? 'Updated live via WebSocket (~1.5s)'
                        : 'WebSocket disconnected — cached reading',
                    style: TextStyle(
                      fontSize: 11,
                      color: liveState.isLiveStreaming ? c.textMuted : c.warning,
                    ),
                  ),
                  TextButton.icon(
                    icon: const Icon(Icons.refresh_rounded, size: 14),
                    label: const Text('Refresh'),
                    onPressed: () => ref.read(systemMetricsProvider.notifier).refresh(),
                  ),
                ],
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildSection({
    required String title,
    required IconData icon,
    required double percent,
    required double ratio,
    required List<String> details,
    required KoraColors c,
  }) {
    Color barColor = c.primary;
    if (percent >= 90.0) {
      barColor = c.error;
    } else if (percent >= 75.0) {
      barColor = c.warning;
    }

    return Container(
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: c.surfaceHighlight,
        borderRadius: BorderRadius.circular(10),
        border: Border.all(color: c.borderSubtle),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Icon(icon, size: 16, color: c.primary),
              const SizedBox(width: 8),
              Text(
                title,
                style: TextStyle(
                  fontSize: 13,
                  fontWeight: FontWeight.w700,
                  color: c.textPrimary,
                ),
              ),
              const Spacer(),
              Text(
                '${percent.toStringAsFixed(1)}%',
                style: TextStyle(
                  fontSize: 13,
                  fontWeight: FontWeight.w800,
                  color: barColor,
                ),
              ),
            ],
          ),
          const SizedBox(height: 8),
          ClipRRect(
            borderRadius: BorderRadius.circular(4),
            child: LinearProgressIndicator(
              value: ratio,
              minHeight: 7,
              backgroundColor: c.borderSubtle,
              valueColor: AlwaysStoppedAnimation<Color>(barColor),
            ),
          ),
          const SizedBox(height: 8),
          Wrap(
            spacing: 12,
            runSpacing: 4,
            children: details.map((d) => Text(
              d,
              style: TextStyle(fontSize: 11, color: c.textSecondary, fontWeight: FontWeight.w500),
            )).toList(),
          ),
        ],
      ),
    );
  }

  Widget _buildRatePill({
    required String label,
    required String value,
    required IconData icon,
    required Color color,
    required KoraColors c,
  }) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 8),
      decoration: BoxDecoration(
        color: c.surface,
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: c.borderSubtle),
      ),
      child: Row(
        children: [
          Icon(icon, size: 14, color: color),
          const SizedBox(width: 6),
          Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                label,
                style: TextStyle(fontSize: 9.5, color: c.textMuted, fontWeight: FontWeight.w600),
              ),
              Text(
                value,
                style: TextStyle(fontSize: 12, fontWeight: FontWeight.w700, color: c.textPrimary),
              ),
            ],
          ),
        ],
      ),
    );
  }
}
