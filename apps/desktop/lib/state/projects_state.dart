import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../models/project.dart';
import '../services/kora_api_service.dart';
import 'connection_state.dart';

class ProjectsState {
  final List<Project> projects;
  final bool isLoading;
  final String? errorMessage;
  final String? activeProjectId;

  const ProjectsState({
    this.projects = const [],
    this.isLoading = false,
    this.errorMessage,
    this.activeProjectId,
  });

  ProjectsState copyWith({
    List<Project>? projects,
    bool? isLoading,
    String? errorMessage,
    String? activeProjectId,
  }) {
    return ProjectsState(
      projects: projects ?? this.projects,
      isLoading: isLoading ?? this.isLoading,
      errorMessage: errorMessage,
      activeProjectId: activeProjectId ?? this.activeProjectId,
    );
  }
}

class ProjectsNotifier extends StateNotifier<ProjectsState> {
  final KoraApiService _apiService;

  ProjectsNotifier(this._apiService) : super(const ProjectsState()) {
    loadProjects();
  }

  Future<void> loadProjects() async {
    state = state.copyWith(isLoading: true, errorMessage: null);
    try {
      final list = await _apiService.getProjects();
      state = state.copyWith(
        projects: list,
        isLoading: false,
        activeProjectId: state.activeProjectId ?? (list.isNotEmpty ? list.first.id : null),
      );
    } catch (e) {
      state = state.copyWith(isLoading: false, errorMessage: e.toString());
    }
  }

  void setActiveProject(String? id) {
    state = state.copyWith(activeProjectId: id);
  }

  Future<void> createProject({
    required String name,
    String description = '',
    String rootPath = '',
  }) async {
    try {
      final newProj = await _apiService.createProject(
        name: name,
        description: description,
        rootPath: rootPath,
      );
      state = state.copyWith(
        projects: [...state.projects, newProj],
        activeProjectId: newProj.id,
      );
    } catch (e) {
      state = state.copyWith(errorMessage: e.toString());
    }
  }

  Future<void> deleteProject(String id) async {
    try {
      await _apiService.deleteProject(id);
      final updated = state.projects.where((p) => p.id != id).toList();
      state = state.copyWith(
        projects: updated,
        activeProjectId: state.activeProjectId == id
            ? (updated.isNotEmpty ? updated.first.id : null)
            : state.activeProjectId,
      );
    } catch (e) {
      state = state.copyWith(errorMessage: e.toString());
    }
  }
}

final projectsProvider = StateNotifierProvider<ProjectsNotifier, ProjectsState>((ref) {
  final api = ref.watch(apiServiceProvider);
  return ProjectsNotifier(api);
});
