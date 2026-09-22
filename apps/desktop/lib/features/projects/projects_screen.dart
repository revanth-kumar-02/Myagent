import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/theme/app_theme.dart';
import '../../models/project.dart';
import '../../state/projects_state.dart';

class ProjectsScreen extends ConsumerWidget {
  const ProjectsScreen({super.key});

  void _showNewProjectDialog(BuildContext context, WidgetRef ref) {
    final c = AppTheme.colors(context);
    final nameCtrl = TextEditingController();
    final descCtrl = TextEditingController();
    final pathCtrl = TextEditingController();

    showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        backgroundColor: c.surface,
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
        title: Text('Create New Project', style: TextStyle(fontSize: 16, fontWeight: FontWeight.w700, color: c.textPrimary)),
        content: SizedBox(
          width: 440,
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              TextField(
                controller: nameCtrl,
                style: TextStyle(color: c.textPrimary),
                decoration: InputDecoration(
                  labelText: 'Project Name',
                  labelStyle: TextStyle(color: c.textSecondary),
                ),
              ),
              const SizedBox(height: 12),
              TextField(
                controller: descCtrl,
                style: TextStyle(color: c.textPrimary),
                decoration: InputDecoration(
                  labelText: 'Description',
                  labelStyle: TextStyle(color: c.textSecondary),
                ),
              ),
              const SizedBox(height: 12),
              TextField(
                controller: pathCtrl,
                style: TextStyle(color: c.textPrimary),
                decoration: InputDecoration(
                  labelText: 'Root Workspace Path (Optional)',
                  labelStyle: TextStyle(color: c.textSecondary),
                ),
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
            style: ElevatedButton.styleFrom(backgroundColor: c.primary, foregroundColor: Colors.white),
            child: const Text('Create'),
            onPressed: () {
              if (nameCtrl.text.trim().isNotEmpty) {
                ref.read(projectsProvider.notifier).createProject(
                  name: nameCtrl.text.trim(),
                  description: descCtrl.text.trim(),
                  rootPath: pathCtrl.text.trim(),
                );
                Navigator.of(ctx).pop();
              }
            },
          ),
        ],
      ),
    );
  }

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final state = ref.watch(projectsProvider);
    final c = AppTheme.colors(context);

    return Container(
      color: c.bg,
      padding: const EdgeInsets.symmetric(horizontal: 28, vertical: 24),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Header
          Row(
            children: [
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      'Knowledge Base & Projects',
                      style: TextStyle(
                        fontSize: 20,
                        fontWeight: FontWeight.w800,
                        letterSpacing: -0.4,
                        color: c.textPrimary,
                      ),
                    ),
                    const SizedBox(height: 4),
                    Text(
                      'Manage indexed codebases and document repositories for RAG vector retrieval.',
                      style: TextStyle(fontSize: 13, color: c.textSecondary),
                    ),
                  ],
                ),
              ),
              ElevatedButton.icon(
                icon: const Icon(Icons.add_rounded, size: 16),
                label: const Text('New Project'),
                style: ElevatedButton.styleFrom(
                  backgroundColor: c.primary,
                  foregroundColor: Colors.white,
                  shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
                  padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
                ),
                onPressed: () => _showNewProjectDialog(context, ref),
              ),
            ],
          ),
          const SizedBox(height: 20),

          // Project List
          Expanded(
            child: state.isLoading
                ? Center(child: CircularProgressIndicator(color: c.primary))
                : state.projects.isEmpty
                    ? Center(
                        child: Text(
                          'No projects configured. Create one to begin indexing documents.',
                          style: TextStyle(fontSize: 13, color: c.textMuted),
                        ),
                      )
                    : ListView.builder(
                        itemCount: state.projects.length,
                        itemBuilder: (context, index) {
                          final project = state.projects[index];
                          final isSelected = project.id == state.activeProjectId;

                          return Container(
                            margin: const EdgeInsets.only(bottom: 12),
                            padding: const EdgeInsets.all(16),
                            decoration: BoxDecoration(
                              color: c.surface,
                              borderRadius: BorderRadius.circular(12),
                              border: Border.all(
                                color: isSelected
                                    ? c.primary
                                    : c.border,
                                width: isSelected ? 1.5 : 1.0,
                              ),
                              boxShadow: [
                                BoxShadow(
                                  color: Colors.black.withValues(alpha: 0.02),
                                  blurRadius: 6,
                                  offset: const Offset(0, 2),
                                ),
                              ],
                            ),
                            child: Row(
                              children: [
                                Container(
                                  padding: const EdgeInsets.all(12),
                                  decoration: BoxDecoration(
                                    color: c.primaryLight,
                                    borderRadius: BorderRadius.circular(10),
                                  ),
                                  child: Icon(Icons.folder_rounded, color: c.primary, size: 22),
                                ),
                                const SizedBox(width: 16),
                                Expanded(
                                  child: Column(
                                    crossAxisAlignment: CrossAxisAlignment.start,
                                    children: [
                                      Row(
                                        children: [
                                          Text(
                                            project.name,
                                            style: TextStyle(
                                              fontSize: 14.5,
                                              fontWeight: FontWeight.w700,
                                              color: c.textPrimary,
                                            ),
                                          ),
                                          if (isSelected) ...[
                                            const SizedBox(width: 8),
                                            Container(
                                              padding: const EdgeInsets.symmetric(horizontal: 7, vertical: 2.5),
                                              decoration: BoxDecoration(
                                                color: c.primaryLight,
                                                borderRadius: BorderRadius.circular(4),
                                                border: Border.all(color: c.primary.withValues(alpha: 0.3)),
                                              ),
                                              child: Text(
                                                'ACTIVE RAG SCOPE',
                                                style: TextStyle(
                                                  fontSize: 9.5,
                                                  fontWeight: FontWeight.w700,
                                                  color: c.primaryDark,
                                                ),
                                              ),
                                            ),
                                          ],
                                        ],
                                      ),
                                      const SizedBox(height: 4),
                                      Text(
                                        project.description.isNotEmpty ? project.description : 'No description provided',
                                        style: TextStyle(fontSize: 12.5, color: c.textSecondary),
                                      ),
                                      const SizedBox(height: 6),
                                      Row(
                                        children: [
                                          Container(
                                            padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                                            decoration: BoxDecoration(
                                              color: c.surfaceHighlight,
                                              borderRadius: BorderRadius.circular(4),
                                            ),
                                            child: Text(
                                              'Path: ${project.rootPath}',
                                              style: TextStyle(fontSize: 11, color: c.textSecondary, fontFamily: 'monospace'),
                                            ),
                                          ),
                                          const SizedBox(width: 10),
                                          Text(
                                            '•  ${project.fileCount} Files  •  ${project.chunkCount} Chunks',
                                            style: TextStyle(fontSize: 11, color: c.textMuted, fontWeight: FontWeight.w500),
                                          ),
                                        ],
                                      ),
                                    ],
                                  ),
                                ),
                                IconButton(
                                  icon: Icon(Icons.delete_outline_rounded, size: 19, color: c.textMuted),
                                  tooltip: 'Delete Project',
                                  onPressed: () => ref.read(projectsProvider.notifier).deleteProject(project.id),
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
