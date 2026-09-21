import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../models/task_item.dart';
import '../services/kora_api_service.dart';
import 'connection_state.dart';

class TasksState {
  final List<TaskItem> tasks;
  final bool isLoading;
  final String? errorMessage;

  const TasksState({
    this.tasks = const [],
    this.isLoading = false,
    this.errorMessage,
  });

  TasksState copyWith({
    List<TaskItem>? tasks,
    bool? isLoading,
    String? errorMessage,
  }) {
    return TasksState(
      tasks: tasks ?? this.tasks,
      isLoading: isLoading ?? this.isLoading,
      errorMessage: errorMessage ?? this.errorMessage,
    );
  }
}

class TasksNotifier extends StateNotifier<TasksState> {
  final KoraApiService _apiService;

  TasksNotifier(this._apiService) : super(const TasksState()) {
    loadTasks();
  }

  Future<void> loadTasks() async {
    state = state.copyWith(isLoading: true, errorMessage: null);
    try {
      final list = await _apiService.getTasks();
      state = state.copyWith(tasks: list, isLoading: false);
    } catch (e) {
      state = state.copyWith(isLoading: false, errorMessage: e.toString());
    }
  }
}

final tasksProvider = StateNotifierProvider<TasksNotifier, TasksState>((ref) {
  final api = ref.watch(apiServiceProvider);
  return TasksNotifier(api);
});
