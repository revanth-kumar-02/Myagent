import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/theme/app_theme.dart';
import '../../models/project.dart';
import '../../services/project/file_type_detector.dart';
import '../../services/project/project_service.dart';
import '../../state/projects_state.dart';
import 'file_preview_modal.dart';

class ProjectDetailScreen extends ConsumerStatefulWidget {
  final Project project;

  const ProjectDetailScreen({super.key, required this.project});

  @override
  ConsumerState<ProjectDetailScreen> createState() => _ProjectDetailScreenState();
}

class _ProjectDetailScreenState extends ConsumerState<ProjectDetailScreen> {
  List<ProjectTreeEntry> _treeEntries = [];
  bool _isLoadingTree = false;
  final Set<String> _expandedFolders = {};
  final Map<String, List<ProjectTreeEntry>> _subfolderEntries = {};

  @override
  void initState() {
    super.initState();
    _loadTree();
  }

  Future<void> _loadTree() async {
    setState(() => _isLoadingTree = true);
    try {
      final entries = await ref.read(projectsProvider.notifier).getProjectTree(widget.project.rootPath);
      if (mounted) {
        setState(() {
          _treeEntries = entries;
          _isLoadingTree = false;
        });
      }
    } catch (_) {
      if (mounted) setState(() => _isLoadingTree = false);
    }
  }

  Future<void> _toggleFolder(ProjectTreeEntry entry) async {
    final path = entry.relativePath;
    if (_expandedFolders.contains(path)) {
      setState(() {
        _expandedFolders.remove(path);
      });
      return;
    }

    setState(() => _expandedFolders.add(path));

    if (!_subfolderEntries.containsKey(path)) {
      try {
        final subEntries = await ref
            .read(projectsProvider.notifier)
            .getProjectTree(widget.project.rootPath, subPath: path);
        if (mounted) {
          setState(() {
            _subfolderEntries[path] = subEntries;
          });
        }
      } catch (_) {}
    }
  }

  String _formatBytes(int bytes) {
    if (bytes <= 0) return '';
    if (bytes < 1024) return '$bytes B';
    if (bytes < 1024 * 1024) return '${(bytes / 1024).toStringAsFixed(1)} KB';
    return '${(bytes / (1024 * 1024)).toStringAsFixed(1)} MB';
  }

