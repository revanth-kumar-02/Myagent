import 'package:flutter/material.dart';

/// Presentation card displaying real-time factual project health metrics.
class ProjectHealthWidget extends StatelessWidget {
  final String healthStatus;
  final String indexingStatus;
  final int totalFiles;
  final int totalChunks;
  final int activeTasks;
  final int failedTasks;
  final int activeGoals;
  final double docCoverageRatio;
  final List<String> issues;

  const ProjectHealthWidget({
    super.key,
    required this.healthStatus,
    required this.indexingStatus,
    required this.totalFiles,
    required this.totalChunks,
    required this.activeTasks,
    required this.failedTasks,
    required this.activeGoals,
    required this.docCoverageRatio,
    this.issues = const [],
  });

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    Color statusColor;
    IconData statusIcon;
    switch (healthStatus.toLowerCase()) {
      case 'healthy':
        statusColor = Colors.green;
        statusIcon = Icons.check_circle_outline;
        break;
      case 'needs_attention':
        statusColor = Colors.orange;
        statusIcon = Icons.warning_amber_rounded;
        break;
      case 'degraded':
        statusColor = Colors.red;
        statusIcon = Icons.error_outline;
        break;
      default:
        statusColor = Colors.grey;
        statusIcon = Icons.help_outline;
    }

    return Card(
      elevation: 2,
      margin: const EdgeInsets.symmetric(vertical: 8, horizontal: 16),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
      child: Padding(
        padding: const EdgeInsets.all(16.0),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                Text(
                  'Project Health & Diagnostics',
                  style: theme.textTheme.titleMedium?.copyWith(fontWeight: FontWeight.bold),
                ),
                Row(
                  children: [
                    Icon(statusIcon, color: statusColor, size: 20),
                    const SizedBox(width: 4),
                    Text(
                      healthStatus.toUpperCase(),
                      style: TextStyle(color: statusColor, fontWeight: FontWeight.bold),
                    ),
                  ],
                ),
              ],
            ),
            const Divider(height: 20),
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceAround,
              children: [
                _buildMetricColumn('Index Status', indexingStatus.toUpperCase(), Icons.storage),
                _buildMetricColumn('Chunks / Files', '$totalChunks / $totalFiles', Icons.library_books),
                _buildMetricColumn('Tasks (Active/Fail)', '$activeTasks / $failedTasks', Icons.task_alt),
                _buildMetricColumn('Active Goals', '$activeGoals', Icons.flag_outlined),
                _buildMetricColumn('Doc Coverage', '${(docCoverageRatio * 100).toInt()}%', Icons.menu_book),
              ],
            ),
            if (issues.isNotEmpty) ...[
              const SizedBox(height: 12),
              Text('Health Alerts & Issues:', style: theme.textTheme.bodySmall?.copyWith(fontWeight: FontWeight.bold, color: Colors.orange[900])),
              const SizedBox(height: 4),
              ...issues.map((issue) => Padding(
                padding: const EdgeInsets.symmetric(vertical: 2.0),
                child: Row(
                  children: [
                    const Icon(Icons.arrow_right, size: 16, color: Colors.orange),
                    Expanded(child: Text(issue, style: const TextStyle(fontSize: 12, color: Colors.black87))),
                  ],
                ),
              )),
            ],
          ],
        ),
      ),
    );
  }

  Widget _buildMetricColumn(String label, String value, IconData icon) {
    return Column(
      children: [
        Icon(icon, size: 20, color: Colors.blueGrey),
        const SizedBox(height: 4),
        Text(value, style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 14)),
        Text(label, style: const TextStyle(fontSize: 11, color: Colors.grey)),
      ],
    );
  }
}
