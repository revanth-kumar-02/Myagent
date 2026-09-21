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
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
          title: const Text('Add Memory Record', style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold)),
          content: SizedBox(
            width: 420,
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                TextField(
                  controller: contentCtrl,
                  maxLines: 3,
                  decoration: InputDecoration(
                    labelText: 'Memory Content',
                    hintText: 'e.g. User prefers concise answers with Python code examples.',
                    border: OutlineInputBorder(borderRadius: BorderRadius.circular(10)),
                  ),
                ),
                const SizedBox(height: 14),
                DropdownButtonFormField<String>(
                  value: selectedType,
                  decoration: InputDecoration(
                    labelText: 'Memory Type',
                    border: OutlineInputBorder(borderRadius: BorderRadius.circular(10)),
                  ),
                  items: const [
                    DropdownMenuItem(value: 'fact', child: Text('Fact / Knowledge')),
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
              style: ElevatedButton.styleFrom(
                backgroundColor: AppTheme.sageGreen,
                foregroundColor: Colors.white,
                shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
              ),
              child: const Text('Save Record'),
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

  Color _badgeBgForType(String type, bool isDark) {
    switch (type) {
      case 'preference':
        return AppTheme.terracotta.withValues(alpha: 0.12);
      case 'fact':
        return AppTheme.sageGreen.withValues(alpha: 0.12);
      case 'decision':
        return AppTheme.softOlive.withValues(alpha: 0.14);
      default:
        return AppTheme.statusSearching.withValues(alpha: 0.12);
    }
  }

  Color _badgeTextColorForType(String type) {
    switch (type) {
      case 'preference':
        return AppTheme.terracotta;
      case 'fact':
        return AppTheme.sageGreen;
      case 'decision':
        return AppTheme.softOlive;
      default:
        return AppTheme.statusSearching;
    }
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
                    const Text(
                      'Agent Long-Term Memory',
                      style: TextStyle(fontSize: 20, fontWeight: FontWeight.bold, letterSpacing: -0.3),
                    ),
                    const SizedBox(height: 4),
                    Text(
                      'Episodic facts, user preferences, and agent-learned context across sessions.',
                      style: TextStyle(
                        fontSize: 12,
                        color: isDark ? AppTheme.textSecondaryDark : AppTheme.textSecondaryLight,
                      ),
                    ),
                  ],
                ),
              ),
              const SizedBox(width: 12),
              ElevatedButton.icon(
                icon: const Icon(Icons.add, size: 16),
                label: const Text('Add Memory'),
                style: ElevatedButton.styleFrom(
                  backgroundColor: AppTheme.sageGreen,
                  foregroundColor: Colors.white,
                  elevation: 0,
                  shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
                ),
                onPressed: () => _showAddMemoryDialog(context, ref),
              ),
            ],
          ),
          const SizedBox(height: 18),

          // Filter chips
          Wrap(
            spacing: 8,
            children: [
              _buildFilterChip(context, ref, label: 'All', value: null, selected: state.filterType == null),
              _buildFilterChip(context, ref, label: 'Preferences', value: 'preference', selected: state.filterType == 'preference'),
              _buildFilterChip(context, ref, label: 'Facts', value: 'fact', selected: state.filterType == 'fact'),
              _buildFilterChip(context, ref, label: 'Decisions', value: 'decision', selected: state.filterType == 'decision'),
            ],
          ),
          const SizedBox(height: 18),

          // Memory Items
          Expanded(
            child: state.isLoading
                ? const Center(child: CircularProgressIndicator(color: AppTheme.sageGreen))
                : filtered.isEmpty
                    ? Center(
                        child: Column(
                          mainAxisSize: MainAxisSize.min,
                          children: [
                            Icon(Icons.psychology_outlined, size: 40, color: AppTheme.softOlive.withValues(alpha: 0.5)),
                            const SizedBox(height: 12),
                            Text(
                              'No memory records match this filter.',
                              style: TextStyle(
                                fontSize: 13,
                                color: isDark ? AppTheme.textSecondaryDark : AppTheme.textSecondaryLight,
                              ),
                            ),
                          ],
                        ),
                      )
                    : ListView.builder(
                        itemCount: filtered.length,
                        itemBuilder: (context, index) {
                          final item = filtered[index];
                          final badgeBg = _badgeBgForType(item.type, isDark);
                          final badgeText = _badgeTextColorForType(item.type);

                          return Container(
                            margin: const EdgeInsets.only(bottom: 10),
                            padding: const EdgeInsets.all(16),
                            decoration: BoxDecoration(
                              color: isDark ? AppTheme.surfaceDark : AppTheme.cardLight,
                              borderRadius: BorderRadius.circular(12),
                              border: Border.all(
                                color: isDark ? AppTheme.borderDark : AppTheme.borderLight,
                              ),
                              boxShadow: isDark
                                  ? []
                                  : [
                                      BoxShadow(
                                        color: Colors.black.withValues(alpha: 0.02),
                                        blurRadius: 4,
                                        offset: const Offset(0, 1),
                                      ),
                                    ],
                            ),
                            child: Row(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                Container(
                                  padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                                  decoration: BoxDecoration(
                                    color: badgeBg,
                                    borderRadius: BorderRadius.circular(6),
                                  ),
                                  child: Text(
                                    item.type.toUpperCase(),
                                    style: TextStyle(
                                      fontSize: 10,
                                      fontWeight: FontWeight.bold,
                                      color: badgeText,
                                      letterSpacing: 0.5,
                                    ),
                                  ),
                                ),
                                const SizedBox(width: 14),
                                Expanded(
                                  child: Column(
                                    crossAxisAlignment: CrossAxisAlignment.start,
                                    children: [
                                      Text(
                                        item.content,
                                        style: TextStyle(
                                          fontSize: 13,
                                          height: 1.4,
                                          color: isDark ? AppTheme.textPrimaryDark : AppTheme.charcoalText,
                                        ),
                                      ),
                                      const SizedBox(height: 6),
                                      Row(
                                        children: [
                                          Icon(
                                            Icons.shield_outlined,
                                            size: 11,
                                            color: isDark ? AppTheme.textSecondaryDark : AppTheme.textSecondaryLight,
                                          ),
                                          const SizedBox(width: 4),
                                          Text(
                                            'Confidence: ${(item.confidence * 100).toInt()}% • Created: ${DateFormatter.formatIso(item.createdAt)}',
                                            style: TextStyle(
                                              fontSize: 11,
                                              color: isDark ? AppTheme.textSecondaryDark : AppTheme.textSecondaryLight,
                                            ),
                                          ),
                                        ],
                                      ),
                                    ],
                                  ),
                                ),
                                IconButton(
                                  icon: Icon(
                                    Icons.delete_outline,
                                    size: 16,
                                    color: isDark ? AppTheme.textSecondaryDark : AppTheme.textSecondaryLight,
                                  ),
                                  hoverColor: AppTheme.terracotta.withValues(alpha: 0.1),
                                  tooltip: 'Delete Record',
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

  Widget _buildFilterChip(
    BuildContext context,
    WidgetRef ref, {
    required String label,
    required String? value,
    required bool selected,
  }) {
    return FilterChip(
      label: Text(label),
      selected: selected,
      selectedColor: AppTheme.sageGreen.withValues(alpha: 0.15),
      checkmarkColor: AppTheme.sageGreen,
      labelStyle: TextStyle(
        fontSize: 12,
        fontWeight: selected ? FontWeight.w600 : FontWeight.normal,
        color: selected ? AppTheme.sageGreen : null,
      ),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
      side: BorderSide(
        color: selected ? AppTheme.sageGreen : AppTheme.borderLight,
      ),
      onSelected: (_) => ref.read(memoryProvider.notifier).setFilterType(value),
    );
  }
}
