import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../models/activity_log.dart';
import '../services/kora_api_service.dart';
import 'connection_state.dart';

class ActivityState {
  final List<ActivityLog> logs;
  final bool isLoading;
  final String? errorMessage;

  const ActivityState({
    this.logs = const [],
    this.isLoading = false,
    this.errorMessage,
  });

  ActivityState copyWith({
    List<ActivityLog>? logs,
    bool? isLoading,
    String? errorMessage,
  }) {
    return ActivityState(
      logs: logs ?? this.logs,
      isLoading: isLoading ?? this.isLoading,
      errorMessage: errorMessage ?? this.errorMessage,
    );
  }
}

class ActivityNotifier extends StateNotifier<ActivityState> {
  final KoraApiService _apiService;

  ActivityNotifier(this._apiService) : super(const ActivityState()) {
    loadActivity();
  }

  Future<void> loadActivity() async {
    state = state.copyWith(isLoading: true, errorMessage: null);
    try {
      final list = await _apiService.getActivityLogs();
      state = state.copyWith(logs: list, isLoading: false);
    } catch (e) {
      state = state.copyWith(isLoading: false, errorMessage: e.toString());
    }
  }
}

final activityProvider = StateNotifierProvider<ActivityNotifier, ActivityState>((ref) {
  final api = ref.watch(apiServiceProvider);
  return ActivityNotifier(api);
});
