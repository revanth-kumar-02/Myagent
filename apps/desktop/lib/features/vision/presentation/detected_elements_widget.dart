import 'package:flutter/material.dart';

class DetectedElementsWidget extends StatelessWidget {
  final List<Map<String, dynamic>> elements;
  final Function(Map<String, dynamic> element)? onElementSelected;

  const DetectedElementsWidget({
    super.key,
    required this.elements,
    this.onElementSelected,
  });

  Color _getTypeColor(String type) {
    switch (type.toLowerCase()) {
      case 'button':
        return Colors.blue;
      case 'input_field':
        return Colors.orange;
      case 'link':
        return Colors.teal;
      case 'menu':
        return Colors.purple;
      case 'dialog':
        return Colors.red;
      case 'checkbox':
        return Colors.green;
      default:
        return Colors.grey;
    }
  }

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
              children: [
                Icon(Icons.category, color: theme.colorScheme.primary),
                const SizedBox(width: 8),
                Text(
                  'Detected UI Elements (${elements.length})',
                  style: theme.textTheme.titleMedium?.copyWith(fontWeight: FontWeight.bold),
                ),
              ],
            ),
            const SizedBox(height: 12),
            if (elements.isEmpty)
              Expanded(
                child: Center(
                  child: Text(
                    'No UI elements detected yet.',
                    style: theme.textTheme.bodyMedium?.copyWith(
                      color: theme.colorScheme.onSurfaceVariant,
                    ),
                  ),
                ),
              )
            else
              Expanded(
                child: ListView.separated(
                  itemCount: elements.length,
                  separatorBuilder: (context, index) => const Divider(height: 8),
                  itemBuilder: (context, index) {
                    final el = elements[index];
                    final label = el['label'] ?? 'Unnamed element';
                    final type = el['element_type'] ?? 'custom';
                    final confidence = (el['confidence'] as num?)?.toDouble() ?? 1.0;
                    final bbox = el['bounding_box'] as Map<String, dynamic>? ?? {};
                    final center = bbox['center'] ?? [0, 0];

                    return ListTile(
                      dense: true,
                      contentPadding: EdgeInsets.zero,
                      leading: Container(
                        padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                        decoration: BoxDecoration(
                          color: _getTypeColor(type).withValues(alpha: 0.15),
                          borderRadius: BorderRadius.circular(6),
                          border: Border.Border.all(
                            color: _getTypeColor(type).withValues(alpha: 0.5),
                          ),
                        ),
                        child: Text(
                          type.toUpperCase(),
                          style: TextStyle(
                            color: _getTypeColor(type),
                            fontSize: 10,
                            fontWeight: FontWeight.bold,
                          ),
                        ),
                      ),
                      title: Text(
                        label,
                        style: theme.textTheme.bodyMedium?.copyWith(fontWeight: FontWeight.w600),
                      ),
                      subtitle: Text(
                        'Center: (${center[0]}, ${center[1]}) | Conf: ${(confidence * 100).toInt()}%',
                        style: theme.textTheme.bodySmall?.copyWith(
                          color: theme.colorScheme.onSurfaceVariant,
                        ),
                      ),
                      trailing: IconButton(
                        icon: const Icon(Icons.touch_app, size: 18),
                        tooltip: 'Ground & Action',
                        onPressed: onElementSelected != null
                            ? () => onElementSelected!(el)
                            : null,
                      ),
                    );
                  },
                ),
              ),
          ],
        ),
      ),
    );
  }
}
