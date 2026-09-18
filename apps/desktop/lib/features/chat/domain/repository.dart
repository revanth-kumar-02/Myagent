import 'entities.dart';

/// ChatRepository — Domain interface for chat operations.
/// Implemented in data/repository_impl.dart.
abstract class ChatRepository {
  /// Send a user message and return a stream of assistant reply chunks.
  Stream<ChatMessage> sendMessage({
    required String message,
    required String sessionId,
    String? projectId,
  });

  /// Load cached history for a session.
  Future<List<ChatMessage>> loadHistory(String sessionId);

  /// Clear history for a session.
  Future<void> clearHistory(String sessionId);
}
