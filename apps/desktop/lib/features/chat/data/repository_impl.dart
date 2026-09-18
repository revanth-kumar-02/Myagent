import '../domain/entities.dart';
import '../domain/repository.dart';

/// ChatRepositoryImpl — Data layer implementation of ChatRepository.
///
/// Wires together KoraSocketService messages → ChatMessage domain objects.
/// Maintains in-memory message history for the session.
/// Full implementation deferred to feature phase.
class ChatRepositoryImpl implements ChatRepository {
  @override
  Stream<ChatMessage> sendMessage({
    required String message,
    required String sessionId,
    String? projectId,
  }) {
    throw UnimplementedError(); // TODO: implement in feature phase
  }

  @override
  Future<List<ChatMessage>> loadHistory(String sessionId) async {
    throw UnimplementedError(); // TODO: implement in feature phase
  }

  @override
  Future<void> clearHistory(String sessionId) async {
    throw UnimplementedError(); // TODO: implement in feature phase
  }
}
