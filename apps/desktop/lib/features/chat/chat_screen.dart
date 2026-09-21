import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/theme/app_theme.dart';
import '../../core/utils/date_formatter.dart';
import '../../models/chat_message.dart';
import '../../state/chat_state.dart';
import '../../state/projects_state.dart';
import '../../widgets/citation_card.dart';
import '../../widgets/plan_progress_card.dart';
import '../../widgets/tool_badge.dart';

class ChatScreen extends ConsumerStatefulWidget {
  const ChatScreen({super.key});

  @override
  ConsumerState<ChatScreen> createState() => _ChatScreenState();
}

class _ChatScreenState extends ConsumerState<ChatScreen> {
  final TextEditingController _inputController = TextEditingController();
  final ScrollController _scrollController = ScrollController();
  final FocusNode _inputFocusNode = FocusNode();

  @override
  void dispose() {
    _inputController.dispose();
    _scrollController.dispose();
    _inputFocusNode.dispose();
    super.dispose();
  }

  void _scrollToBottom() {
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (_scrollController.hasClients) {
        _scrollController.animateTo(
          _scrollController.position.maxScrollExtent,
          duration: const Duration(milliseconds: 200),
          curve: Curves.easeOut,
        );
      }
    });
  }

  void _handleSend() {
    final text = _inputController.text;
    if (text.trim().isEmpty) return;

    ref.read(chatProvider.notifier).sendMessage(text);
    _inputController.clear();
    _scrollToBottom();
  }

  @override
  Widget build(BuildContext context) {
    final chatState = ref.watch(chatProvider);
    final projectsState = ref.watch(projectsProvider);
    final isDark = Theme.of(context).brightness == Brightness.dark;

    // Auto scroll when streaming
    ref.listen(chatProvider, (previous, next) {
      if (next.isStreaming) {
        _scrollToBottom();
      }
    });

    return Column(
      children: [
        // Top Toolbar
        Container(
          height: 48,
          padding: const EdgeInsets.symmetric(horizontal: 16),
          decoration: BoxDecoration(
            border: Border(
              bottom: BorderSide(
                color: isDark ? AppTheme.borderDark : AppTheme.borderLight,
                width: 1,
              ),
            ),
          ),
          child: Row(
            children: [
              const Icon(Icons.chat_bubble_outline, size: 16, color: AppTheme.primary),
              const SizedBox(width: 8),
              const Text(
                'Kora Chat',
                style: TextStyle(fontWeight: FontWeight.w600, fontSize: 13),
              ),
              const SizedBox(width: 16),
              // Project selector
              Container(
                height: 28,
                padding: const EdgeInsets.symmetric(horizontal: 8),
                decoration: BoxDecoration(
                  color: isDark ? const Color(0xFF1E293B) : const Color(0xFFF1F5F9),
                  borderRadius: BorderRadius.circular(6),
                ),
                child: DropdownButtonHideUnderline(
                  child: DropdownButton<String?>(
                    value: chatState.selectedProjectId,
                    isDense: true,
                    style: TextStyle(
                      fontSize: 12,
                      color: isDark ? AppTheme.textPrimaryDark : AppTheme.textPrimaryLight,
                    ),
                    items: [
                      const DropdownMenuItem(
                        value: null,
                        child: Text('All Workspace Knowledge'),
                      ),
                      ...projectsState.projects.map((p) => DropdownMenuItem(
                        value: p.id,
                        child: Text('Project: ${p.name}'),
                      )),
                    ],
                    onChanged: (val) {
                      ref.read(chatProvider.notifier).setSelectedProject(val);
                    },
                  ),
                ),
              ),
              const Spacer(),
              if (chatState.messages.isNotEmpty)
                IconButton(
                  icon: const Icon(Icons.delete_outline, size: 18),
                  tooltip: 'Clear Conversation',
                  onPressed: () => ref.read(chatProvider.notifier).clearMessages(),
                ),
            ],
          ),
        ),

        // Message List
        Expanded(
          child: chatState.messages.isEmpty
              ? _buildEmptyState()
              : ListView.builder(
                  controller: _scrollController,
                  padding: const EdgeInsets.all(16),
                  itemCount: chatState.messages.length,
                  itemBuilder: (context, index) {
                    final message = chatState.messages[index];
                    return _buildMessageItem(message, isDark);
                  },
                ),
        ),

        // Bottom Input Area
        Container(
          padding: const EdgeInsets.all(12),
          decoration: BoxDecoration(
            color: isDark ? AppTheme.surfaceDark : AppTheme.surfaceLight,
            border: Border(
              top: BorderSide(
                color: isDark ? AppTheme.borderDark : AppTheme.borderLight,
                width: 1,
              ),
            ),
          ),
          child: Row(
            crossAxisAlignment: CrossAxisAlignment.end,
            children: [
              Expanded(
                child: TextField(
                  controller: _inputController,
                  focusNode: _inputFocusNode,
                  maxLines: 4,
                  minLines: 1,
                  style: const TextStyle(fontSize: 13),
                  decoration: InputDecoration(
                    hintText: 'Ask Kora anything or trigger tools...',
                    hintStyle: TextStyle(
                      color: isDark ? AppTheme.textSecondaryDark : AppTheme.textSecondaryLight,
                    ),
                    filled: true,
                    fillColor: isDark ? const Color(0xFF0F172A) : const Color(0xFFF8FAFC),
                    border: OutlineInputBorder(
                      borderRadius: BorderRadius.circular(8),
                      borderSide: BorderSide(
                        color: isDark ? AppTheme.borderDark : AppTheme.borderLight,
                      ),
                    ),
                  ),
                  onSubmitted: (_) => _handleSend(),
                ),
              ),
              const SizedBox(width: 8),
              if (chatState.isStreaming)
                IconButton.filled(
                  icon: const Icon(Icons.stop, size: 18),
                  tooltip: 'Stop Generation',
                  style: IconButton.styleFrom(
                    backgroundColor: AppTheme.error,
                    foregroundColor: Colors.white,
                    shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
                  ),
                  onPressed: () => ref.read(chatProvider.notifier).cancelGeneration(),
                )
              else
                IconButton.filled(
                  icon: const Icon(Icons.send_rounded, size: 18),
                  tooltip: 'Send Message',
                  style: IconButton.styleFrom(
                    backgroundColor: AppTheme.primary,
                    foregroundColor: Colors.white,
                    shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
                  ),
                  onPressed: _handleSend,
                ),
            ],
          ),
        ),
      ],
    );
  }

  Widget _buildEmptyState() {
    return Center(
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          Container(
            width: 48,
            height: 48,
            decoration: BoxDecoration(
              color: AppTheme.primary.withValues(alpha: 0.15),
              borderRadius: BorderRadius.circular(12),
            ),
            child: const Icon(Icons.auto_awesome, color: AppTheme.primary, size: 24),
          ),
          const SizedBox(height: 12),
          const Text(
            'How can Kora help you today?',
            style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold),
          ),
          const SizedBox(height: 6),
          const Text(
            'Connected to Hugging Face models with RAG, Memory, & DuckDuckGo.',
            style: TextStyle(fontSize: 12, color: Colors.grey),
          ),
        ],
      ),
    );
  }

  Widget _buildMessageItem(ChatMessage message, bool isDark) {
    final isUser = message.role == MessageRole.user;

    return Padding(
      padding: const EdgeInsets.only(bottom: 16),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        mainAxisAlignment: isUser ? MainAxisAlignment.end : MainAxisAlignment.start,
        children: [
          if (!isUser) ...[
            Container(
              width: 28,
              height: 28,
              margin: const EdgeInsets.only(right: 10, top: 2),
              decoration: BoxDecoration(
                color: AppTheme.primary,
                borderRadius: BorderRadius.circular(6),
              ),
              child: const Center(
                child: Text(
                  'K',
                  style: TextStyle(
                    color: Colors.white,
                    fontWeight: FontWeight.bold,
                    fontSize: 14,
                  ),
                ),
              ),
            ),
          ],
          Flexible(
            child: Container(
              padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
              decoration: BoxDecoration(
                color: isUser
                    ? AppTheme.primary
                    : (isDark ? AppTheme.surfaceDark : AppTheme.surfaceLight),
                borderRadius: BorderRadius.circular(8),
                border: isUser
                    ? null
                    : Border.all(
                        color: isDark ? AppTheme.borderDark : AppTheme.borderLight,
                      ),
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  // Active tool badge or Plan steps
                  if (!isUser && message.planSteps.isNotEmpty)
                    PlanProgressCard(steps: message.planSteps),

                  if (!isUser && message.activeTool != null)
                    Padding(
                      padding: const EdgeInsets.only(bottom: 8),
                      child: ToolBadge(
                        toolName: message.activeTool!,
                        isExecuting: message.status == MessageStatus.streaming,
                      ),
                    ),

                  // Message Content
                  SelectableText(
                    message.content.isEmpty && message.status == MessageStatus.streaming
                        ? 'Thinking...'
                        : message.content,
                    style: TextStyle(
                      fontSize: 13,
                      height: 1.45,
                      color: isUser ? Colors.white : null,
                    ),
                  ),

                  // Sources & Citations
                  if (!isUser && (message.sources.isNotEmpty || message.webSources.isNotEmpty))
                    CitationCard(
                      sources: message.sources,
                      webSources: message.webSources,
                    ),

                  // Metadata footer
                  if (!isUser && message.status == MessageStatus.done)
                    Padding(
                      padding: const EdgeInsets.only(top: 8),
                      child: Row(
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          if (message.modelUsed != null) ...[
                            Text(
                              message.modelUsed!,
                              style: const TextStyle(fontSize: 10, color: Colors.grey),
                            ),
                            const SizedBox(width: 8),
                          ],
                          if (message.latencyMs != null) ...[
                            Text(
                              '${message.latencyMs}ms',
                              style: const TextStyle(fontSize: 10, color: Colors.grey),
                            ),
                            const SizedBox(width: 8),
                          ],
                          Text(
                            DateFormatter.formatShortTime(message.timestamp),
                            style: const TextStyle(fontSize: 10, color: Colors.grey),
                          ),
                        ],
                      ),
                    ),
                ],
              ),
            ),
          ),
          if (isUser) const SizedBox(width: 4),
        ],
      ),
    );
  }
}
