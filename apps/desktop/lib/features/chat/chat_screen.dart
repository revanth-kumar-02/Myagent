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

    // Auto scroll when streaming
    ref.listen(chatProvider, (previous, next) {
      if (next.isStreaming) {
        _scrollToBottom();
      }
    });

    return Container(
      color: AppTheme.bgLight,
      child: Column(
        children: [
          // Top Toolbar / Context Bar
          Container(
            height: 48,
            padding: const EdgeInsets.symmetric(horizontal: 16),
            decoration: const BoxDecoration(
              color: AppTheme.surfaceLight,
              border: Border(
                bottom: BorderSide(
                  color: AppTheme.borderLight,
                  width: 1,
                ),
              ),
            ),
            child: Row(
              children: [
                const Icon(Icons.forum_rounded, size: 16, color: AppTheme.primary),
                const SizedBox(width: 8),
                const Text(
                  'Kora Chat',
                  style: TextStyle(
                    fontWeight: FontWeight.w700,
                    fontSize: 13,
                    color: AppTheme.textPrimaryLight,
                  ),
                ),
                const SizedBox(width: 16),
                // Knowledge Context Selector Pill
                Container(
                  height: 30,
                  padding: const EdgeInsets.symmetric(horizontal: 10),
                  decoration: BoxDecoration(
                    color: AppTheme.surfaceHighlightLight,
                    borderRadius: BorderRadius.circular(8),
                    border: Border.all(color: AppTheme.borderLight),
                  ),
                  child: DropdownButtonHideUnderline(
                    child: DropdownButton<String?>(
                      value: chatState.selectedProjectId,
                      isDense: true,
                      icon: const Icon(Icons.keyboard_arrow_down_rounded, size: 16, color: AppTheme.textSecondaryLight),
                      style: const TextStyle(
                        fontSize: 12,
                        fontWeight: FontWeight.w500,
                        color: AppTheme.textPrimaryLight,
                      ),
                      items: [
                        const DropdownMenuItem(
                          value: null,
                          child: Row(
                            mainAxisSize: MainAxisSize.min,
                            children: [
                              Icon(Icons.hub_rounded, size: 13, color: AppTheme.primary),
                              SizedBox(width: 6),
                              Text('All Workspace Knowledge'),
                            ],
                          ),
                        ),
                        ...projectsState.projects.map((p) => DropdownMenuItem(
                          value: p.id,
                          child: Row(
                            mainAxisSize: MainAxisSize.min,
                            children: [
                              const Icon(Icons.folder_rounded, size: 13, color: AppTheme.secondary),
                              const SizedBox(width: 6),
                              Text('Project: ${p.name}'),
                            ],
                          ),
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
                    icon: const Icon(Icons.delete_sweep_rounded, size: 19, color: AppTheme.textSecondaryLight),
                    tooltip: 'Clear Conversation',
                    onPressed: () => ref.read(chatProvider.notifier).clearMessages(),
                  ),
              ],
            ),
          ),

          // Message Stream List
          Expanded(
            child: chatState.messages.isEmpty
                ? _buildEmptyState()
                : ListView.builder(
                    controller: _scrollController,
                    padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 16),
                    itemCount: chatState.messages.length,
                    itemBuilder: (context, index) {
                      final message = chatState.messages[index];
                      return _buildMessageItem(message);
                    },
                  ),
          ),

          // Bottom Floating Composer Dock
          Container(
            padding: const EdgeInsets.fromLTRB(20, 10, 20, 16),
            decoration: const BoxDecoration(
              color: AppTheme.bgLight,
              border: Border(
                top: BorderSide(
                  color: AppTheme.borderLight,
                  width: 1,
                ),
              ),
            ),
            child: Container(
              decoration: BoxDecoration(
                color: AppTheme.surfaceLight,
                borderRadius: BorderRadius.circular(12),
                border: Border.all(color: AppTheme.borderLight, width: 1),
                boxShadow: [
                  BoxShadow(
                    color: Colors.black.withValues(alpha: 0.04),
                    blurRadius: 10,
                    offset: const Offset(0, 3),
                  ),
                ],
              ),
              child: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  // Text input field
                  Padding(
                    padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 6),
                    child: TextField(
                      controller: _inputController,
                      focusNode: _inputFocusNode,
                      maxLines: 5,
                      minLines: 1,
                      style: const TextStyle(
                        fontSize: 13.5,
                        color: AppTheme.textPrimaryLight,
                        height: 1.4,
                      ),
                      decoration: const InputDecoration(
                        hintText: 'Ask Kora anything, query project knowledge, or trigger tools...',
                        hintStyle: TextStyle(color: AppTheme.textMuted, fontSize: 13),
                        filled: false,
                        border: InputBorder.none,
                        enabledBorder: InputBorder.none,
                        focusedBorder: InputBorder.none,
                        contentPadding: EdgeInsets.symmetric(vertical: 8),
                      ),
                      onSubmitted: (_) => _handleSend(),
                    ),
                  ),

                  // Bottom Dock Toolbar (Attachments, Voice, Capability, Send/Cancel)
                  Padding(
                    padding: const EdgeInsets.fromLTRB(10, 0, 10, 8),
                    child: Row(
                      children: [
                        // Attachment Action
                        IconButton(
                          icon: const Icon(Icons.attach_file_rounded, size: 18, color: AppTheme.textSecondaryLight),
                          tooltip: 'Attach Document or Image',
                          padding: const EdgeInsets.all(6),
                          constraints: const BoxConstraints(),
                          onPressed: () {
                            ScaffoldMessenger.of(context).showSnackBar(
                              const SnackBar(content: Text('File attachments indexed automatically via RAG.')),
                            );
                          },
                        ),
                        const SizedBox(width: 4),
                        // Voice Action
                        IconButton(
                          icon: const Icon(Icons.mic_rounded, size: 18, color: AppTheme.secondary),
                          tooltip: 'Voice Input',
                          padding: const EdgeInsets.all(6),
                          constraints: const BoxConstraints(),
                          onPressed: () {
                            ScaffoldMessenger.of(context).showSnackBar(
                              const SnackBar(content: Text('Voice audio model: Gemma-4 Audio Gateway ready.')),
                            );
                          },
                        ),
                        const SizedBox(width: 8),
                        // Capability Tag
                        Container(
                          padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                          decoration: BoxDecoration(
                            color: AppTheme.surfaceHighlightLight,
                            borderRadius: BorderRadius.circular(6),
                          ),
                          child: const Row(
                            mainAxisSize: MainAxisSize.min,
                            children: [
                              Icon(Icons.bolt_rounded, size: 12, color: AppTheme.primary),
                              SizedBox(width: 4),
                              Text(
                                'Capability Routing',
                                style: TextStyle(
                                  fontSize: 10.5,
                                  fontWeight: FontWeight.w600,
                                  color: AppTheme.textSecondaryLight,
                                ),
                              ),
                            ],
                          ),
                        ),
                        const Spacer(),
                        // Send or Stop/Cancel Action
                        if (chatState.isStreaming)
                          ElevatedButton.icon(
                            icon: const Icon(Icons.stop_rounded, size: 16),
                            label: const Text('Cancel'),
                            style: ElevatedButton.styleFrom(
                              backgroundColor: AppTheme.accent, // Terracotta Stop Button
                              foregroundColor: Colors.white,
                              padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 8),
                              shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
                            ),
                            onPressed: () => ref.read(chatProvider.notifier).cancelGeneration(),
                          )
                        else
                          ElevatedButton.icon(
                            icon: const Icon(Icons.arrow_upward_rounded, size: 16),
                            label: const Text('Send'),
                            style: ElevatedButton.styleFrom(
                              backgroundColor: AppTheme.primary, // Sage Green Primary
                              foregroundColor: Colors.white,
                              padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
                              shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
                            ),
                            onPressed: _handleSend,
                          ),
                      ],
                    ),
                  ),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildEmptyState() {
    return Center(
      child: SingleChildScrollView(
        child: Container(
          constraints: const BoxConstraints(maxWidth: 580),
          padding: const EdgeInsets.all(24),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Container(
                width: 52,
                height: 52,
                decoration: BoxDecoration(
                  color: AppTheme.primaryLight,
                  borderRadius: BorderRadius.circular(14),
                  border: Border.all(color: AppTheme.primary.withValues(alpha: 0.2)),
                ),
                child: const Icon(Icons.auto_awesome_rounded, color: AppTheme.primary, size: 28),
              ),
              const SizedBox(height: 16),
              const Text(
                'How can Kora assist you today?',
                style: TextStyle(
                  fontSize: 18,
                  fontWeight: FontWeight.w800,
                  color: AppTheme.textPrimaryLight,
                  letterSpacing: -0.3,
                ),
              ),
              const SizedBox(height: 8),
              const Text(
                'Autonomous agent with RAG document intelligence, persistent memory, and live DuckDuckGo research.',
                textAlign: TextAlign.center,
                style: TextStyle(fontSize: 13, color: AppTheme.textSecondaryLight, height: 1.4),
              ),
              const SizedBox(height: 24),
              // Starter Prompts in Warm Cards
              Wrap(
                spacing: 10,
                runSpacing: 10,
                alignment: WrapAlignment.center,
                children: [
                  _buildStarterChip('Search DuckDuckGo for latest Hugging Face models', Icons.travel_explore_rounded),
                  _buildStarterChip('Explain autonomous agent architecture and tools', Icons.psychology_rounded),
                  _buildStarterChip('Analyze project workspace files with RAG', Icons.folder_open_rounded),
                ],
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildStarterChip(String prompt, IconData icon) {
    return InkWell(
      onTap: () {
        _inputController.text = prompt;
        _handleSend();
      },
      borderRadius: BorderRadius.circular(10),
      child: Container(
        constraints: const BoxConstraints(maxWidth: 270),
        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
        decoration: BoxDecoration(
          color: AppTheme.surfaceLight,
          borderRadius: BorderRadius.circular(10),
          border: Border.all(color: AppTheme.borderLight),
          boxShadow: [
            BoxShadow(
              color: Colors.black.withValues(alpha: 0.02),
              blurRadius: 4,
              offset: const Offset(0, 2),
            ),
          ],
        ),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(icon, size: 15, color: AppTheme.primary),
            const SizedBox(width: 8),
            Flexible(
              child: Text(
                prompt,
                style: const TextStyle(
                  fontSize: 12,
                  fontWeight: FontWeight.w500,
                  color: AppTheme.textPrimaryLight,
                ),
                maxLines: 2,
                overflow: TextOverflow.ellipsis,
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildMessageItem(ChatMessage message) {
    final isUser = message.role == MessageRole.user;

    return Padding(
      padding: const EdgeInsets.only(bottom: 20),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        mainAxisAlignment: isUser ? MainAxisAlignment.end : MainAxisAlignment.start,
        children: [
          if (!isUser) ...[
            Container(
              width: 32,
              height: 32,
              margin: const EdgeInsets.only(right: 12, top: 2),
              decoration: BoxDecoration(
                color: AppTheme.primary,
                borderRadius: BorderRadius.circular(8),
                boxShadow: [
                  BoxShadow(
                    color: AppTheme.primary.withValues(alpha: 0.25),
                    blurRadius: 6,
                    offset: const Offset(0, 2),
                  ),
                ],
              ),
              child: const Center(
                child: Text(
                  'K',
                  style: TextStyle(
                    color: Colors.white,
                    fontWeight: FontWeight.w700,
                    fontSize: 15,
                  ),
                ),
              ),
            ),
          ],
          Flexible(
            child: Container(
              constraints: const BoxConstraints(maxWidth: 820),
              padding: const EdgeInsets.all(16),
              decoration: BoxDecoration(
                color: isUser
                    ? AppTheme.primaryLight
                    : AppTheme.surfaceLight,
                borderRadius: BorderRadius.circular(12),
                border: Border.all(
                  color: isUser
                      ? AppTheme.primary.withValues(alpha: 0.3)
                      : AppTheme.borderLight,
                  width: 1,
                ),
                boxShadow: [
                  BoxShadow(
                    color: Colors.black.withValues(alpha: 0.03),
                    blurRadius: 8,
                    offset: const Offset(0, 2),
                  ),
                ],
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  // Active Tool & Plan Stepper
                  if (!isUser && message.planSteps.isNotEmpty)
                    PlanProgressCard(steps: message.planSteps),

                  if (!isUser && message.activeTool != null)
                    Padding(
                      padding: const EdgeInsets.only(bottom: 10),
                      child: ToolBadge(
                        toolName: message.activeTool!,
                        isExecuting: message.status == MessageStatus.streaming,
                      ),
                    ),

                  // Message Content with Streaming/Thinking indicator
                  if (message.content.isEmpty && message.status == MessageStatus.streaming)
                    const Row(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        SizedBox(
                          width: 14,
                          height: 14,
                          child: CircularProgressIndicator(
                            strokeWidth: 2,
                            color: AppTheme.primary,
                          ),
                        ),
                        SizedBox(width: 10),
                        Text(
                          'Kora is reasoning & executing plan...',
                          style: TextStyle(
                            fontSize: 13,
                            fontWeight: FontWeight.w500,
                            color: AppTheme.statusThinking,
                            fontStyle: FontStyle.italic,
                          ),
                        ),
                      ],
                    )
                  else
                    SelectableText(
                      message.content,
                      style: const TextStyle(
                        fontSize: 13.5,
                        height: 1.5,
                        color: AppTheme.textPrimaryLight,
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
                      padding: const EdgeInsets.only(top: 10),
                      child: Row(
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          if (message.modelUsed != null) ...[
                            Container(
                              padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                              decoration: BoxDecoration(
                                color: AppTheme.surfaceHighlightLight,
                                borderRadius: BorderRadius.circular(4),
                              ),
                              child: Text(
                                message.modelUsed!,
                                style: const TextStyle(
                                  fontSize: 10,
                                  fontWeight: FontWeight.w600,
                                  color: AppTheme.textSecondaryLight,
                                ),
                              ),
                            ),
                            const SizedBox(width: 8),
                          ],
                          if (message.latencyMs != null) ...[
                            Text(
                              '${message.latencyMs}ms',
                              style: const TextStyle(fontSize: 10, color: AppTheme.textMuted),
                            ),
                            const SizedBox(width: 8),
                          ],
                          Text(
                            DateFormatter.formatShortTime(message.timestamp),
                            style: const TextStyle(fontSize: 10, color: AppTheme.textMuted),
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

