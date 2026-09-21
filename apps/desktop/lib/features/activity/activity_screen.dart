import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/theme/app_theme.dart';
import '../../core/utils/date_formatter.dart';
import '../../models/activity_log.dart';
import '../../state/activity_state.dart';

class ActivityScreen extends ConsumerWidget {
  const ActivityScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final state = ref.watch(activityProvider);

    return Container(
      color: AppTheme.bgLight,
      padding: const EdgeInsets.symmetric(horizontal: 28, vertical: 24),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              const Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      'Observability & Trace Telemetry',
                      style: TextStyle(
                        fontSize: 20,
                        fontWeight: FontWeight.w800,
                        letterSpacing: -0.4,
                        color: AppTheme.textPrimaryLight,
                      ),
                    ),
                    SizedBox(height: 4),
                    Text(
                      'Real-time execution telemetry, model latencies, tool dispatches, and audit events.',
                      style: TextStyle(fontSize: 13, color: AppTheme.textSecondaryLight),
                    ),
                  ],
                ),
              ),
              OutlinedButton.icon(
                icon: const Icon(Icons.refresh_rounded, size: 16),
                label: const Text('Refresh'),
                onPressed: () => ref.read(activityProvider.notifier).loadActivity(),
              ),
            ],
          ),
          const SizedBox(height: 20),

          Expanded(
            child: state.isLoading
                ? const Center(child: CircularProgressIndicator(color: AppTheme.primary))
                : state.logs.isEmpty
                    ? const Center(
                        child: Text(
                          'No activity traces recorded yet. Traces populate upon executing agent turns.',
                          style: TextStyle(fontSize: 13, color: AppTheme.textMuted),
                        ),
                      )
                    : ListView.builder(
                        itemCount: state.logs.length,
                        itemBuilder: (context, index) {
                          final log = state.logs[index];

                          return Container(
                            margin: const EdgeInsets.only(bottom: 10),
                            padding: const EdgeInsets.all(14),
                            decoration: BoxDecoration(
                              color: AppTheme.surfaceLight,
                              borderRadius: BorderRadius.circular(10),
                              border: Border.all(color: AppTheme.borderLight, width: 1),
                              boxShadow: [
                                BoxShadow(
                                  color: Colors.black.withValues(alpha: 0.02),
                                  blurRadius: 4,
                                  offset: const Offset(0, 2),
                                ),
                              ],
                            ),
                            child: Row(
                              children: [
                                Container(
                                  padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3.5),
                                  decoration: BoxDecoration(
                                    color: AppTheme.primaryLight,
                                    borderRadius: BorderRadius.circular(6),
                                    border: Border.all(color: AppTheme.primary.withValues(alpha: 0.2)),
                                  ),
                                  child: Text(
                                    log.eventType,
                                    style: const TextStyle(
                                      fontSize: 11,
                                      fontWeight: FontWeight.w700,
                                      color: AppTheme.primaryDark,
                                    ),
                                  ),
                                ),
                                const SizedBox(width: 14),
                                Expanded(
                                  child: Text(
                                    log.details,
                                    style: const TextStyle(
                                      fontSize: 12.5,
                                      fontWeight: FontWeight.w500,
                                      color: AppTheme.textPrimaryLight,
                                    ),
                                  ),
                                ),
                                if (log.latencyMs > 0) ...[
                                  Container(
                                    padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                                    decoration: BoxDecoration(
                                      color: AppTheme.surfaceHighlightLight,
                                      borderRadius: BorderRadius.circular(4),
                                    ),
                                    child: Text(
                                      '${log.latencyMs}ms',
                                      style: const TextStyle(
                                        fontSize: 11,
                                        fontWeight: FontWeight.w600,
                                        color: AppTheme.textSecondaryLight,
                                      ),
                                    ),
                                  ),
                                  const SizedBox(width: 12),
                                ],
                                Text(
                                  DateFormatter.formatIso(log.timestamp),
                                  style: const TextStyle(fontSize: 11, color: AppTheme.textMuted),
                                ),
                              ],
                            ),
                          );
                        },
                      ),
          ),
        ],
      ),
    );
  }
}

