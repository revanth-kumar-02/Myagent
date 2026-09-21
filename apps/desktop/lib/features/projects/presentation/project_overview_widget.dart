import 'package:flutter/material.dart';

/// Presentation card displaying project profile overview and technologies.
class ProjectOverviewWidget extends StatelessWidget {
  final String projectName;
  final String rootPath;
  final String status;
  final List<String> technologies;
  final List<String> entryPoints;
  final VoidCallback? onIndexRequested;
  final VoidCallback? onArchiveRequested;

  const ProjectOverviewWidget({
    super.key,
    required this.projectName,
    required this.rootPath,
    required this.status,
    required this.technologies,
    required this.entryPoints,
    this.onIndexRequested,
    this.onArchiveRequested,
  });

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

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
                Row(
                  children: [
                    const Icon(Icons.folder_special, size: 28, color: Colors.blueAccent),
                    const SizedBox(width: 8),
                    Text(
                      projectName,
                      style: theme.textTheme.titleLarge?.copyWith(fontWeight: FontWeight.bold),
                    ),
                  ],
                ),
                Chip(
                  label: Text(status.toUpperCase()),
                  backgroundColor: status == 'active' ? Colors.green.withOpacity(0.2) : Colors.grey.withOpacity(0.2),
                  labelStyle: TextStyle(
                    color: status == 'active' ? Colors.green[800] : Colors.grey[700],
                    fontWeight: FontWeight.bold,
                  ),
                ),
              ],
            ),
            const SizedBox(height: 8),
            Text(
              'Path: $rootPath',
              style: theme.textTheme.bodyMedium?.copyWith(color: Colors.grey[600], fontFeatures: const []),
            ),
            const SizedBox(height: 12),
            if (technologies.isNotEmpty) ...[
              Text('Detected Technologies:', style: theme.textTheme.bodySmall?.copyWith(fontWeight: FontWeight.bold)),
              const SizedBox(height: 4),
              Wrap(
                spacing: 6,
                runSpacing: 4,
                children: technologies.map((t) => Chip(
                  label: Text(t, style: const TextStyle(fontSize: 12)),
                  padding: EdgeInsets.zero,
                  materialTapTargetSize: MaterialTapTargetSize.shrinkWrap,
                )).toList(),
              ),
              const SizedBox(height: 12),
            ],
            if (entryPoints.isNotEmpty) ...[
              Text('Entry Points:', style: theme.textTheme.bodySmall?.copyWith(fontWeight: FontWeight.bold)),
              const SizedBox(height: 2),
              Text(entryPoints.join(', '), style: theme.textTheme.bodySmall?.copyWith(color: Colors.blueGrey)),
              const SizedBox(height: 12),
            ],
            Row(
              mainAxisAlignment: MainAxisAlignment.end,
              children: [
                OutlinedButton.icon(
                  onPressed: onArchiveRequested,
                  icon: const Icon(Icons.archive_outlined, size: 16),
                  label: const Text('Archive'),
                ),
                const SizedBox(width: 8),
                ElevatedButton.icon(
                  onPressed: onIndexRequested,
                  icon: const Icon(Icons.refresh, size: 16),
                  label: const Text('Re-index RAG'),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }
}
