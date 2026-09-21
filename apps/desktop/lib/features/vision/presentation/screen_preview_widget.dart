import 'package:flutter/material.dart';

class ScreenPreviewWidget extends StatelessWidget {
  final String? screenshotPath;
  final List<Map<String, dynamic>> detectedElements;
  final Map<String, dynamic>? activeTarget;
  final bool isAnalyzing;
  final VoidCallback onRefreshCapture;

  const ScreenPreviewWidget({
    super.key,
    required this.screenshotPath,
    required this.detectedElements,
    this.activeTarget,
    this.isAnalyzing = false,
    required this.onRefreshCapture,
  });

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    return Card(
      elevation: 0,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(12),
        side: BorderSide(color: theme.colorScheme.outlineVariant),
      ),
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
                    Icon(Icons.screenshot_monitor, color: theme.colorScheme.primary),
                    const SizedBox(width: 8),
                    Text(
                      'Live Screen & Visual Canvas',
                      style: theme.textTheme.titleMedium?.copyWith(fontWeight: FontWeight.bold),
                    ),
                  ],
                ),
                ElevatedButton.icon(
                  onPressed: isAnalyzing ? null : onRefreshCapture,
                  icon: isAnalyzing
                      ? const SizedBox(
                          width: 14,
                          height: 14,
                          child: CircularProgressIndicator(strokeWidth: 2),
                        )
                      : const Icon(Icons.camera_alt, size: 16),
                  label: Text(isAnalyzing ? 'Analyzing...' : 'Capture Screen'),
                ),
              ],
            ),
            const SizedBox(height: 12),
            Expanded(
              child: Container(
                width: double.infinity,
                decoration: BoxDecoration(
                  color: theme.colorScheme.surfaceContainerHighest.withValues(alpha: 0.3),
                  borderRadius: BorderRadius.circular(8),
                  border: Border.Border.all(color: theme.colorScheme.outlineVariant),
                ),
                child: Stack(
                  fit: StackFit.expand,
                  children: [
                    Center(
                      child: Column(
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          Icon(
                            Icons.desktop_windows,
                            size: 48,
                            color: theme.colorScheme.onSurfaceVariant.withValues(alpha: 0.5),
                          ),
                          const SizedBox(height: 8),
                          Text(
                            screenshotPath != null
                                ? 'Screenshot: $screenshotPath'
                                : 'No screen capture loaded',
                            style: theme.textTheme.bodySmall?.copyWith(
                              color: theme.colorScheme.onSurfaceVariant,
                            ),
                          ),
                        ],
                      ),
                    ),
                    if (activeTarget != null)
                      Positioned(
                        top: 24,
                        right: 24,
                        child: Container(
                          padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
                          decoration: BoxDecoration(
                            color: Colors.green.withValues(alpha: 0.9),
                            borderRadius: BorderRadius.circular(6),
                          ),
                          child: Row(
                            mainAxisSize: MainAxisSize.min,
                            children: [
                              const Icon(Icons.gps_fixed, color: Colors.white, size: 14),
                              const SizedBox(width: 6),
                              Text(
                                'Target Grounded: (${activeTarget!['x']}, ${activeTarget!['y']})',
                                style: const TextStyle(
                                  color: Colors.white,
                                  fontSize: 12,
                                  fontWeight: FontWeight.bold,
                                ),
                              ),
                            ],
                          ),
                        ),
                      ),
                  ],
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
