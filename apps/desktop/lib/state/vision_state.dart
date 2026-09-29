import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../models/vision_models.dart';
import '../services/vision_api_service.dart';

// ── Provider ──────────────────────────────────────────────────────────────────

final visionServiceProvider = Provider<VisionApiService>((ref) {
  return VisionApiService();
});

final visionProvider = StateNotifierProvider<VisionNotifier, VisionState>((ref) {
  final service = ref.read(visionServiceProvider);
  return VisionNotifier(service);
});

// ── State ─────────────────────────────────────────────────────────────────────

enum VisionPhase {
  idle,
  loadingCapabilities,
  analyzing,
  capturing,
  asking,
  buildingContext,
  error,
}

class VisionState {
  final VisionPhase phase;
  final VisionCapabilities? capabilities;
  final VisionAnalysisResult? currentAnalysis;
  final List<RecentVisionItem> recentItems;
  final String? lastAnswer;
  final String? lastAnswerQuestion;
  final VisionContextResult? lastContext;
  final String? errorMessage;
  final bool contextSentToChat;

  const VisionState({
    this.phase = VisionPhase.idle,
    this.capabilities,
    this.currentAnalysis,
    this.recentItems = const [],
    this.lastAnswer,
    this.lastAnswerQuestion,
    this.lastContext,
    this.errorMessage,
    this.contextSentToChat = false,
  });

  bool get isWorking =>
      phase == VisionPhase.analyzing ||
      phase == VisionPhase.capturing ||
      phase == VisionPhase.asking ||
      phase == VisionPhase.buildingContext ||
      phase == VisionPhase.loadingCapabilities;

  bool get hasResult => currentAnalysis != null;
  bool get canAnalyze => capabilities?.canAnalyze ?? false;
  bool get canCapture => capabilities?.canCapture ?? false;
  bool get canAsk => hasResult && (capabilities?.canAsk ?? false);

  VisionState copyWith({
    VisionPhase? phase,
    VisionCapabilities? capabilities,
    Object? currentAnalysis = _sentinel,
    List<RecentVisionItem>? recentItems,
    Object? lastAnswer = _sentinel,
    Object? lastAnswerQuestion = _sentinel,
    Object? lastContext = _sentinel,
    Object? errorMessage = _sentinel,
    bool? contextSentToChat,
  }) {
    return VisionState(
      phase: phase ?? this.phase,
      capabilities: capabilities ?? this.capabilities,
      currentAnalysis: identical(currentAnalysis, _sentinel)
          ? this.currentAnalysis
          : currentAnalysis as VisionAnalysisResult?,
      recentItems: recentItems ?? this.recentItems,
      lastAnswer: identical(lastAnswer, _sentinel) ? this.lastAnswer : lastAnswer as String?,
      lastAnswerQuestion: identical(lastAnswerQuestion, _sentinel)
          ? this.lastAnswerQuestion
          : lastAnswerQuestion as String?,
      lastContext: identical(lastContext, _sentinel)
          ? this.lastContext
          : lastContext as VisionContextResult?,
      errorMessage: identical(errorMessage, _sentinel)
          ? this.errorMessage
          : errorMessage as String?,
      contextSentToChat: contextSentToChat ?? this.contextSentToChat,
    );
  }

  static const _sentinel = Object();
}

// ── Notifier ──────────────────────────────────────────────────────────────────

class VisionNotifier extends StateNotifier<VisionState> {
  final VisionApiService _service;

  VisionNotifier(this._service) : super(const VisionState()) {
    // Load capabilities on construction
    loadCapabilities();
  }

  /// Load what the backend can actually do.
  Future<void> loadCapabilities() async {
    state = state.copyWith(phase: VisionPhase.loadingCapabilities, errorMessage: null);
    try {
      final caps = await _service.getCapabilities();
      state = state.copyWith(phase: VisionPhase.idle, capabilities: caps);
    } catch (e) {
      state = state.copyWith(
        phase: VisionPhase.error,
        errorMessage: 'Could not reach Vision backend: ${e.toString()}',
      );
    }
  }

  /// Analyze a local image file (file picker result).
  Future<void> analyzeFile(String filePath, {String? customPrompt}) async {
    state = state.copyWith(
      phase: VisionPhase.analyzing,
      errorMessage: null,
      currentAnalysis: null,
      lastAnswer: null,
      lastContext: null,
      contextSentToChat: false,
    );
    try {
      final result = await _service.analyzeImage(filePath, customPrompt: customPrompt);
      state = state.copyWith(phase: VisionPhase.idle, currentAnalysis: result);
      await _refreshRecent();
    } catch (e) {
      state = state.copyWith(
        phase: VisionPhase.error,
        errorMessage: 'Image analysis failed: ${e.toString()}',
      );
    }
  }

