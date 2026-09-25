import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/theme/app_theme.dart';
import '../../core/utils/date_formatter.dart';
import '../../models/memory_item.dart';
import '../../state/memory_state.dart';

class MemoryScreen extends ConsumerStatefulWidget {
  const MemoryScreen({super.key});

  @override
  ConsumerState<MemoryScreen> createState() => _MemoryScreenState();
}

class _MemoryScreenState extends ConsumerState<MemoryScreen> {
  final TextEditingController _searchCtrl = TextEditingController();

  @override
  void dispose() {
    _searchCtrl.dispose();
    super.dispose();
  }

  void _showCorrectMemoryDialog(BuildContext context, MemoryItem item) {
    final c = AppTheme.colors(context);
    final contentCtrl = TextEditingController(text: item.content);
    String selectedType = item.type;
    double confidence = item.confidence;

    showDialog(
      context: context,
      builder: (ctx) => StatefulBuilder(
        builder: (ctx, setModalState) => AlertDialog(
          backgroundColor: c.surface,
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
          title: Row(
            children: [
              Icon(Icons.edit_note_rounded, color: c.primary, size: 22),
              const SizedBox(width: 8),
              Text(
                'Correct Memory Record',
                style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold, color: c.textPrimary),
              ),
            ],
          ),
          content: SizedBox(
            width: 460,
            child: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  'Update or clarify what Kora remembered to ensure accurate future reasoning.',
                  style: TextStyle(fontSize: 12, color: c.textSecondary),
                ),
                const SizedBox(height: 14),
                TextField(
                  controller: contentCtrl,
                  maxLines: 3,
                  style: TextStyle(color: c.textPrimary, fontSize: 13),
                  decoration: InputDecoration(
                    labelText: 'Memory Content',
                    labelStyle: TextStyle(color: c.textSecondary),
                    filled: true,
                    fillColor: c.bg,
                    border: OutlineInputBorder(borderRadius: BorderRadius.circular(10), borderSide: BorderSide(color: c.border)),
                  ),
                ),
                const SizedBox(height: 14),
                DropdownButtonFormField<String>(
                  value: ['user_preference', 'user_profile_context', 'decision', 'project_context', 'workflow_pattern', 'agent_learning', 'fact', 'preference'].contains(selectedType)
                      ? selectedType
                      : 'user_preference',
                  dropdownColor: c.surface,
                  style: TextStyle(color: c.textPrimary, fontSize: 13),
                  decoration: InputDecoration(
                    labelText: 'Category',
                    labelStyle: TextStyle(color: c.textSecondary),
                    filled: true,
                    fillColor: c.bg,
                    border: OutlineInputBorder(borderRadius: BorderRadius.circular(10), borderSide: BorderSide(color: c.border)),
                  ),
                  items: [
                    DropdownMenuItem(value: 'user_preference', child: Text('Learned Preference', style: TextStyle(color: c.textPrimary))),
                    DropdownMenuItem(value: 'user_profile_context', child: Text('Important Fact / Profile', style: TextStyle(color: c.textPrimary))),
                    DropdownMenuItem(value: 'decision', child: Text('Decision', style: TextStyle(color: c.textPrimary))),
                    DropdownMenuItem(value: 'project_context', child: Text('Project Context', style: TextStyle(color: c.textPrimary))),
                    DropdownMenuItem(value: 'workflow_pattern', child: Text('Workflow Pattern', style: TextStyle(color: c.textPrimary))),
                    DropdownMenuItem(value: 'agent_learning', child: Text('Agent Learning', style: TextStyle(color: c.textPrimary))),
                  ],
                  onChanged: (val) {
                    if (val != null) setModalState(() => selectedType = val);
                  },
                ),
                const SizedBox(height: 16),
                Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    Text('Confidence Level', style: TextStyle(fontSize: 12, fontWeight: FontWeight.w600, color: c.textPrimary)),
                    Text('${(confidence * 100).toInt()}%', style: TextStyle(fontSize: 12, fontWeight: FontWeight.bold, color: c.primary)),
                  ],
                ),
                Slider(
                  value: confidence,
                  min: 0.1,
                  max: 1.0,
                  divisions: 18,
                  activeColor: c.primary,
                  inactiveColor: c.border,
                  onChanged: (val) => setModalState(() => confidence = val),
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
              child: const Text('Save Correction'),
              onPressed: () {
                if (contentCtrl.text.trim().isNotEmpty) {
                  ref.read(memoryProvider.notifier).correctMemory(
                    item.id,
                    content: contentCtrl.text.trim(),
                    type: selectedType,
                    confidence: confidence,
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

  void _showForgetDialog(BuildContext context, MemoryItem item) {
    final c = AppTheme.colors(context);
    showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        backgroundColor: c.surface,
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
        title: Row(
          children: [
            Icon(Icons.delete_forever_rounded, color: c.accent, size: 22),
            const SizedBox(width: 8),
            Text('Forget Memory?', style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold, color: c.textPrimary)),
          ],
        ),
        content: Text(
          'Are you sure you want Kora to forget this memory?\n\n"${item.content}"\n\nThis will remove it from both vector storage and knowledge graph reasoning.',
          style: TextStyle(fontSize: 13, height: 1.4, color: c.textSecondary),
        ),
        actions: [
          TextButton(
            child: Text('Cancel', style: TextStyle(color: c.textSecondary)),
            onPressed: () => Navigator.of(ctx).pop(),
          ),
          ElevatedButton(
            style: ElevatedButton.styleFrom(
              backgroundColor: c.accent,
              foregroundColor: Colors.white,
              shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
            ),
            child: const Text('Forget Permanently'),
            onPressed: () {
              ref.read(memoryProvider.notifier).forgetMemory(item.id);
              Navigator.of(ctx).pop();
            },
          ),
        ],
      ),
    );
  }

  Color _badgeBgForType(String type, KoraColors c) {
    switch (type.toLowerCase()) {
      case 'user_preference':
      case 'preference':
        return c.accent.withValues(alpha: 0.15);
      case 'user_profile_context':
      case 'fact':
        return c.primary.withValues(alpha: 0.15);
      case 'decision':
        return c.secondary.withValues(alpha: 0.15);
      case 'project_context':
        return c.primary.withValues(alpha: 0.2);
      case 'workflow_pattern':
        return c.warning.withValues(alpha: 0.15);
      default:
        return c.secondary.withValues(alpha: 0.12);
    }
  }

  Color _badgeTextColorForType(String type, KoraColors c) {
    switch (type.toLowerCase()) {
      case 'user_preference':
      case 'preference':
        return c.accent;
      case 'user_profile_context':
      case 'fact':
        return c.primary;
      case 'decision':
        return c.secondary;
      case 'project_context':
        return c.primary;
      case 'workflow_pattern':
        return c.warning;
      default:
        return c.secondary;
    }
  }

  String _formatTypeLabel(String type) {
    switch (type.toLowerCase()) {
      case 'user_preference':
      case 'preference':
        return 'PREFERENCE';
      case 'user_profile_context':
      case 'fact':
        return 'PROFILE & FACT';
      case 'decision':
        return 'DECISION';
      case 'project_context':
        return 'PROJECT CONTEXT';
      case 'workflow_pattern':
        return 'WORKFLOW';
      case 'agent_learning':
        return 'AGENT LEARNING';
      default:
        return type.toUpperCase().replaceAll('_', ' ');
    }
  }

  @override
  Widget build(BuildContext context) {
    final state = ref.watch(memoryProvider);
    final c = AppTheme.colors(context);

    // Filter logic
    final isGraphTab = state.filterType == 'graph';
    final query = _searchCtrl.text.trim().toLowerCase();

    List<MemoryItem> filtered = state.memories;
    if (state.filterType != null && state.filterType != 'all' && !isGraphTab) {
      filtered = filtered.where((m) {
        final t = m.type.toLowerCase();
        final filter = state.filterType!.toLowerCase();
        if (filter == 'user_preference') return t == 'user_preference' || t == 'preference';
        if (filter == 'user_profile_context') return t == 'user_profile_context' || t == 'fact';
        return t == filter;
      }).toList();
    }

    if (query.isNotEmpty) {
      filtered = filtered.where((m) => m.content.toLowerCase().contains(query)).toList();
    }

    // Use server-side stats when available; fall back to local counts
    final activeCount = state.activeCount > 0
        ? state.activeCount
        : state.memories.where((m) => m.isActive).length;
    final avgConf = state.avgConfidence > 0
        ? (state.avgConfidence * 100).toInt()
        : (state.memories.isEmpty
            ? 0
            : (state.memories.map((m) => m.confidence).reduce((a, b) => a + b) /
                    state.memories.length *
                    100)
                .toInt());

    return Container(
      color: c.bg,
      padding: const EdgeInsets.all(24),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Header Row
          Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      children: [
                        Text(
                          'MEMORY & KNOWLEDGE',
                          style: TextStyle(
                            fontSize: 20,
                            fontWeight: FontWeight.w800,
                            letterSpacing: -0.3,
                            color: c.textPrimary,
                          ),
                        ),
                        const SizedBox(width: 10),
                        Container(
                          padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
                          decoration: BoxDecoration(
                            color: c.primary.withValues(alpha: 0.12),
                            borderRadius: BorderRadius.circular(12),
                          ),
                          child: Text(
                            'Auto-Learning',
                            style: TextStyle(
                              fontSize: 10,
                              fontWeight: FontWeight.bold,
                              color: c.primary,
                            ),
                          ),
                        ),
                      ],
                    ),
                    const SizedBox(height: 4),
                    Text(
                      'Kora automatically extracts, validates, and refines durable preferences, decisions, and knowledge graph relations.',
                      style: TextStyle(fontSize: 12, color: c.textSecondary),
                    ),
                  ],
                ),
              ),
              IconButton(
                icon: Icon(Icons.refresh_rounded, size: 20, color: c.textSecondary),
                tooltip: 'Refresh Memories',
                onPressed: () => ref.read(memoryProvider.notifier).loadMemories(),
              ),
            ],
          ),
          const SizedBox(height: 16),

          // Telemetry & Stats Bar
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
            decoration: BoxDecoration(
              color: c.surface,
              borderRadius: BorderRadius.circular(12),
              border: Border.all(color: c.border),
            ),
            child: Row(
              children: [
                _buildStatItem('Active Memories', '$activeCount', Icons.psychology_outlined, c.primary, c),
                _buildStatDivider(c),
                _buildStatItem('Graph Entities', '${state.entities.length}', Icons.hub_outlined, c.secondary, c),
                _buildStatDivider(c),
                _buildStatItem('Relationships', '${state.relationships.length}', Icons.share_outlined, c.accent, c),
                _buildStatDivider(c),
                _buildStatItem('Avg Confidence', '$avgConf%', Icons.verified_outlined, c.primary, c),

              ],
            ),
          ),
          const SizedBox(height: 16),

          // Search & Filter Row
          Row(
            children: [
              Expanded(
                child: SizedBox(
                  height: 38,
                  child: TextField(
                    controller: _searchCtrl,
                    style: TextStyle(fontSize: 13, color: c.textPrimary),
                    decoration: InputDecoration(
                      hintText: 'Search learned memories or facts...',
                      hintStyle: TextStyle(fontSize: 12, color: c.textSecondary),
                      prefixIcon: Icon(Icons.search_rounded, size: 18, color: c.textSecondary),
                      filled: true,
                      fillColor: c.surface,
                      contentPadding: EdgeInsets.zero,
                      border: OutlineInputBorder(borderRadius: BorderRadius.circular(10), borderSide: BorderSide(color: c.border)),
                      enabledBorder: OutlineInputBorder(borderRadius: BorderRadius.circular(10), borderSide: BorderSide(color: c.border)),
                    ),
                    onChanged: (val) => setState(() {}),
                  ),
                ),
              ),
            ],
          ),
          const SizedBox(height: 12),

          // Category Tabs / Filter Chips
          Wrap(
            spacing: 6,
            runSpacing: 6,
            children: [
              _buildTabChip(label: 'All Memories', value: 'all', selected: state.filterType == null || state.filterType == 'all', c: c),
              _buildTabChip(label: 'Learned Preferences', value: 'user_preference', selected: state.filterType == 'user_preference', c: c),
              _buildTabChip(label: 'Important Facts', value: 'user_profile_context', selected: state.filterType == 'user_profile_context', c: c),
              _buildTabChip(label: 'Decisions', value: 'decision', selected: state.filterType == 'decision', c: c),
              _buildTabChip(label: 'Project Context', value: 'project_context', selected: state.filterType == 'project_context', c: c),
              _buildTabChip(label: 'Workflow Patterns', value: 'workflow_pattern', selected: state.filterType == 'workflow_pattern', c: c),
              _buildTabChip(label: 'Entities & Graph', value: 'graph', selected: state.filterType == 'graph', c: c, icon: Icons.hub_rounded),
            ],
          ),
          const SizedBox(height: 16),

          // Main Content View (Graph View vs Memory List)
          Expanded(
            child: state.isLoading
                ? Center(child: CircularProgressIndicator(color: c.primary))
                : isGraphTab
                    ? _buildKnowledgeGraphView(state, c)
                    : filtered.isEmpty
                        ? _buildEmptyState(c)
                        : ListView.builder(
                            itemCount: filtered.length,
                            itemBuilder: (context, index) {
                              final item = filtered[index];
                              return _buildMemoryCard(item, c);
                            },
                          ),
          ),
        ],
      ),
    );
  }

  Widget _buildStatItem(String label, String value, IconData icon, Color color, KoraColors c) {
    return Expanded(
      child: Row(
        children: [
          Container(
            padding: const EdgeInsets.all(6),
            decoration: BoxDecoration(
              color: color.withValues(alpha: 0.12),
              borderRadius: BorderRadius.circular(8),
            ),
            child: Icon(icon, size: 16, color: color),
          ),
          const SizedBox(width: 10),
          Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            mainAxisSize: MainAxisSize.min,
            children: [
              Text(
                value,
                style: TextStyle(fontSize: 14, fontWeight: FontWeight.bold, color: c.textPrimary),
              ),
              Text(
                label,
                style: TextStyle(fontSize: 10, color: c.textSecondary),
              ),
            ],
          ),
        ],
      ),
    );
  }

  Widget _buildStatDivider(KoraColors c) {
    return Container(
      width: 1,
      height: 24,
      margin: const EdgeInsets.symmetric(horizontal: 12),
      color: c.border,
    );
  }

  Widget _buildTabChip({
    required String label,
    required String value,
    required bool selected,
    required KoraColors c,
    IconData? icon,
  }) {
    return InkWell(
      borderRadius: BorderRadius.circular(8),
      onTap: () => ref.read(memoryProvider.notifier).setFilterType(value),
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 7),
        decoration: BoxDecoration(
          color: selected ? c.primary.withValues(alpha: 0.15) : c.surface,
          borderRadius: BorderRadius.circular(8),
          border: Border.all(color: selected ? c.primary : c.border),
        ),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            if (icon != null) ...[
              Icon(icon, size: 14, color: selected ? c.primary : c.textSecondary),
              const SizedBox(width: 6),
            ],
            Text(
              label,
              style: TextStyle(
                fontSize: 11,
                fontWeight: selected ? FontWeight.w700 : FontWeight.w500,
                color: selected ? c.primary : c.textPrimary,
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildMemoryCard(MemoryItem item, KoraColors c) {
    final badgeBg = _badgeBgForType(item.type, c);
    final badgeText = _badgeTextColorForType(item.type, c);

    return Container(
      margin: const EdgeInsets.only(bottom: 12),
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: c.surface,
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: c.border),
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
        children: [
          // Top metadata row
          Row(
            children: [
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                decoration: BoxDecoration(
                  color: badgeBg,
                  borderRadius: BorderRadius.circular(6),
                ),
                child: Text(
                  _formatTypeLabel(item.type),
                  style: TextStyle(
                    fontSize: 10,
                    fontWeight: FontWeight.bold,
                    color: badgeText,
                    letterSpacing: 0.4,
                  ),
                ),
              ),
              const SizedBox(width: 8),
              // Status Pill
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 7, vertical: 3),
                decoration: BoxDecoration(
                  color: item.isActive ? c.primary.withValues(alpha: 0.1) : c.border,
                  borderRadius: BorderRadius.circular(6),
                ),
                child: Text(
                  item.isActive ? 'ACTIVE' : 'ARCHIVED',
                  style: TextStyle(
                    fontSize: 9,
                    fontWeight: FontWeight.w600,
                    color: item.isActive ? c.primary : c.textSecondary,
                  ),
                ),
              ),
              const SizedBox(width: 8),
              // Scope Pill
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 7, vertical: 3),
                decoration: BoxDecoration(
                  color: c.bg,
                  borderRadius: BorderRadius.circular(6),
                  border: Border.all(color: c.border),
                ),
                child: Text(
                  item.projectId == null || item.projectId == 'default-project' ? 'Global Scope' : 'Project Scope',
                  style: TextStyle(fontSize: 9, color: c.textSecondary),
                ),
              ),
              const Spacer(),
              // Actions
              IconButton(
                icon: Icon(
                  item.isActive ? Icons.archive_outlined : Icons.unarchive_outlined,
                  size: 16,
                  color: c.textSecondary,
                ),
                tooltip: item.isActive ? 'Disable / Archive Memory' : 'Enable Memory',
                hoverColor: c.primary.withValues(alpha: 0.1),
                onPressed: () => ref.read(memoryProvider.notifier).toggleMemoryStatus(item.id),
              ),
              IconButton(
                icon: Icon(Icons.edit_outlined, size: 16, color: c.textSecondary),
                tooltip: 'Correct / Edit Memory',
                hoverColor: c.primary.withValues(alpha: 0.1),
                onPressed: () => _showCorrectMemoryDialog(context, item),
              ),
              IconButton(
                icon: Icon(Icons.delete_outline, size: 16, color: c.accent),
                tooltip: 'Forget Memory',
                hoverColor: c.accent.withValues(alpha: 0.1),
                onPressed: () => _showForgetDialog(context, item),
              ),
            ],
          ),
          const SizedBox(height: 10),

          // Content
          Text(
            item.content,
            style: TextStyle(
              fontSize: 13,
              height: 1.45,
              fontWeight: FontWeight.w500,
              color: item.isActive ? c.textPrimary : c.textSecondary,
            ),
          ),
          const SizedBox(height: 12),

          // Bottom Details & Telemetry
          Row(
            children: [
              Icon(Icons.shield_outlined, size: 12, color: c.textSecondary),
              const SizedBox(width: 4),
              Text(
                'Confidence: ${(item.confidence * 100).toInt()}%',
                style: TextStyle(fontSize: 11, fontWeight: FontWeight.w600, color: c.textSecondary),
              ),
              const SizedBox(width: 12),
              Icon(Icons.source_outlined, size: 12, color: c.textSecondary),
              const SizedBox(width: 4),
              Text(
                'Source: ${item.source.replaceAll('_', ' ')}',
                style: TextStyle(fontSize: 11, color: c.textSecondary),
              ),
              const Spacer(),
              Text(
                'Learned: ${DateFormatter.formatIso(item.createdAt)}',
                style: TextStyle(fontSize: 10, color: c.textSecondary),
              ),
            ],
          ),
        ],
      ),
    );
  }

  Widget _buildKnowledgeGraphView(MemoryState state, KoraColors c) {
    if (state.entities.isEmpty && state.relationships.isEmpty) {
      return Center(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(Icons.hub_outlined, size: 48, color: c.secondary.withValues(alpha: 0.4)),
            const SizedBox(height: 12),
            Text(
              'No Knowledge Graph relationships mapped yet.',
              style: TextStyle(fontSize: 14, fontWeight: FontWeight.w600, color: c.textPrimary),
            ),
            const SizedBox(height: 4),
            Text(
              'As memories and entities are formed, Kora maps semantic connections here.',
              style: TextStyle(fontSize: 12, color: c.textSecondary),
            ),
          ],
        ),
      );
    }

    return SingleChildScrollView(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            'Extracted Knowledge Entities',
            style: TextStyle(fontSize: 13, fontWeight: FontWeight.bold, color: c.textPrimary),
          ),
          const SizedBox(height: 8),
          Wrap(
            spacing: 8,
            runSpacing: 8,
            children: state.entities.map((e) {
              return Container(
                padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
                decoration: BoxDecoration(
                  color: c.surface,
                  borderRadius: BorderRadius.circular(8),
                  border: Border.all(color: c.border),
                ),
                child: Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Icon(
                      e.type == 'person' ? Icons.person_outline : (e.type == 'technology' ? Icons.code_rounded : Icons.lightbulb_outline),
                      size: 14,
                      color: c.primary,
                    ),
                    const SizedBox(width: 6),
                    Text(
                      e.name,
                      style: TextStyle(fontSize: 12, fontWeight: FontWeight.w600, color: c.textPrimary),
                    ),
                    const SizedBox(width: 4),
                    Text(
                      '(${e.type})',
                      style: TextStyle(fontSize: 10, color: c.textSecondary),
                    ),
                  ],
                ),
              );
            }).toList(),
          ),
          const SizedBox(height: 20),
          Text(
            'Semantic Graph Relationships',
            style: TextStyle(fontSize: 13, fontWeight: FontWeight.bold, color: c.textPrimary),
          ),
          const SizedBox(height: 8),
          ...state.relationships.map((r) {
            return Container(
              margin: const EdgeInsets.only(bottom: 8),
              padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
              decoration: BoxDecoration(
                color: c.surface,
                borderRadius: BorderRadius.circular(10),
                border: Border.all(color: c.border),
              ),
              child: Row(
                children: [
                  Container(
                    padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                    decoration: BoxDecoration(
                      color: c.primary.withValues(alpha: 0.12),
                      borderRadius: BorderRadius.circular(6),
                    ),
                    child: Text(
                      r.source,
                      style: TextStyle(fontSize: 11, fontWeight: FontWeight.bold, color: c.primary),
                    ),
                  ),
                  Padding(
                    padding: const EdgeInsets.symmetric(horizontal: 8),
                    child: Row(
                      children: [
                        Icon(Icons.arrow_right_alt_rounded, size: 18, color: c.textSecondary),
                        Text(
                          ' [${r.type}] ',
                          style: TextStyle(fontSize: 11, fontStyle: FontStyle.italic, color: c.accent),
                        ),
                        Icon(Icons.arrow_right_alt_rounded, size: 18, color: c.textSecondary),
                      ],
                    ),
                  ),
                  Container(
                    padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                    decoration: BoxDecoration(
                      color: c.secondary.withValues(alpha: 0.12),
                      borderRadius: BorderRadius.circular(6),
                    ),
                    child: Text(
                      r.target,
                      style: TextStyle(fontSize: 11, fontWeight: FontWeight.bold, color: c.secondary),
                    ),
                  ),
                  const Spacer(),
                  Text(
                    '${(r.confidence * 100).toInt()}% conf',
                    style: TextStyle(fontSize: 10, color: c.textSecondary),
                  ),
                ],
              ),
            );
          }),
        ],
      ),
    );
  }

  Widget _buildEmptyState(KoraColors c) {
    return Center(
      child: Container(
        constraints: const BoxConstraints(maxWidth: 440),
        padding: const EdgeInsets.all(24),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Container(
              padding: const EdgeInsets.all(16),
              decoration: BoxDecoration(
                color: c.primary.withValues(alpha: 0.08),
                shape: BoxShape.circle,
              ),
              child: Icon(
                Icons.psychology_outlined,
                size: 40,
                color: c.primary,
              ),
            ),
            const SizedBox(height: 16),
            Text(
              "Kora hasn't learned anything important yet.",
              textAlign: TextAlign.center,
              style: TextStyle(
                fontSize: 15,
                fontWeight: FontWeight.bold,
                letterSpacing: -0.2,
                color: c.textPrimary,
              ),
            ),
            const SizedBox(height: 8),
            Text(
              'As you collaborate, Kora automatically detects preferences, key facts, decisions, and workflow patterns without manual note-taking.',
              textAlign: TextAlign.center,
              style: TextStyle(
                fontSize: 12,
                height: 1.45,
                color: c.textSecondary,
              ),
            ),
          ],
        ),
      ),
    );
  }
}