  @override
  Widget build(BuildContext context) {
    final c = AppTheme.colors(context);
    final p = widget.project;

    return Container(
      color: c.bg,
      padding: const EdgeInsets.symmetric(horizontal: 28, vertical: 24),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Navigation & Actions Header
          Row(
            children: [
              OutlinedButton.icon(
                icon: const Icon(Icons.arrow_back_rounded, size: 16),
                label: const Text('Back to Projects'),
                style: OutlinedButton.styleFrom(
                  foregroundColor: c.textPrimary,
                  side: BorderSide(color: c.border),
                  padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
                  shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
                ),
                onPressed: () => ref.read(projectsProvider.notifier).selectProject(null),
              ),
              const Spacer(),
              ElevatedButton.icon(
                icon: const Icon(Icons.code_rounded, size: 15),
                label: const Text('VS Code'),
                style: ElevatedButton.styleFrom(
                  backgroundColor: c.surfaceHighlight,
                  foregroundColor: c.textPrimary,
                  elevation: 0,
                  side: BorderSide(color: c.border),
                  padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
                  shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
                ),
                onPressed: () => ref.read(projectsProvider.notifier).openInVSCode(p.rootPath),
              ),
              const SizedBox(width: 8),
              ElevatedButton.icon(
                icon: const Icon(Icons.folder_open_rounded, size: 15),
                label: const Text('File Explorer'),
                style: ElevatedButton.styleFrom(
                  backgroundColor: c.primary,
                  foregroundColor: Colors.white,
                  elevation: 0,
                  padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
                  shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
                ),
                onPressed: () => ref.read(projectsProvider.notifier).openInFileExplorer(p.rootPath),
              ),
            ],
          ),
          const SizedBox(height: 20),

          // Project Title & Overview Banner
          Container(
            padding: const EdgeInsets.all(20),
            decoration: BoxDecoration(
              color: c.surface,
              borderRadius: BorderRadius.circular(12),
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
                Row(
                  crossAxisAlignment: CrossAxisAlignment.center,
                  children: [
                    Container(
                      width: 44,
                      height: 44,
                      decoration: BoxDecoration(
                        color: c.primaryLight,
                        borderRadius: BorderRadius.circular(10),
                      ),
                      child: Icon(Icons.folder_rounded, size: 24, color: c.primary),
                    ),
                    const SizedBox(width: 14),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Row(
                            children: [
                              Text(
                                p.name,
                                style: TextStyle(
                                  fontSize: 20,
                                  fontWeight: FontWeight.w800,
                                  color: c.textPrimary,
                                ),
                              ),
                              const SizedBox(width: 10),
                              Container(
                                padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                                decoration: BoxDecoration(
                                  color: c.secondaryLight,
                                  borderRadius: BorderRadius.circular(6),
                                ),
                                child: Text(
                                  p.projectType,
                                  style: TextStyle(
                                    fontSize: 11,
                                    fontWeight: FontWeight.w700,
                                    color: c.secondaryDark,
                                  ),
                                ),
                              ),
                            ],
                          ),
                          const SizedBox(height: 4),
                          Row(
                            children: [
                              Expanded(
                                child: Text(
                                  p.rootPath,
                                  style: TextStyle(fontSize: 12, color: c.textMuted),
                                  overflow: TextOverflow.ellipsis,
                                ),
                              ),
                              IconButton(
                                icon: const Icon(Icons.copy_rounded, size: 13),
                                tooltip: 'Copy path',
                                visualDensity: VisualDensity.compact,
                                padding: EdgeInsets.zero,
                                constraints: const BoxConstraints(minWidth: 20, minHeight: 20),
                                onPressed: () {
                                  Clipboard.setData(ClipboardData(text: p.rootPath));
                                  ScaffoldMessenger.of(context).showSnackBar(
                                    const SnackBar(content: Text('Project path copied to clipboard')),
                                  );
                                },
                              ),
                            ],
                          ),
                        ],
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 16),
                const Divider(height: 1),
                const SizedBox(height: 14),

                // Statistics row
                Wrap(
                  spacing: 24,
                  runSpacing: 12,
                  children: [
                    _buildStatPill('Files', '${p.fileCount}', Icons.insert_drive_file_outlined, c),
                    _buildStatPill('Folders', '${p.folderCount}', Icons.folder_outlined, c),
                    _buildStatPill('Git', p.gitStatus, Icons.source_rounded, c),
                    if (p.lastModified.isNotEmpty)
                      _buildStatPill('Last Modified', p.lastModified, Icons.access_time_rounded, c),
                  ],
                ),

                if (p.detectedLanguages.isNotEmpty) ...[
                  const SizedBox(height: 14),
                  Row(
                    crossAxisAlignment: CrossAxisAlignment.center,
                    children: [
                      Text(
                        'Languages:',
                        style: TextStyle(fontSize: 12, fontWeight: FontWeight.w600, color: c.textSecondary),
                      ),
                      const SizedBox(width: 8),
                      Expanded(
                        child: Wrap(
                          spacing: 6,
                          runSpacing: 4,
                          children: p.detectedLanguages.map((lang) {
                            return Container(
                              padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                              decoration: BoxDecoration(
                                color: c.primaryLight,
                                borderRadius: BorderRadius.circular(6),
                                border: Border.all(color: c.primary.withValues(alpha: 0.15)),
                              ),
                              child: Text(
                                lang,
                                style: TextStyle(
                                  fontSize: 11,
                                  fontWeight: FontWeight.w600,
                                  color: c.primary,
                                ),
                              ),
                            );
                          }).toList(),
                        ),
                      ),
                    ],
                  ),
                ],
              ],
            ),
          ),
          const SizedBox(height: 20),

          // Real Directory Files Tree
          Text(
            'Filesystem Structure',
            style: TextStyle(
              fontSize: 15,
              fontWeight: FontWeight.w800,
              letterSpacing: -0.2,
              color: c.textPrimary,
            ),
          ),
          const SizedBox(height: 8),

          Expanded(
            child: Container(
              decoration: BoxDecoration(
                color: c.surface,
                borderRadius: BorderRadius.circular(12),
                border: Border.all(color: c.border),
              ),
              child: _isLoadingTree
                  ? Center(child: CircularProgressIndicator(color: c.primary))
                  : _treeEntries.isEmpty
                      ? Center(
                          child: Text(
                            'Directory is empty or unreadable.',
                            style: TextStyle(fontSize: 13, color: c.textMuted),
                          ),
                        )
                      : ListView.builder(
                          padding: const EdgeInsets.symmetric(vertical: 8),
                          itemCount: _treeEntries.length,
                          itemBuilder: (context, index) {
                            final entry = _treeEntries[index];
                            return _buildTreeItem(entry, c, level: 0);
                          },
                        ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildStatPill(String label, String value, IconData icon, dynamic c) {
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        Icon(icon, size: 14, color: c.secondary),
        const SizedBox(width: 6),
        Text(
          '$label: ',
          style: TextStyle(fontSize: 12, color: c.textMuted),
        ),
        Text(
          value,
          style: TextStyle(fontSize: 12, fontWeight: FontWeight.w700, color: c.textPrimary),
        ),
      ],
    );
  }

  Widget _buildTreeItem(ProjectTreeEntry entry, dynamic c, {required int level}) {
    final isExpanded = _expandedFolders.contains(entry.relativePath);
    final subEntries = _subfolderEntries[entry.relativePath] ?? [];

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        InkWell(
          borderRadius: BorderRadius.circular(6),
          hoverColor: c.surfaceHighlight.withValues(alpha: 0.6),
          onTap: entry.isDirectory
              ? () => _toggleFolder(entry)
              : () => FilePreviewModal.show(
                    context,
                    projectPath: widget.project.rootPath,
                    entry: entry,
                  ),
          child: Padding(
            padding: EdgeInsets.only(left: 16.0 + (level * 20.0), top: 6, bottom: 6, right: 16),
            child: Row(
              children: [
                if (entry.isDirectory)
                  Icon(
                    isExpanded ? Icons.keyboard_arrow_down_rounded : Icons.keyboard_arrow_right_rounded,
                    size: 16,
                    color: c.textMuted,
                  )
                else
                  const SizedBox(width: 16),
                const SizedBox(width: 4),
                Icon(
                  entry.isDirectory
                      ? (isExpanded ? Icons.folder_open_rounded : Icons.folder_rounded)
                      : FileTypeDetector.getIcon(entry.name),
                  size: 16,
                  color: entry.isDirectory ? c.primary : c.textSecondary,
                ),
                const SizedBox(width: 8),
                Expanded(
                  child: Text(
                    entry.name,
                    style: TextStyle(
                      fontSize: 13,
                      fontWeight: entry.isDirectory ? FontWeight.w600 : FontWeight.w400,
                      color: c.textPrimary,
                    ),
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                  ),
                ),
                if (!entry.isDirectory) ...[
                  if (entry.sizeBytes > 0)
                    Text(
                      _formatBytes(entry.sizeBytes),
                      style: TextStyle(fontSize: 11, color: c.textMuted),
                    ),
                  const SizedBox(width: 8),
                  Icon(
                    Icons.visibility_outlined,
                    size: 13,
                    color: c.textMuted.withValues(alpha: 0.6),
                  ),
                ],
              ],
            ),
          ),
        ),
        if (entry.isDirectory && isExpanded)
          ...subEntries.map((sub) => _buildTreeItem(sub, c, level: level + 1)),
      ],
    );
  }
}
