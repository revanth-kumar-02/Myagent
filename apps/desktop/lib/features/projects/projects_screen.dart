import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/theme/app_theme.dart';
import '../../models/project.dart';
import '../../services/project/project_service.dart';
import '../../state/projects_state.dart';
import 'project_detail_screen.dart';

class ProjectsScreen extends ConsumerWidget {
  const ProjectsScreen({super.key});

  void _showChooseDirectoryDialog(BuildContext context, WidgetRef ref, String? currentPath) {
    final c = AppTheme.colors(context);
    final pathCtrl = TextEditingController(text: currentPath ?? ProjectService.defaultWorkspaceSuggestion);

    showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        backgroundColor: c.surface,
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
        title: Text(
          'Choose Workspace Directory',
          style: TextStyle(fontSize: 16, fontWeight: FontWeight.w700, color: c.textPrimary),
        ),
        content: SizedBox(
          width: 500,
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                'Enter the directory containing your project folders on this machine:',
                style: TextStyle(fontSize: 13, color: c.textSecondary),
              ),
              const SizedBox(height: 12),
              TextField(
                controller: pathCtrl,
                style: TextStyle(color: c.textPrimary, fontSize: 13),
                decoration: InputDecoration(
                  labelText: 'Workspace Path',
                  labelStyle: TextStyle(color: c.textSecondary),
                  prefixIcon: Icon(Icons.folder_outlined, size: 18, color: c.secondary),
                ),
              ),
              const SizedBox(height: 16),
              Text(
                'Suggested Workspaces:',
                style: TextStyle(fontSize: 11, fontWeight: FontWeight.w600, color: c.textMuted),
              ),
              const SizedBox(height: 8),
              Wrap(
                spacing: 8,
                runSpacing: 6,
                children: [
                  _buildQuickPathChip('/home/rev/My_Personal_Space/Projects/Unfinished', pathCtrl, c),
                  _buildQuickPathChip('/home/rev/My_Personal_Space/Projects/Finished', pathCtrl, c),
                  _buildQuickPathChip('/home/rev/My_Personal_Space/Projects', pathCtrl, c),
                ],
              ),
            ],
          ),
        ),
        actions: [
          TextButton(
            child: Text('Cancel', style: TextStyle(color: c.textSecondary)),
            onPressed: () => Navigator.of(ctx).pop(),
          ),
          OutlinedButton.icon(
            icon: const Icon(Icons.file_open_outlined, size: 14),
            label: const Text('Browse Native...'),
            style: OutlinedButton.styleFrom(foregroundColor: c.textPrimary),
            onPressed: () async {
              Navigator.of(ctx).pop();
              await ref.read(projectsProvider.notifier).chooseWorkspace();
            },
          ),
          ElevatedButton(
            style: ElevatedButton.styleFrom(backgroundColor: c.primary, foregroundColor: Colors.white),
            child: const Text('Select Directory'),
            onPressed: () {
              final path = pathCtrl.text.trim();
              if (path.isNotEmpty) {
                ref.read(projectsProvider.notifier).setWorkspace(path);
                Navigator.of(ctx).pop();
              }
            },
          ),
        ],
      ),
    );
  }

  Widget _buildQuickPathChip(String path, TextEditingController ctrl, dynamic c) {
    return ActionChip(
      backgroundColor: c.surfaceHighlight,
      side: BorderSide(color: c.border),
      label: Text(
        path,
        style: TextStyle(fontSize: 11, color: c.textPrimary),
      ),
      onPressed: () {
        ctrl.text = path;
      },
    );
  }

  void _showNewProjectDialog(BuildContext context, WidgetRef ref, String? workspacePath) {
    final c = AppTheme.colors(context);
    final nameCtrl = TextEditingController();
    final parentCtrl = TextEditingController(text: workspacePath ?? '');
    String selectedTemplate = 'Blank';

    showDialog(
      context: context,
      builder: (ctx) => StatefulBuilder(
        builder: (context, setDialogState) => AlertDialog(
          backgroundColor: c.surface,
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
          title: Text(
            'Create New Project Directory',
            style: TextStyle(fontSize: 16, fontWeight: FontWeight.w700, color: c.textPrimary),
          ),
          content: SizedBox(
            width: 460,
            child: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  'Creates a physical project folder on your local filesystem.',
                  style: TextStyle(fontSize: 12, color: c.textSecondary),
                ),
                const SizedBox(height: 14),
                TextField(
                  controller: nameCtrl,
                  autofocus: true,
                  style: TextStyle(color: c.textPrimary),
                  decoration: InputDecoration(
                    labelText: 'Project Name',
                    hintText: 'e.g. MyNewAgent',
                    labelStyle: TextStyle(color: c.textSecondary),
                  ),
                ),
                const SizedBox(height: 12),
                TextField(
                  controller: parentCtrl,
                  style: TextStyle(color: c.textPrimary, fontSize: 13),
                  decoration: InputDecoration(
                    labelText: 'Parent Directory',
                    labelStyle: TextStyle(color: c.textSecondary),
                  ),
                ),
                const SizedBox(height: 14),
                Text(
                  'Project Type (Optional):',
                  style: TextStyle(fontSize: 12, color: c.textSecondary),
                ),
                const SizedBox(height: 6),
                DropdownButtonFormField<String>(
                  value: selectedTemplate,
                  dropdownColor: c.surface,
                  style: TextStyle(color: c.textPrimary, fontSize: 13),
                  decoration: InputDecoration(
                    contentPadding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
                  ),
                  items: const [
                    DropdownMenuItem(value: 'Blank', child: Text('Blank Directory')),
                    DropdownMenuItem(value: 'Flutter', child: Text('Flutter Application')),
                    DropdownMenuItem(value: 'Python', child: Text('Python Project')),
                    DropdownMenuItem(value: 'TypeScript', child: Text('TypeScript / Node.js')),
                    DropdownMenuItem(value: 'Rust', child: Text('Rust / Cargo')),
                  ],
                  onChanged: (val) {
                    if (val != null) setDialogState(() => selectedTemplate = val);
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
              style: ElevatedButton.styleFrom(backgroundColor: c.primary, foregroundColor: Colors.white),
              child: const Text('Create Folder'),
              onPressed: () async {
                final name = nameCtrl.text.trim();
                final parent = parentCtrl.text.trim();
                if (name.isNotEmpty && parent.isNotEmpty) {
                  final ok = await ref.read(projectsProvider.notifier).createProject(
                    name: name,
                    parentPath: parent,
                    template: selectedTemplate,
                  );
                  if (ok && ctx.mounted) {
                    Navigator.of(ctx).pop();
                    ScaffoldMessenger.of(context).showSnackBar(
                      SnackBar(content: Text('Created project "$name" on filesystem')),
                    );
                  }
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
    final state = ref.watch(projectsProvider);
    final c = AppTheme.colors(context);

    // If viewing project detail, render detail screen
    if (state.selectedProject != null) {
      return ProjectDetailScreen(project: state.selectedProject!);
    }

    return Container(
      color: c.bg,
      padding: const EdgeInsets.symmetric(horizontal: 28, vertical: 24),
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
                    Text(
                      'Kora Projects',
                      style: TextStyle(
                        fontSize: 22,
                        fontWeight: FontWeight.w800,
                        letterSpacing: -0.4,
                        color: c.textPrimary,
                      ),
                    ),
                    const SizedBox(height: 4),
                    if (state.workspacePath != null)
                      Row(
                        children: [
                          Icon(Icons.folder_shared_outlined, size: 14, color: c.secondary),
                          const SizedBox(width: 6),
                          Expanded(
                            child: Text(
                              'Workspace: ${state.workspacePath}',
                              style: TextStyle(fontSize: 12.5, color: c.textSecondary, fontWeight: FontWeight.w500),
                              overflow: TextOverflow.ellipsis,
                            ),
                          ),
                          const SizedBox(width: 8),
                          InkWell(
                            onTap: () => _showChooseDirectoryDialog(context, ref, state.workspacePath),
                            borderRadius: BorderRadius.circular(4),
                            child: Padding(
                              padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                              child: Text(
                                'Change',
                                style: TextStyle(
                                  fontSize: 12,
                                  fontWeight: FontWeight.w700,
                                  color: c.primary,
                                  decoration: TextDecoration.underline,
                                ),
                              ),
                            ),
                          ),
                        ],
                      )
                    else
                      Text(
                        'Local filesystem workspace manager. Inspect real directories, codebases, and structure.',
                        style: TextStyle(fontSize: 13, color: c.textSecondary),
                      ),
                  ],
                ),
              ),
              const SizedBox(width: 12),
              OutlinedButton.icon(
                icon: const Icon(Icons.folder_open_rounded, size: 15),
                label: const Text('Choose Directory'),
                style: OutlinedButton.styleFrom(
                  foregroundColor: c.textPrimary,
                  side: BorderSide(color: c.border),
                  padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
                  shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
                ),
                onPressed: () => _showChooseDirectoryDialog(context, ref, state.workspacePath),
              ),
              const SizedBox(width: 8),
              IconButton(
                icon: const Icon(Icons.refresh_rounded, size: 18),
                tooltip: 'Refresh projects from filesystem',
                color: c.textSecondary,
                onPressed: () => ref.read(projectsProvider.notifier).refreshProjects(),
              ),
              const SizedBox(width: 8),
              ElevatedButton.icon(
                icon: const Icon(Icons.add_rounded, size: 16),
                label: const Text('New Project'),
                style: ElevatedButton.styleFrom(
                  backgroundColor: c.primary,
                  foregroundColor: Colors.white,
                  shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
                  padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
                ),
                onPressed: () => _showNewProjectDialog(context, ref, state.workspacePath),
              ),
            ],
          ),
          const SizedBox(height: 20),

          // Error Message banner if any
          if (state.errorMessage != null) ...[
            Container(
              margin: const EdgeInsets.only(bottom: 16),
              padding: const EdgeInsets.all(12),
              decoration: BoxDecoration(
                color: Colors.red.withValues(alpha: 0.08),
                borderRadius: BorderRadius.circular(8),
                border: Border.all(color: Colors.red.withValues(alpha: 0.2)),
              ),
              child: Row(
                children: [
                  const Icon(Icons.error_outline_rounded, size: 16, color: Colors.red),
                  const SizedBox(width: 8),
                  Expanded(
                    child: Text(
                      state.errorMessage!,
                      style: const TextStyle(fontSize: 12.5, color: Colors.red),
                    ),
                  ),
                  TextButton(
                    child: const Text('Choose Another Directory', style: TextStyle(fontSize: 12)),
                    onPressed: () => _showChooseDirectoryDialog(context, ref, state.workspacePath),
                  ),
                ],
              ),
            ),
          ],

          // Main Body
          Expanded(
            child: state.isLoading
                ? Center(
                    child: Column(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        CircularProgressIndicator(color: c.primary),
                        const SizedBox(height: 14),
                        Text(
                          'Scanning real filesystem directories...',
                          style: TextStyle(fontSize: 13, color: c.textSecondary, fontWeight: FontWeight.w500),
                        ),
                      ],
                    ),
                  )
                : state.workspacePath == null
                    ? _buildNoWorkspaceView(context, ref, c)
                    : state.projects.isEmpty
                        ? _buildNoProjectsView(context, ref, c, state.workspacePath!)
                        : ListView.builder(
                            itemCount: state.projects.length,
                            itemBuilder: (context, index) {
                              final project = state.projects[index];
                              return _buildProjectCard(context, ref, project, c);
                            },
                          ),
          ),
        ],
      ),
    );
  }

  Widget _buildNoWorkspaceView(BuildContext context, WidgetRef ref, dynamic c) {
    return Center(
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          Container(
            width: 68,
            height: 68,
            decoration: BoxDecoration(
              color: c.primaryLight,
              shape: BoxShape.circle,
            ),
            child: Icon(Icons.folder_open_rounded, size: 32, color: c.primary),
          ),
          const SizedBox(height: 16),
          Text(
            'No workspace selected',
            style: TextStyle(fontSize: 18, fontWeight: FontWeight.w700, color: c.textPrimary),
          ),
          const SizedBox(height: 6),
          Text(
            'Choose a directory containing your project repositories on this computer.',
            style: TextStyle(fontSize: 13, color: c.textSecondary),
            textAlign: TextAlign.center,
          ),
          const SizedBox(height: 20),
          ElevatedButton.icon(
            icon: const Icon(Icons.folder_shared_rounded, size: 16),
            label: const Text('Choose Directory'),
            style: ElevatedButton.styleFrom(
              backgroundColor: c.primary,
              foregroundColor: Colors.white,
              shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
              padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 14),
            ),
            onPressed: () => _showChooseDirectoryDialog(context, ref, null),
          ),
          const SizedBox(height: 24),
          Text(
            'Or select the local projects directory:',
            style: TextStyle(fontSize: 11, fontWeight: FontWeight.w600, color: c.textMuted),
          ),
          const SizedBox(height: 8),
          ActionChip(
            backgroundColor: c.surfaceHighlight,
            side: BorderSide(color: c.border),
            label: const Text('/home/rev/My_Personal_Space/Projects/Unfinished'),
            onPressed: () => ref.read(projectsProvider.notifier).setWorkspace('/home/rev/My_Personal_Space/Projects/Unfinished'),
          ),
        ],
      ),
    );
  }

  Widget _buildNoProjectsView(BuildContext context, WidgetRef ref, dynamic c, String workspacePath) {
    return Center(
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          Container(
            width: 60,
            height: 60,
            decoration: BoxDecoration(
              color: c.surfaceHighlight,
              shape: BoxShape.circle,
            ),
            child: Icon(Icons.folder_off_outlined, size: 28, color: c.textSecondary),
          ),
          const SizedBox(height: 14),
          Text(
            'No projects found',
            style: TextStyle(fontSize: 17, fontWeight: FontWeight.w700, color: c.textPrimary),
          ),
          const SizedBox(height: 6),
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 40),
            child: Text(
              'No subdirectories were found in $workspacePath.\nCreate your first project or choose another directory.',
              style: TextStyle(fontSize: 13, color: c.textSecondary),
              textAlign: TextAlign.center,
            ),
          ),
          const SizedBox(height: 18),
          Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              ElevatedButton.icon(
                icon: const Icon(Icons.add_rounded, size: 15),
                label: const Text('New Project'),
                style: ElevatedButton.styleFrom(
                  backgroundColor: c.primary,
                  foregroundColor: Colors.white,
                  padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
                  shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
                ),
                onPressed: () => _showNewProjectDialog(context, ref, workspacePath),
              ),
              const SizedBox(width: 10),
              OutlinedButton(
                style: OutlinedButton.styleFrom(
                  foregroundColor: c.textPrimary,
                  side: BorderSide(color: c.border),
                  padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
                  shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
                ),
                child: const Text('Choose Another Directory'),
                onPressed: () => _showChooseDirectoryDialog(context, ref, workspacePath),
              ),
            ],
          ),
        ],
      ),
    );
  }

  Widget _buildProjectCard(BuildContext context, WidgetRef ref, Project project, dynamic c) {
    return Container(
      margin: const EdgeInsets.only(bottom: 14),
      decoration: BoxDecoration(
        color: c.surface,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: c.border, width: 1),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withValues(alpha: 0.02),
            blurRadius: 6,
            offset: const Offset(0, 2),
          ),
        ],
      ),
      child: InkWell(
        borderRadius: BorderRadius.circular(12),
        onTap: () => ref.read(projectsProvider.notifier).selectProject(project),
        child: Padding(
          padding: const EdgeInsets.all(18),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              // Top Title + Badges
              Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Container(
                    width: 38,
                    height: 38,
                    decoration: BoxDecoration(
                      color: c.primaryLight,
                      borderRadius: BorderRadius.circular(8),
                    ),
                    child: Icon(Icons.folder_rounded, size: 20, color: c.primary),
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Row(
                          children: [
                            Text(
                              project.name,
                              style: TextStyle(
                                fontSize: 16,
                                fontWeight: FontWeight.w700,
                                color: c.textPrimary,
                              ),
                            ),
                            const SizedBox(width: 8),
                            Container(
                              padding: const EdgeInsets.symmetric(horizontal: 7, vertical: 2),
                              decoration: BoxDecoration(
                                color: c.secondaryLight,
                                borderRadius: BorderRadius.circular(4),
                              ),
                              child: Text(
                                project.projectType,
                                style: TextStyle(
                                  fontSize: 10.5,
                                  fontWeight: FontWeight.w600,
                                  color: c.secondaryDark,
                                ),
                              ),
                            ),
                          ],
                        ),
                        const SizedBox(height: 3),
                        Text(
                          project.rootPath,
                          style: TextStyle(fontSize: 11.5, color: c.textMuted),
                          overflow: TextOverflow.ellipsis,
                        ),
                      ],
                    ),
                  ),
                  if (project.lastModified.isNotEmpty)
                    Text(
                      project.lastModified,
                      style: TextStyle(fontSize: 11, color: c.textMuted),
                    ),
                ],
              ),
              const SizedBox(height: 12),

              // Languages & Top-Level Folders
              if (project.detectedLanguages.isNotEmpty || project.topLevelFolders.isNotEmpty) ...[
                Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    if (project.detectedLanguages.isNotEmpty) ...[
                      Text(
                        'Languages: ',
                        style: TextStyle(fontSize: 11.5, fontWeight: FontWeight.w600, color: c.textSecondary),
                      ),
                      Text(
                        project.detectedLanguages.take(4).join(' · '),
                        style: TextStyle(fontSize: 11.5, color: c.primary, fontWeight: FontWeight.w600),
                      ),
                      const SizedBox(width: 16),
                    ],
                    if (project.topLevelFolders.isNotEmpty) ...[
                      Text(
                        'Structure: ',
                        style: TextStyle(fontSize: 11.5, fontWeight: FontWeight.w600, color: c.textSecondary),
                      ),
                      Expanded(
                        child: Text(
                          project.topLevelFolders.take(5).map((f) => '$f/').join('  '),
                          style: TextStyle(fontSize: 11.5, color: c.textMuted),
                          overflow: TextOverflow.ellipsis,
                        ),
                      ),
                    ],
                  ],
                ),
                const SizedBox(height: 10),
              ],

              // Stats Row + Actions
              Row(
                children: [
                  Icon(Icons.insert_drive_file_outlined, size: 13, color: c.textMuted),
                  const SizedBox(width: 4),
                  Text(
                    '${project.fileCount} files · ${project.folderCount} folders',
                    style: TextStyle(fontSize: 11.5, color: c.textSecondary),
                  ),
                  const SizedBox(width: 14),
                  Icon(
                    project.gitStatus.startsWith('Git') ? Icons.check_circle_outline_rounded : Icons.radio_button_unchecked_rounded,
                    size: 13,
                    color: project.gitStatus.startsWith('Git') ? c.primary : c.textMuted,
                  ),
                  const SizedBox(width: 4),
                  Text(
                    project.gitStatus,
                    style: TextStyle(fontSize: 11.5, color: c.textSecondary),
                  ),
                  const Spacer(),

                  // Actions
                  OutlinedButton.icon(
                    icon: const Icon(Icons.visibility_outlined, size: 13),
                    label: const Text('Open'),
                    style: OutlinedButton.styleFrom(
                      foregroundColor: c.textPrimary,
                      side: BorderSide(color: c.border),
                      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
                      visualDensity: VisualDensity.compact,
                    ),
                    onPressed: () => ref.read(projectsProvider.notifier).selectProject(project),
                  ),
                  const SizedBox(width: 6),
                  OutlinedButton.icon(
                    icon: const Icon(Icons.code_rounded, size: 13),
                    label: const Text('VS Code'),
                    style: OutlinedButton.styleFrom(
                      foregroundColor: c.textPrimary,
                      side: BorderSide(color: c.border),
                      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
                      visualDensity: VisualDensity.compact,
                    ),
                    onPressed: () => ref.read(projectsProvider.notifier).openInVSCode(project.rootPath),
                  ),
                  const SizedBox(width: 6),
                  ElevatedButton.icon(
                    icon: const Icon(Icons.folder_open_rounded, size: 13),
                    label: const Text('File Explorer'),
                    style: ElevatedButton.styleFrom(
                      backgroundColor: c.surfaceHighlight,
                      foregroundColor: c.textPrimary,
                      elevation: 0,
                      side: BorderSide(color: c.border),
                      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
                      visualDensity: VisualDensity.compact,
                    ),
                    onPressed: () => ref.read(projectsProvider.notifier).openInFileExplorer(project.rootPath),
                  ),
                ],
              ),
            ],
          ),
        ),
      ),
    );
  }
}
