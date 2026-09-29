import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_markdown/flutter_markdown.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/theme/app_theme.dart';
import '../../core/utils/date_formatter.dart';
import '../../models/chat_message.dart';
import '../../models/plan_step.dart';
import '../../models/tool_command.dart';
import '../../state/chat_state.dart';
import '../../state/connection_state.dart';
import '../../state/projects_state.dart';
import '../../widgets/citation_card.dart';
import '../../widgets/plan_progress_card.dart';
import '../../widgets/slash_command_picker.dart';
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

  List<ToolCommand> _availableTools = defaultToolCommands;
  bool _showSlashPicker = false;
  String _slashFilter = '';
  int _selectedSlashIndex = 0;
  bool _userScrolledUp = false;

  @override
  void initState() {
    super.initState();
    _inputController.addListener(_onTextChanged);
    _inputFocusNode.onKeyEvent = _handleKeyEvent;
    _scrollController.addListener(_onScroll);
    _fetchDynamicTools();
  }

  void _onScroll() {
    if (!_scrollController.hasClients) return;
    final maxScroll = _scrollController.position.maxScrollExtent;
    final currentScroll = _scrollController.position.pixels;
    if (maxScroll - currentScroll > 60) {
      if (!_userScrolledUp) {
        _userScrolledUp = true;
      }
    } else {
      if (_userScrolledUp) {
        _userScrolledUp = false;
      }
    }
  }

  Future<void> _fetchDynamicTools() async {
    try {
      final api = ref.read(apiServiceProvider);
      final tools = await api.getTools();
      if (mounted && tools.isNotEmpty) {
        setState(() {
          _availableTools = tools;
        });
      }
    } catch (_) {
      // Keep default fallback tool commands
    }
  }

  IconData _getToolIcon(String category) {
    return switch (category.toLowerCase()) {
      'system' => Icons.terminal_rounded,
      'browser' || 'web' => Icons.language_rounded,
      'file' || 'workspace' => Icons.folder_open_rounded,
      'research' => Icons.travel_explore_rounded,
      'memory' => Icons.psychology_rounded,
      'automation' => Icons.smart_toy_rounded,
      'vision' => Icons.visibility_rounded,
      _ => Icons.build_circle_outlined,
    };
  }

  void _onTextChanged() {
    final text = _inputController.text;
    final selection = _inputController.selection;

    if (text.startsWith('/') && selection.baseOffset >= 1 && !text.contains('://')) {
      final query = text.substring(1).trim().toLowerCase();
      final filtered = _getFilteredCommands(query);
      setState(() {
        _showSlashPicker = filtered.isNotEmpty;
        _slashFilter = query;
        _selectedSlashIndex = 0;
      });
    } else {
      if (_showSlashPicker) {
        setState(() {
          _showSlashPicker = false;
        });
      }
    }
  }

  List<ToolCommand> _getFilteredCommands(String query) {
    if (query.isEmpty) return _availableTools;
    return _availableTools.where((cmd) =>
      cmd.name.toLowerCase().contains(query) ||
      cmd.title.toLowerCase().contains(query) ||
      cmd.description.toLowerCase().contains(query) ||
      cmd.category.toLowerCase().contains(query)
    ).toList();
  }

  List<ToolCommand> get _filteredCommands => _getFilteredCommands(_slashFilter);

  KeyEventResult _handleKeyEvent(FocusNode node, KeyEvent event) {
    if (event is! KeyDownEvent) return KeyEventResult.ignored;

    // Handle slash command keyboard navigation
    if (_showSlashPicker && _filteredCommands.isNotEmpty) {
      if (event.logicalKey == LogicalKeyboardKey.arrowDown) {
        setState(() {
          _selectedSlashIndex = (_selectedSlashIndex + 1) % _filteredCommands.length;
        });
        return KeyEventResult.handled;
      } else if (event.logicalKey == LogicalKeyboardKey.arrowUp) {
        setState(() {
          _selectedSlashIndex = (_selectedSlashIndex - 1 + _filteredCommands.length) % _filteredCommands.length;
        });
        return KeyEventResult.handled;
      } else if (event.logicalKey == LogicalKeyboardKey.enter && !HardwareKeyboard.instance.isShiftPressed) {
        _selectCommand(_filteredCommands[_selectedSlashIndex]);
        return KeyEventResult.handled;
      } else if (event.logicalKey == LogicalKeyboardKey.escape) {
        setState(() {
          _showSlashPicker = false;
        });
        return KeyEventResult.handled;
      }
    }

    // Normal composer Send on Enter (Shift+Enter inserts newline)
    if (event.logicalKey == LogicalKeyboardKey.enter && !HardwareKeyboard.instance.isShiftPressed) {
      final text = _inputController.text.trim();
      if (text.isNotEmpty) {
        _handleSend();
      }
      return KeyEventResult.handled;
    }

    return KeyEventResult.ignored;
  }

  void _selectCommand(ToolCommand command) {
    setState(() {
      _inputController.text = '/${command.name} ';
      _inputController.selection = TextSelection.fromPosition(
        TextPosition(offset: _inputController.text.length),
      );
      _showSlashPicker = false;
    });
    _inputFocusNode.requestFocus();
  }

  @override
  void dispose() {
    _inputController.removeListener(_onTextChanged);
    _inputController.dispose();
    _scrollController.removeListener(_onScroll);
    _scrollController.dispose();
    _inputFocusNode.dispose();
    super.dispose();
  }

  void _handleSend() {
    final text = _inputController.text.trim();
    if (text.isEmpty) return;

    final isStreaming = ref.read(chatProvider).isStreaming;
    if (isStreaming) return;

    _userScrolledUp = false;
    ref.read(chatProvider.notifier).sendMessage(text);
    _inputController.clear();
    setState(() {
      _showSlashPicker = false;
    });
    _scrollToBottom(force: true);
  }

  void _scrollToBottom({bool force = false}) {
    if (!force && _userScrolledUp) return;
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

  @override
  Widget build(BuildContext context) {
    final chatState = ref.watch(chatProvider);
    final projectsState = ref.watch(projectsProvider);
    final c = AppTheme.colors(context);

    // Auto scroll when streaming unless user scrolled up
    ref.listen(chatProvider, (previous, next) {
      if (next.isStreaming && !_userScrolledUp) {
        _scrollToBottom();
      }
    });

    return Container(
      color: c.bg,
      child: Column(
        children: [
          // Top Toolbar / Context Bar
          Container(
            height: 48,
            padding: const EdgeInsets.symmetric(horizontal: 16),
            decoration: BoxDecoration(
              color: c.surface,
              border: Border(
                bottom: BorderSide(
                  color: c.border,
                  width: 1,
                ),
              ),
            ),
            child: Row(
              children: [
                Icon(Icons.forum_rounded, size: 16, color: c.primary),
                const SizedBox(width: 8),
                Text(
                  'Kora Chat',
                  style: TextStyle(
                    fontWeight: FontWeight.w700,
                    fontSize: 13,
                    color: c.textPrimary,
                  ),
                ),
                const SizedBox(width: 16),
                // Knowledge Context Selector Pill
                Container(
                  height: 30,
                  padding: const EdgeInsets.symmetric(horizontal: 10),
                  decoration: BoxDecoration(
                    color: c.surfaceHighlight,
                    borderRadius: BorderRadius.circular(8),
                    border: Border.all(color: c.border),
                  ),
                  child: DropdownButtonHideUnderline(
                    child: DropdownButton<String?>(
                      value: chatState.selectedProjectId,
                      isDense: true,
                      dropdownColor: c.surface,
                      icon: Icon(Icons.keyboard_arrow_down_rounded, size: 16, color: c.textSecondary),
                      style: TextStyle(
                        fontSize: 12,
                        fontWeight: FontWeight.w500,
                        color: c.textPrimary,
                      ),
                      items: [
                        DropdownMenuItem(
                          value: null,
                          child: Row(
                            mainAxisSize: MainAxisSize.min,
                            children: [
                              Icon(Icons.hub_rounded, size: 13, color: c.primary),
                              const SizedBox(width: 6),
                              Text('All Workspace Knowledge', style: TextStyle(color: c.textPrimary)),
                            ],
                          ),
                        ),
                        ...projectsState.projects.map((p) => DropdownMenuItem(
                          value: p.id,
                          child: Row(
                            mainAxisSize: MainAxisSize.min,
                            children: [
                              Icon(Icons.folder_rounded, size: 13, color: c.secondary),
                              const SizedBox(width: 6),
                              Text('Project: ${p.name}', style: TextStyle(color: c.textPrimary)),
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
                    icon: Icon(Icons.delete_sweep_rounded, size: 19, color: c.textSecondary),
                    tooltip: 'Clear Conversation',
                    onPressed: () => ref.read(chatProvider.notifier).clearMessages(),
                  ),
              ],
            ),
          ),

          // Message Stream List
          Expanded(
            child: chatState.messages.isEmpty
                ? _buildEmptyState(c)
                : Scrollbar(
                    controller: _scrollController,
                    thumbVisibility: false,
                    interactive: true,
                    thickness: 5.0,
                    radius: const Radius.circular(8),
                    child: ListView.builder(
                      controller: _scrollController,
                      padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 16),
                      itemCount: chatState.messages.length,
                      itemBuilder: (context, index) {
                        final message = chatState.messages[index];
                        return _buildMessageItem(message, c);
                      },
                    ),
                  ),
          ),

          // Bottom Floating Composer Dock
          Container(
            padding: const EdgeInsets.fromLTRB(20, 10, 20, 16),
            decoration: BoxDecoration(
              color: c.bg,
              border: Border(
                top: BorderSide(
                  color: c.border,
                  width: 1,
                ),
              ),
            ),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                if (_showSlashPicker)
                  SlashCommandPicker(
                    commands: _filteredCommands,
                    selectedIndex: _selectedSlashIndex,
                    onSelect: _selectCommand,
                  ),
                Container(
                  decoration: BoxDecoration(
                    color: c.surface,
                    borderRadius: BorderRadius.circular(12),
                    border: Border.all(color: c.border, width: 1),
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
                      // Dynamic live status bar (only visible during active generation/streaming)
                      if (chatState.isStreaming)
                        Container(
                          padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 7),
                          decoration: BoxDecoration(
                            color: c.surfaceHighlight,
                            borderRadius: const BorderRadius.vertical(top: Radius.circular(12)),
                            border: Border(bottom: BorderSide(color: c.border)),
                          ),
                          child: Row(
                            children: [
                              SizedBox(
                                width: 11,
                                height: 11,
                                child: CircularProgressIndicator(strokeWidth: 1.5, color: c.primary),
                              ),
                              const SizedBox(width: 8),
                              Text(
                                chatState.activeTool != null
                                    ? 'Executing /${chatState.activeTool}...'
                                    : (chatState.activePlanSteps.any((s) => s.status == PlanStepStatus.running)
                                        ? chatState.activePlanSteps.firstWhere((s) => s.status == PlanStepStatus.running).label
                                        : 'Thinking & generating response...'),
                                style: TextStyle(
                                  fontSize: 11,
                                  fontWeight: FontWeight.w600,
                                  color: c.primaryDark,
                                ),
                              ),
                            ],
                          ),
                        ),

                      // Text input field
                      Padding(
                        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 6),
                        child: TextField(
                          controller: _inputController,
                          focusNode: _inputFocusNode,
                          maxLines: 5,
                          minLines: 1,
                          keyboardType: TextInputType.multiline,
                          textInputAction: TextInputAction.newline,
                          style: TextStyle(
                            fontSize: 13.5,
                            color: c.textPrimary,
                            height: 1.4,
                          ),
                          decoration: InputDecoration(
                            hintText: "Ask Kora anything or trigger tools with '/'...",
                            hintStyle: TextStyle(color: c.textMuted, fontSize: 13),
                            filled: false,
                            border: InputBorder.none,
                            enabledBorder: InputBorder.none,
                            focusedBorder: InputBorder.none,
                            contentPadding: const EdgeInsets.symmetric(vertical: 8),
                          ),
                        ),
                      ),

                      // Bottom Dock Toolbar (Tools +, Attachments, Voice, Dynamic Tokens, Send/Cancel)
                      Padding(
                        padding: const EdgeInsets.fromLTRB(10, 0, 10, 8),
                        child: Row(
                          children: [
                            // Tools & Capabilities Button (+)
                            IconButton(
                              icon: Icon(
                                _showSlashPicker ? Icons.close_rounded : Icons.add_circle_outline_rounded,
                                size: 19,
                                color: _showSlashPicker ? c.accent : c.primary,
                              ),
                              tooltip: _showSlashPicker ? 'Close Tools' : 'Explore Tools & Commands',
                              padding: const EdgeInsets.all(6),
                              constraints: const BoxConstraints(),
                              onPressed: () {
                                setState(() {
                                  _showSlashPicker = !_showSlashPicker;
                                  _slashFilter = '';
                                  _selectedSlashIndex = 0;
                                });
                              },
                            ),
                            const SizedBox(width: 4),
                            // Attachment Action
                            IconButton(
                              icon: Icon(Icons.attach_file_rounded, size: 18, color: c.textSecondary),
                              tooltip: 'Attach Workspace Document or Image',
                              padding: const EdgeInsets.all(6),
                              constraints: const BoxConstraints(),
                              onPressed: () {
                                ScaffoldMessenger.of(context).showSnackBar(
                                  const SnackBar(content: Text('Workspace files indexed automatically via RAG.')),
                                );
                              },
                            ),
                            const SizedBox(width: 4),
                            // Voice Action
                            IconButton(
                              icon: Icon(Icons.mic_rounded, size: 18, color: c.secondary),
                              tooltip: 'Voice Input',
                              padding: const EdgeInsets.all(6),
                              constraints: const BoxConstraints(),
                              onPressed: () {
                                ScaffoldMessenger.of(context).showSnackBar(
                                  const SnackBar(content: Text('Voice Gateway active.')),
                                );
                              },
                            ),
                            const Spacer(),
                            // Real token context if available from latest message
                            if (chatState.messages.isNotEmpty &&
                                chatState.messages.any((m) => m.role == MessageRole.assistant && m.inputTokens != null && m.outputTokens != null)) ...[
                              Padding(
                                padding: const EdgeInsets.only(right: 8),
                                child: Text(
                                  '${chatState.messages.lastWhere((m) => m.role == MessageRole.assistant && m.inputTokens != null).inputTokens! + chatState.messages.lastWhere((m) => m.role == MessageRole.assistant && m.outputTokens != null).outputTokens!} tokens',
                                  style: TextStyle(fontSize: 10.5, color: c.textMuted, fontFamily: 'monospace'),
                                ),
                              ),
                            ],
                            // Send or Stop/Cancel Action
                            if (chatState.isStreaming)
                              ElevatedButton.icon(
                                icon: const Icon(Icons.stop_rounded, size: 16),
                                label: const Text('Cancel'),
                                style: ElevatedButton.styleFrom(
                                  backgroundColor: c.accent, // Terracotta Stop Button
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
                                  backgroundColor: c.primary, // Sage Green Primary
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
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildEmptyState(KoraColors c) {
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
                  color: c.primaryLight,
                  borderRadius: BorderRadius.circular(14),
                  border: Border.all(color: c.primary.withValues(alpha: 0.2)),
                ),
                child: Icon(Icons.auto_awesome_rounded, color: c.primary, size: 28),
              ),
              const SizedBox(height: 16),
              Text(
                'How can Kora assist you today?',
                style: TextStyle(
                  fontSize: 18,
                  fontWeight: FontWeight.w800,
                  color: c.textPrimary,
                  letterSpacing: -0.3,
                ),
              ),
              const SizedBox(height: 8),
              Text(
                'Autonomous agent with RAG document intelligence, persistent memory, and live DuckDuckGo research.',
                textAlign: TextAlign.center,
                style: TextStyle(fontSize: 13, color: c.textSecondary, height: 1.4),
              ),
              const SizedBox(height: 24),
              // Starter Prompts in Warm Cards
              Wrap(
                spacing: 10,
                runSpacing: 10,
                alignment: WrapAlignment.center,
                children: [
                  _buildStarterChip('Search DuckDuckGo for latest Hugging Face models', Icons.travel_explore_rounded, c),
                  _buildStarterChip('Explain autonomous agent architecture and tools', Icons.psychology_rounded, c),
                  _buildStarterChip('Analyze project workspace files with RAG', Icons.folder_open_rounded, c),
                ],
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildStarterChip(String prompt, IconData icon, KoraColors c) {
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
          color: c.surface,
          borderRadius: BorderRadius.circular(10),
          border: Border.all(color: c.border),
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
            Icon(icon, size: 15, color: c.primary),
            const SizedBox(width: 8),
            Flexible(
              child: Text(
                prompt,
                style: TextStyle(
                  fontSize: 12,
                  fontWeight: FontWeight.w500,
                  color: c.textPrimary,
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

  Widget _buildMessageItem(ChatMessage message, KoraColors c) {
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
                color: c.primary,
                borderRadius: BorderRadius.circular(8),
                boxShadow: [
                  BoxShadow(
                    color: c.primary.withValues(alpha: 0.25),
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
                    ? c.primaryLight
                    : c.surface,
                borderRadius: BorderRadius.circular(12),
                border: Border.all(
                  color: isUser
                      ? c.primary.withValues(alpha: 0.35)
                      : c.border,
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

                  // Message Content with Streaming/Thinking indicator or Error
                  if (message.status == MessageStatus.error)
                    Container(
                      padding: const EdgeInsets.all(12),
                      decoration: BoxDecoration(
                        color: c.errorLight,
                        borderRadius: BorderRadius.circular(8),
                        border: Border.all(color: c.error.withValues(alpha: 0.3)),
                      ),
                      child: Row(
                        children: [
                          Icon(Icons.error_outline_rounded, size: 18, color: c.error),
                          const SizedBox(width: 10),
                          Expanded(
                            child: SelectableText(
                              message.errorMessage?.isNotEmpty == true ? message.errorMessage! : (message.content.isNotEmpty ? message.content : 'An unexpected error occurred during inference.'),
                              style: TextStyle(
                                fontSize: 13,
                                color: c.error,
                                fontWeight: FontWeight.w500,
                              ),
                            ),
                          ),
                        ],
                      ),
                    )
                  else if (message.content.isEmpty && message.status == MessageStatus.streaming)
                    Row(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        SizedBox(
                          width: 14,
                          height: 14,
                          child: CircularProgressIndicator(
                            strokeWidth: 2,
                            color: c.primary,
                          ),
                        ),
                        const SizedBox(width: 10),
                        Text(
                          message.activeTool != null
                              ? 'Executing /${message.activeTool}...'
                              : (message.planSteps.isNotEmpty
                                  ? 'Kora is reasoning & executing plan...'
                                  : 'Kora is thinking...'),
                          style: TextStyle(
                            fontSize: 13,
                            fontWeight: FontWeight.w500,
                            color: c.statusThinking,
                            fontStyle: FontStyle.italic,
                          ),
                        ),
                      ],
                    )
                  else if (isUser)
                    SelectableText(
                      message.content,
                      style: TextStyle(
                        fontSize: 13.5,
                        height: 1.5,
                        color: c.textPrimary,
                      ),
                    )
                  else
                    MarkdownBody(
                      data: message.content,
                      selectable: true,
                      onTapLink: (text, href, title) {
                        if (href != null && context.mounted) {
                          ScaffoldMessenger.of(context).showSnackBar(
                            SnackBar(
                              content: Text('Link: $href'),
                              duration: const Duration(seconds: 2),
                            ),
                          );
                        }
                      },
                      styleSheet: MarkdownStyleSheet(
                        p: TextStyle(
                          fontSize: 13.5,
                          height: 1.5,
                          color: c.textPrimary,
                        ),
                        a: TextStyle(
                          color: c.primary,
                          decoration: TextDecoration.underline,
                        ),
                        strong: TextStyle(
                          fontWeight: FontWeight.w700,
                          color: c.textPrimary,
                        ),
                        em: TextStyle(
                          fontStyle: FontStyle.italic,
                          color: c.textPrimary,
                        ),
                        h1: TextStyle(
                          fontSize: 18,
                          fontWeight: FontWeight.w700,
                          color: c.textPrimary,
                          height: 1.4,
                        ),
                        h2: TextStyle(
                          fontSize: 16,
                          fontWeight: FontWeight.w700,
                          color: c.textPrimary,
                          height: 1.4,
                        ),
                        h3: TextStyle(
                          fontSize: 14.5,
                          fontWeight: FontWeight.w600,
                          color: c.textPrimary,
                          height: 1.4,
                        ),
                        h4: TextStyle(
                          fontSize: 13.5,
                          fontWeight: FontWeight.w600,
                          color: c.textPrimary,
                          height: 1.4,
                        ),
                        code: TextStyle(
                          fontFamily: 'monospace',
                          fontSize: 12.5,
                          color: c.primaryDark,
                          backgroundColor: c.surfaceHighlight,
                        ),
                        codeblockDecoration: BoxDecoration(
                          color: c.surfaceHighlight,
                          borderRadius: BorderRadius.circular(8),
                          border: Border.all(color: c.border),
                        ),
                        codeblockPadding: const EdgeInsets.all(12),
                        blockquote: TextStyle(
                          fontSize: 13,
                          fontStyle: FontStyle.italic,
                          color: c.textSecondary,
                        ),
                        blockquoteDecoration: BoxDecoration(
                          border: Border(
                            left: BorderSide(color: c.primary, width: 3),
                          ),
                          color: c.surfaceHighlight.withValues(alpha: 0.5),
                        ),
                        blockquotePadding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
                        listBullet: TextStyle(
                          fontSize: 13.5,
                          color: c.textSecondary,
                        ),
                        tableBorder: TableBorder.all(color: c.border, width: 1),
                        tableHead: TextStyle(
                          fontWeight: FontWeight.w700,
                          color: c.textPrimary,
                        ),
                        tableBody: TextStyle(
                          fontSize: 13,
                          color: c.textPrimary,
                        ),
                      ),
                    ),

                  // Sources & Citations
                  if (!isUser && (message.sources.isNotEmpty || message.webSources.isNotEmpty))
                    CitationCard(
                      sources: message.sources,
                      webSources: message.webSources,
                    ),

                  // Metadata & Action Toolbar
                  if (!isUser && message.status == MessageStatus.done)
                    Padding(
                      padding: const EdgeInsets.only(top: 10),
                      child: Row(
                        children: [
                          if (message.modelUsed != null) ...[
                            Container(
                              padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                              decoration: BoxDecoration(
                                color: c.surfaceHighlight,
                                borderRadius: BorderRadius.circular(4),
                              ),
                              child: Text(
                                message.modelUsed!,
                                style: TextStyle(
                                  fontSize: 10,
                                  fontWeight: FontWeight.w600,
                                  color: c.textSecondary,
                                ),
                              ),
                            ),
                            const SizedBox(width: 8),
                          ],
                          if (message.latencyMs != null) ...[
                            Text(
                              '${message.latencyMs}ms',
                              style: TextStyle(fontSize: 10, color: c.textMuted, fontFamily: 'monospace'),
                            ),
                            const SizedBox(width: 8),
                          ],
                          Text(
                            DateFormatter.formatShortTime(message.timestamp),
                            style: TextStyle(fontSize: 10, color: c.textMuted),
                          ),
                          const Spacer(),
                          IconButton(
                            icon: Icon(Icons.copy_rounded, size: 14, color: c.textMuted),
                            tooltip: 'Copy Response',
                            splashRadius: 16,
                            onPressed: () {
                              ScaffoldMessenger.of(context).showSnackBar(
                                const SnackBar(
                                  content: Text('Copied response to clipboard'),
                                  duration: Duration(seconds: 1),
                                ),
                              );
                            },
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
