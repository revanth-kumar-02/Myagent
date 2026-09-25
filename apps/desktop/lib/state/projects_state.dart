import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../models/project.dart';
import '../models/project_file_data.dart';
import '../services/project/project_launcher.dart';
import '../services/project/project_service.dart';

class ProjectsState {
  final String? workspacePath;
  final List<Project> projects;
  final bool isLoading;
  final String? errorMessage;
  final String? activeProjectId;
  final Project? selectedProject;

  const ProjectsState({
    this.workspacePath,
    this.projects = const [],
    this.isLoading = false,
    this.errorMessage,
    this.activeProjectId,
    this.selectedProject,
  });

  Project? get activeProject {
    if (activeProjectId == null) return projects.isNotEmpty ? projects.first : null;
    return projects.firstWhere(
      (p) => p.id == activeProjectId,
      orElse: () => projects.isNotEmpty ? projects.first : const Project(id: '', name: '', rootPath: ''),
    );
  }

  ProjectsState copyWith({
    String? workspacePath,
    List<Project>? projects,
    bool? isLoading,
    String? errorMessage,
    String? activeProjectId,
    Project? selectedProject,
    bool clearSelectedProject = false,
    bool clearError = false,
  }) {
    return ProjectsState(
      workspacePath: workspacePath ?? this.workspacePath,
      projects: projects ?? this.projects,
      isLoading: isLoading ?? this.isLoading,
      errorMessage: clearError ? null : (errorMessage ?? this.errorMessage),
      activeProjectId: activeProjectId ?? this.activeProjectId,
      selectedProject: clearSelectedProject ? null : (selectedProject ?? this.selectedProject),
    );
  }
}

class ProjectsNotifier extends StateNotifier<ProjectsState> {
  final ProjectService _projectService;

  ProjectsNotifier(this._projectService) : super(const ProjectsState()) {
    initWorkspace();
  }

  Future<void> initWorkspace() async {
    state = state.copyWith(isLoading: true, clearError: true);
    try {
      final saved = await _projectService.getPersistedWorkspace();
      if (saved != null && saved.isNotEmpty) {
        state = state.copyWith(workspacePath: saved);
        await scanProjects(saved);
      } else {
        state = state.copyWith(isLoading: false);
      }
    } catch (e) {
      state = state.copyWith(isLoading: false, errorMessage: e.toString());
    }
  }

  Future<void> setWorkspace(String path) async {
    final clean = path.trim();
    if (clean.isEmpty) return;
    await _projectService.saveWorkspace(clean);
    state = state.copyWith(workspacePath: clean);
    await scanProjects(clean);
  }

  Future<void> chooseWorkspace() async {
    final picked = await _projectService.pickDirectory(initialDirectory: state.workspacePath);
    if (picked != null && picked.isNotEmpty) {
      await setWorkspace(picked);
    }
  }

  Future<void> scanProjects(String workspacePath) async {
    state = state.copyWith(isLoading: true, clearError: true);
    try {
      final list = await _projectService.scanProjects(workspacePath);
      state = state.copyWith(
        projects: list,
        isLoading: false,
        activeProjectId: state.activeProjectId ?? (list.isNotEmpty ? list.first.id : null),
      );
    } catch (e) {
      state = state.copyWith(
        isLoading: false,
        errorMessage: 'Failed to scan workspace "$workspacePath": $e',
      );
    }
  }

  Future<void> refreshProjects() async {
    if (state.workspacePath != null) {
      await scanProjects(state.workspacePath!);
    }
  }

  void setActiveProject(String? id) {
    state = state.copyWith(activeProjectId: id);
  }

  void selectProject(Project? p) {
    state = state.copyWith(
      selectedProject: p,
      clearSelectedProject: p == null,
    );
  }

  Future<bool> createProject({
    required String name,
    String? parentPath,
    String? template,
  }) async {
    final targetWorkspace = parentPath ?? state.workspacePath;
    if (targetWorkspace == null || targetWorkspace.isEmpty) {
      state = state.copyWith(errorMessage: 'Please select a workspace directory first.');
      return false;
    }

    state = state.copyWith(isLoading: true, clearError: true);
    try {
      final newProj = await _projectService.createProject(
        workspacePath: targetWorkspace,
        name: name,
        template: template,
      );

      final updated = [...state.projects, newProj]
        ..sort((a, b) => a.name.toLowerCase().compareTo(b.name.toLowerCase()));

      state = state.copyWith(
        projects: updated,
        activeProjectId: newProj.id,
        isLoading: false,
      );
      return true;
    } catch (e) {
      state = state.copyWith(
        isLoading: false,
        errorMessage: 'Failed to create project: $e',
      );
      return false;
    }
  }

  Future<void> openInVSCode(String path) async {
    await ProjectLauncher.openInVSCode(path);
  }

  Future<void> openInFileExplorer(String path) async {
    await ProjectLauncher.openInFileExplorer(path);
  }

  Future<void> openTerminal(String path) async {
    await ProjectLauncher.openTerminal(path);
  }

  Future<List<ProjectTreeEntry>> getProjectTree(String projectPath, {String subPath = ''}) async {
    return _projectService.getProjectTree(projectPath, subPath: subPath);
  }

  Future<ProjectFileData> readFile({required String projectPath, required String relativePath}) async {
    return _projectService.readFile(projectPath: projectPath, relativePath: relativePath);
  }
}

final projectServiceProvider = Provider<ProjectService>((ref) {
  return ProjectService();
});

final projectsProvider = StateNotifierProvider<ProjectsNotifier, ProjectsState>((ref) {
  final service = ref.watch(projectServiceProvider);
  return ProjectsNotifier(service);
});
