import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/theme/app_theme.dart';
import '../../core/utils/date_formatter.dart';
import '../../models/memory_item.dart';
import '../../state/memory_state.dart';

class MemoryScreen extends ConsumerWidget {
  const MemoryScreen({super.key});

  void _showAddMemoryDialog(BuildContext context, WidgetRef ref) {
    final contentCtrl = TextEditingController();
    String selectedType = 'fact';

    showDialog(
      context: context,
      builder: (ctx) => StatefulBuilder(
        builder: (ctx, setModalState) => AlertDialog(
          title: const Text('Add Memory Record', style: TextStyle(fontSize: 16)),
          content: SizedBox(
            width: 400,
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                TextField(
                  controller: contentCtrl,
                  maxLines: 3,
                  decoration: const InputDecoration(labelText: 'Memory Content'),
                ),
                const SizedBox(height: 12),
                DropdownButtonFormField<String>(
                  value: selectedType,
                  decoration: const InputDecoration(labelText: 'Type'),
                  items: const [
                    DropdownMenuItem(value: 'fact', child: Text('Fact / General Knowledge')),
                    DropdownMenuItem(value: 'preference', child: Text('User Preference')),
                    DropdownMenuItem(value: 'decision', child: Text('Past Decision')),
                    DropdownMenuItem(value: 'context', child: Text('Task Context')),
                  ],
                  onChanged: (val) {
                    if (val != null) setModalState(() => selectedType = val);
                  },
                ),
              ],
            ),
          ),
          actions: [
            TextButton(
              child: const Text('Cancel'),
              onPressed: () => Navigator.of(ctx).pop(),
            ),
            ElevatedButton(
              style: ElevatedButton.styleFrom(backgroundColor: AppTheme.primary, foregroundColor: Colors.white),
              child: const Text('Save'),
              onPressed: () {
                if (contentCtrl.text.trim().isNotEmpty) {
                  ref.read(memoryProvider.notifier).addMemory(
                    content: contentCtrl.text.trim(),
                    type: selectedType,
                  );
                  Navigator.of(ctx).pop();
                }
              },
            ),
          ],
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final state = ref.watch(memoryProvider);
    final isDark = Theme.of(context).brightness == Brightness.dark;

    final filtered = state.filterType == null
        ? state.memories
        : state.memories.where((m) => m.type == state.filterType).toList();

    return Padding(
      padding: const EdgeInsets.all(24),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Text('Agent Long-Term Memory', style: TextStyle(fontSize: 20, fontWeight: FontWeight.bold)),
                    const SizedBox(height: 4),
                    Text(
                      'Stored facts, learned preferences, and episodic turn outcomes.',
                      style: TextStyle(fontSize: 12, color: isDark ? AppTheme.textSecondaryDark : AppTheme.textSecondaryLight),
                    ),
                  ],
                ),
              ),
              const SizedBox(width: 12),
              ElevatedButton.icon(
                icon: const Icon(Icons.add, size: 16),
                label: const Text('Add Memory'),
                style: ElevatedButton.styleFrom(
                  backgroundColor: AppTheme.primary,
                  foregroundColor: Colors.white,
                  shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
                ),
                onPressed: () => _showAddMemoryDialog(context, ref),
              ),
            ],
          ),
          const SizedBox(height: 16),

          // Filter chips
          Wrap(
            spacing: 8,
            children: [
              ChoiceChip(
                label: const Text('All'),
                selected: state.filterType == null,
                onSelected: (_) => ref.read(memoryProvider.notifier).setFilterType(null),
              ),
              ChoiceChip(
                label: const Text('Preferences'),
                selected: state.filterType == 'preference',
                onSelected: (_) => ref.read(memoryProvider.notifier).setFilterType('preference'),
              ),
              ChoiceChip(
                label: const Text('Facts'),
                selected: state.filterType == 'fact',
                onSelected: (_) => ref.read(memoryProvider.notifier).setFilterType('fact'),
              ),
              ChoiceChip(
                label: const Text('Decisions'),
                selected: state.filterType == 'decision',
                onSelected: (_) => ref.read(memoryProvider.notifier).setFilterType('decision'),
              ),
            ],
          ),
          const SizedBox(height: 16),

          // Memory Items
          Expanded(
            child: state.isLoading
                ? const Center(child: CircularProgressIndicator())
                : filtered.isEmpty
                    ? const Center(child: Text('No memories recorded for this filter.'))
                    : ListView.builder(
                        itemCount: filtered.length,
                        itemBuilder: (context, index) {
                          final item = filtered[index];

                          return Container(
                            margin: const EdgeInsets.only(bottom: 10),
                            padding: const EdgeInsets.all(14),
                            decoration: BoxDecoration(
                              color: isDark ? AppTheme.surfaceDark : AppTheme.surfaceLight,
                              borderRadius: BorderRadius.circular(8),
                              border: Border.all(
                                color: isDark ? AppTheme.borderDark : AppTheme.borderLight,
                              ),
                            ),
                            child: Row(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                Container(
                                  padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                                  decoration: BoxDecoration(
                                    color: AppTheme.accent.withValues(alpha: 0.15),
                                    borderRadius: BorderRadius.circular(4),
                                  ),
                                  child: Text(
                                    item.type.toUpperCase(),
                                    style: const TextStyle(fontSize: 10, fontWeight: FontWeight.bold, color: AppTheme.accent),
                                  ),
                                ),
                                const SizedBox(width: 12),
                                Expanded(
                                  child: Column(
                                    crossAxisAlignment: CrossAxisAlignment.start,
                                    children: [
                                      Text(item.content, style: const TextStyle(fontSize: 13, height: 1.4)),
                                      const SizedBox(height: 6),
                                      Text(
                                        'Confidence: ${(item.confidence * 100).toInt()}% • Created: ${DateFormatter.formatIso(item.createdAt)}',
                                        style: const TextStyle(fontSize: 10, color: Colors.grey),
                                      ),
                                    ],
                                  ),
                                ),
                                IconButton(
                                  icon: const Icon(Icons.delete_outline, size: 16, color: Colors.grey),
                                  tooltip: 'Delete Memory',
                                  onPressed: () => ref.read(memoryProvider.notifier).deleteMemory(item.id),
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