  /// Trigger server-side screen capture and analyze.
  Future<void> captureScreen({String target = 'full_screen', String? customPrompt}) async {
    state = state.copyWith(
      phase: VisionPhase.capturing,
      errorMessage: null,
      currentAnalysis: null,
      lastAnswer: null,
      lastContext: null,
      contextSentToChat: false,
    );
    try {
      final raw = await _service.captureScreen(
        target: target,
        analyze: true,
        customPrompt: customPrompt,
      );

      if (raw.containsKey('analysis_error')) {
        state = state.copyWith(
          phase: VisionPhase.error,
          errorMessage: 'Capture succeeded but analysis failed: ${raw['analysis_error']}',
        );
        return;
      }

      VisionAnalysisResult? analysis;
      if (raw.containsKey('analysis')) {
        final analysisJson = raw['analysis'] as Map<String, dynamic>;
        analysis = VisionAnalysisResult.fromJson(
          analysisJson,
          imageUrl: analysisJson['imageUrl'] as String?,
        );
      }

      state = state.copyWith(phase: VisionPhase.idle, currentAnalysis: analysis);
      await _refreshRecent();
    } catch (e) {
      state = state.copyWith(
        phase: VisionPhase.error,
        errorMessage: 'Screen capture failed: ${e.toString()}',
      );
    }
  }

  /// Ask a visual question about the current analysis.
  Future<void> askQuestion(String question) async {
    final analysisId = state.currentAnalysis?.analysisId;
    if (analysisId == null || analysisId.isEmpty) return;

    state = state.copyWith(
      phase: VisionPhase.asking,
      errorMessage: null,
      lastAnswer: null,
      lastAnswerQuestion: question,
    );
    try {
      final result = await _service.askQuestion(analysisId, question);
      state = state.copyWith(
        phase: VisionPhase.idle,
        lastAnswer: result['answer'] as String? ?? '(No answer returned)',
        lastAnswerQuestion: question,
      );
    } catch (e) {
      state = state.copyWith(
        phase: VisionPhase.error,
        errorMessage: 'Visual Q&A failed: ${e.toString()}',
      );
    }
  }

  /// Build a chat-ready context string from the current analysis.
  /// Returns the context string so the caller (Vision screen) can inject it
  /// into the chat via WS CHAT_REQUEST.
  Future<VisionContextResult?> buildContext() async {
    final analysisId = state.currentAnalysis?.analysisId;
    if (analysisId == null || analysisId.isEmpty) return null;

    state = state.copyWith(phase: VisionPhase.buildingContext, errorMessage: null);
    try {
      final ctx = await _service.buildContext(analysisId);
      state = state.copyWith(phase: VisionPhase.idle, lastContext: ctx);
      return ctx;
    } catch (e) {
      state = state.copyWith(
        phase: VisionPhase.error,
        errorMessage: 'Context build failed: ${e.toString()}',
      );
      return null;
    }
  }

  /// Mark that the context has been sent to chat.
  void markContextSentToChat() {
    state = state.copyWith(contextSentToChat: true);
  }

  /// Clear current analysis and start fresh.
  void clearAnalysis() {
    state = state.copyWith(
      phase: VisionPhase.idle,
      currentAnalysis: null,
      lastAnswer: null,
      lastAnswerQuestion: null,
      lastContext: null,
      errorMessage: null,
      contextSentToChat: false,
    );
  }

  Future<void> loadRecentAnalyses() async {
    try {
      final items = await _service.getRecentAnalyses();
      state = state.copyWith(recentItems: items);
    } catch (_) {
      // Non-fatal; recent panel is optional
    }
  }

  /// Load a previously stored analysis as the current result (e.g. from Recent panel).
  void loadStoredAnalysis(VisionAnalysisResult analysis) {
    state = state.copyWith(
      phase: VisionPhase.idle,
      currentAnalysis: analysis,
      lastAnswer: null,
      lastAnswerQuestion: null,
      lastContext: null,
      errorMessage: null,
      contextSentToChat: false,
    );
  }

  Future<void> deleteAnalysis(String analysisId) async {
    try {
      await _service.deleteAnalysis(analysisId);
      await _refreshRecent();
      if (state.currentAnalysis?.analysisId == analysisId) {
        clearAnalysis();
      }
    } catch (_) {}
  }

  Future<void> _refreshRecent() async {
    try {
      final items = await _service.getRecentAnalyses();
      state = state.copyWith(recentItems: items);
    } catch (_) {}
  }

  @override
  void dispose() {
    _service.dispose();
    super.dispose();
  }
}
