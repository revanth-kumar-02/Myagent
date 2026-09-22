import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/theme/app_theme.dart';
import '../../core/utils/date_formatter.dart';
import '../../models/memory_item.dart';
import '../../state/memory_state.dart';

class MemoryScreen extends ConsumerWidget {
  const MemoryScreen({super.key});

  void _showAddMemoryDialog(BuildContext context, WidgetRef ref) {
    final c = AppTheme.colors(context);
    final contentCtrl = TextEditingController();
    String selectedType = 'fact';

    showDialog(
      context: context,
      builder: (ctx) => StatefulBuilder(
        builder: (ctx, setModalState) => AlertDialog(
          backgroundColor: c.surface,
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
          title: Text('Add Memory Record', style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold, color: c.textPrimary)),
          content: SizedBox(
            width: 420,
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                TextField(
                  controller: contentCtrl,
                  maxLines: 3,
                  style: TextStyle(color: c.textPrimary),
                  decoration: InputDecoration(
                    labelText: 'Memory Content',
                    labelStyle: TextStyle(color: c.textSecondary),
                    hintText: 'e.g. User prefers concise answers with Python code examples.',
                    border: OutlineInputBorder(borderRadius: BorderRadius.circular(10)),
                  ),
                ),
                const SizedBox(height: 14),
                DropdownButtonFormField<String>(
                  value: selectedType,
                  dropdownColor: c.surface,
                  style: TextStyle(color: c.textPrimary),
                  decoration: InputDecoration(
                    labelText: 'Memory Type',
                    labelStyle: TextStyle(color: c.textSecondary),
                    border: OutlineInputBorder(borderRadius: BorderRadius.circular(10)),
                  ),
                  items: [
                    DropdownMenuItem(value: 'fact', child: Text('Fact / Knowledge', style: TextStyle(color: c.textPrimary))),
                    DropdownMenuItem(value: 'preference', child: Text('User Preference', style: TextStyle(color: c.textPrimary))),
                    DropdownMenuItem(value: 'decision', child: Text('Past Decision', style: TextStyle(color: c.textPrimary))),
                    DropdownMenuItem(value: 'context', child: Text('Task Context', style: TextStyle(color: c.textPrimary))),
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
              child: Text('Cancel', style: TextStyle(color: c.textSecondary)),
              onPressed: () => Navigator.of(ctx).pop(),
            ),
            ElevatedButton(
              style: ElevatedButton.styleFrom(
                backgroundColor: c.primary,
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

  Color _badgeBgForType(String type, KoraColors c) {
    switch (type) {
      case 'preference':
        return c.accent.withValues(alpha: 0.15);
      case 'fact':
        return c.primary.withValues(alpha: 0.15);
      case 'decision':
        return c.secondary.withValues(alpha: 0.15);
      default:
        return c.warning.withValues(alpha: 0.15);
    }
  }

  Color _badgeTextColorForType(String type, KoraColors c) {
    switch (type) {
      case 'preference':
        return c.accent;
      case 'fact':
        return c.primary;
      case 'decision':
        return c.secondary;
      default:
        return c.warning;
    }
  }

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final state = ref.watch(memoryProvider);
    final c = AppTheme.colors(context);

    final filtered = state.filterType == null
        ? state.memories
        : state.memories.where((m) => m.type == state.filterType).toList();

    return Container(
      color: c.bg,
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
                    Text(
                      'Agent Long-Term Memory',
                      style: TextStyle(fontSize: 20, fontWeight: FontWeight.bold, letterSpacing: -0.3, color: c.textPrimary),
                    ),
                    const SizedBox(height: 4),
                    Text(
                      'Episodic facts, user preferences, and agent-learned context across sessions.',
                      style: TextStyle(
                        fontSize: 12,
                        color: c.textSecondary,
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
                  backgroundColor: c.primary,
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
              _buildFilterChip(context, ref, label: 'All', value: null, selected: state.filterType == null, c: c),
              _buildFilterChip(context, ref, label: 'Preferences', value: 'preference', selected: state.filterType == 'preference', c: c),
              _buildFilterChip(context, ref, label: 'Facts', value: 'fact', selected: state.filterType == 'fact', c: c),
              _buildFilterChip(context, ref, label: 'Decisions', value: 'decision', selected: state.filterType == 'decision', c: c),
            ],
          ),
          const SizedBox(height: 18),

          // Memory Items
          Expanded(
            child: state.isLoading
                ? Center(child: CircularProgressIndicator(color: c.primary))
                : filtered.isEmpty
                    ? Center(
                        child: Column(
                          mainAxisSize: MainAxisSize.min,
                          children: [
                            Icon(Icons.psychology_outlined, size: 40, color: c.secondary.withValues(alpha: 0.5)),
                            const SizedBox(height: 12),
                            Text(
                              'No memory records match this filter.',
                              style: TextStyle(
                                fontSize: 13,
                                color: c.textSecondary,
                              ),
                            ),
                          ],
                        ),
                      )
                    : ListView.builder(
                        itemCount: filtered.length,
                        itemBuilder: (context, index) {
                          final item = filtered[index];
                          final badgeBg = _badgeBgForType(item.type, c);
                          final badgeText = _badgeTextColorForType(item.type, c);

                          return Container(
                            margin: const EdgeInsets.only(bottom: 10),
                            padding: const EdgeInsets.all(16),
                            decoration: BoxDecoration(
                              color: c.surface,
                              borderRadius: BorderRadius.circular(12),
                              border: Border.all(
                                color: c.border,
                              ),
                              boxShadow: [
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
                                          color: c.textPrimary,
                                        ),
                                      ),
                                      const SizedBox(height: 6),
                                      Row(
                                        children: [
                                          Icon(
                                            Icons.shield_outlined,
                                            size: 11,
                                            color: c.textSecondary,
                                          ),
                                          const SizedBox(width: 4),
                                          Text(
                                            'Confidence: ${(item.confidence * 100).toInt()}% • Created: ${DateFormatter.formatIso(item.createdAt)}',
                                            style: TextStyle(
                                              fontSize: 11,
                                              color: c.textSecondary,
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
                                    color: c.textSecondary,
                                  ),
                                  hoverColor: c.accent.withValues(alpha: 0.1),
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
    required KoraColors c,
  }) {
    return FilterChip(
      label: Text(label),
      selected: selected,
      selectedColor: c.primary.withValues(alpha: 0.15),
      checkmarkColor: c.primary,
      labelStyle: TextStyle(
        fontSize: 12,
        fontWeight: selected ? FontWeight.w600 : FontWeight.normal,
        color: selected ? c.primary : c.textPrimary,
      ),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
      side: BorderSide(
        color: selected ? c.primary : c.border,
      ),
      onSelected: (_) => ref.read(memoryProvider.notifier).setFilterType(value),
    );
  }
}
