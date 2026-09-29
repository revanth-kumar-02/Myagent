import 'dart:async';
import 'package:file_picker/file_picker.dart';
import 'package:flutter/material.dart';
import 'package:flutter_markdown/flutter_markdown.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/theme/app_theme.dart';
import '../../models/vision_models.dart';
import '../../state/chat_state.dart';
import '../../state/vision_state.dart';

/// VisionScreen — Vision Workspace
///
/// A native Kora workspace for image analysis, screen capture, OCR,
/// visual Q&A, and injecting visual context into the agent chat.
///
/// Architecture:
///   VisionScreen → visionProvider (VisionNotifier) → VisionApiService
///   → POST /api/vision/analyze  (upload)
///   → POST /api/vision/capture  (server screen capture)
///   → POST /api/vision/ask      (visual Q&A)
///   → POST /api/vision/context  (context → chat)
///
/// No mock data. If the backend cannot provide a real result the UI
/// shows an honest error state.
class VisionScreen extends ConsumerStatefulWidget {
  final VoidCallback? onNavigateToChat;

  const VisionScreen({super.key, this.onNavigateToChat});

  @override
  ConsumerState<VisionScreen> createState() => _VisionScreenState();
}

class _VisionScreenState extends ConsumerState<VisionScreen>
    with SingleTickerProviderStateMixin {
  late TabController _tabController;
  final TextEditingController _questionCtrl = TextEditingController();
  bool _showRecentPanel = true;

  @override
  void initState() {
    super.initState();
    _tabController = TabController(length: 3, vsync: this);
    // Load recent analyses when screen opens
    WidgetsBinding.instance.addPostFrameCallback((_) {
      ref.read(visionProvider.notifier).loadRecentAnalyses();
    });
  }

  @override
  void dispose() {
    _tabController.dispose();
    _questionCtrl.dispose();
    super.dispose();
  }

  // ── Actions ─────────────────────────────────────────────────────────────────

  Future<void> _pickAndAnalyze() async {
    final result = await FilePicker.platform.pickFiles(
      type: FileType.image,
      allowMultiple: false,
    );
    if (result == null || result.files.isEmpty) return;
    final path = result.files.first.path;
    if (path == null) return;
    await ref.read(visionProvider.notifier).analyzeFile(path);
  }

  Future<void> _captureScreen() async {
    await ref.read(visionProvider.notifier).captureScreen();
  }

  Future<void> _askQuestion() async {
    final q = _questionCtrl.text.trim();
    if (q.isEmpty) return;
    await ref.read(visionProvider.notifier).askQuestion(q);
    _questionCtrl.clear();
  }

  Future<void> _sendToChat() async {
    final notifier = ref.read(visionProvider.notifier);
    final ctx = await notifier.buildContext();
    if (ctx == null) return;

    // Inject into chat via the chat state notifier
    final chatNotifier = ref.read(chatProvider.notifier);
    chatNotifier.sendVisionContext(ctx.contextString);
    notifier.markContextSentToChat();

    if (mounted) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('Visual context sent to Kora Chat'),
          duration: Duration(seconds: 2),
        ),
      );
      // Navigate to chat if callback provided
      widget.onNavigateToChat?.call();
    }
  }

  // ── Build ────────────────────────────────────────────────────────────────────

  @override
  Widget build(BuildContext context) {
    final c = AppTheme.colors(context);
    final vision = ref.watch(visionProvider);

    return Row(
      children: [
        // ── Main Panel ────────────────────────────────────────────────────────
        Expanded(
          child: Column(
            children: [
              // Toolbar
              _buildToolbar(c, vision),
              // Capability banner (shown when model not available)
              if (vision.capabilities != null && !vision.canAnalyze)
                _buildCapabilityBanner(c, vision.capabilities!),
              // Tab bar
              Container(
                color: c.surface,
                child: TabBar(
                  controller: _tabController,
                  labelColor: c.primary,
                  unselectedLabelColor: c.textSecondary,
                  indicatorColor: c.primary,
                  indicatorSize: TabBarIndicatorSize.label,
                  tabs: const [
                    Tab(icon: Icon(Icons.image_search_rounded, size: 18), text: 'Analyze'),
                    Tab(icon: Icon(Icons.question_answer_rounded, size: 18), text: 'Ask Kora'),
                    Tab(icon: Icon(Icons.text_fields_rounded, size: 18), text: 'OCR & Elements'),
                  ],
                ),
              ),
              // Tab body
              Expanded(
                child: TabBarView(
                  controller: _tabController,
                  children: [
                    _AnalyzeTab(
                      vision: vision,
                      onPickFile: _pickAndAnalyze,
                      onCapture: _captureScreen,
                      onSendToChat: _sendToChat,
                    ),
                    _AskTab(
                      vision: vision,
                      questionCtrl: _questionCtrl,
                      onAsk: _askQuestion,
                    ),
                    _OcrElementsTab(vision: vision),
                  ],
                ),
              ),
            ],
          ),
        ),

        // ── Recent Results Panel ───────────────────────────────────────────────
        if (_showRecentPanel)
          _RecentPanel(
            c: c,
            recentItems: vision.recentItems,
            currentAnalysisId: vision.currentAnalysis?.analysisId,
            onClose: () => setState(() => _showRecentPanel = false),
          ),
      ],
    );
  }

  Widget _buildToolbar(KoraColors c, VisionState vision) {
    return Container(
      height: 52,
      padding: const EdgeInsets.symmetric(horizontal: 16),
      decoration: BoxDecoration(
        color: c.surface,
        border: Border(bottom: BorderSide(color: c.border)),
      ),
      child: Row(
        children: [
          // Upload image button
          _ToolbarButton(
            icon: Icons.upload_file_rounded,
            label: 'Upload Image',
            enabled: !vision.isWorking,
            onTap: _pickAndAnalyze,
            c: c,
          ),
          const SizedBox(width: 8),
          // Paste from clipboard — shown as a shortcut hint
          _ToolbarButton(
            icon: Icons.content_paste_rounded,
            label: 'Paste Image',
            enabled: !vision.isWorking,
            onTap: _pasteFromClipboard,
            c: c,
          ),
          const SizedBox(width: 8),
          // Screen capture
          _ToolbarButton(
            icon: Icons.screenshot_monitor_rounded,
            label: 'Capture Screen',
            enabled: !vision.isWorking && (vision.canCapture || vision.capabilities == null),
            onTap: _captureScreen,
            c: c,
          ),
          const Spacer(),
          // Send to chat (only when analysis exists)
          if (vision.hasResult)
            _ToolbarButton(
              icon: Icons.send_to_mobile_rounded,
              label: 'Send to Chat',
              enabled: !vision.isWorking,
              onTap: _sendToChat,
              c: c,
              primary: true,
            ),
          const SizedBox(width: 8),
          if (vision.hasResult)
            IconButton(
              icon: Icon(Icons.clear_rounded, size: 18, color: c.textSecondary),
              tooltip: 'Clear',
              onPressed: () => ref.read(visionProvider.notifier).clearAnalysis(),
            ),
          // Recent panel toggle
          IconButton(
            icon: Icon(Icons.history_rounded, size: 18, color: c.textSecondary),
            tooltip: _showRecentPanel ? 'Hide Recent' : 'Show Recent',
            onPressed: () => setState(() => _showRecentPanel = !_showRecentPanel),
          ),
        ],
      ),
    );
  }

  Future<void> _pasteFromClipboard() async {
    // Note: Flutter desktop clipboard image support is limited.
    // We show a message explaining the limitation honestly.
    if (!mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(
      const SnackBar(
        content: Text(
          'Clipboard image paste is not yet supported on desktop. '
          'Use "Upload Image" to pick a file instead.',
        ),
        duration: Duration(seconds: 3),
      ),
    );
  }

  Widget _buildCapabilityBanner(KoraColors c, VisionCapabilities caps) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
      color: Colors.orange.withValues(alpha: 0.12),
      child: Row(
        children: [
          Icon(Icons.warning_amber_rounded, size: 16, color: Colors.orange.shade700),
          const SizedBox(width: 8),
          Expanded(
            child: Text(
              'Vision model not available — ${caps.visionModels.isEmpty ? "no vision model registered" : "model provider offline"}. '
              'Image analysis requires the gemma-vision model to be reachable.',
              style: TextStyle(fontSize: 12, color: Colors.orange.shade900),
            ),
          ),
          TextButton(
            onPressed: () => ref.read(visionProvider.notifier).loadCapabilities(),
            child: Text('Retry', style: TextStyle(fontSize: 12, color: Colors.orange.shade900)),
          ),
        ],
      ),
    );
  }
}

// ── Analyze Tab ───────────────────────────────────────────────────────────────

class _AnalyzeTab extends ConsumerWidget {
  final VisionState vision;
  final VoidCallback onPickFile;
  final VoidCallback onCapture;
  final VoidCallback onSendToChat;

  const _AnalyzeTab({
    required this.vision,
    required this.onPickFile,
    required this.onCapture,
    required this.onSendToChat,
  });

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final c = AppTheme.colors(context);

    if (vision.isWorking) {
      return _LoadingState(
        c: c,
        message: switch (vision.phase) {
          VisionPhase.analyzing => 'Analyzing image with ${_modelName(vision)}…',
          VisionPhase.capturing => 'Capturing screen…',
          VisionPhase.loadingCapabilities => 'Connecting to vision backend…',
          _ => 'Working…',
        },
      );
    }

    if (vision.phase == VisionPhase.error) {
      return _ErrorState(c: c, message: vision.errorMessage ?? 'Unknown error');
    }

    if (!vision.hasResult) {
      return _EmptyState(c: c, onPickFile: onPickFile, onCapture: onCapture);
    }

    final analysis = vision.currentAnalysis!;
    return _ResultView(c: c, analysis: analysis, onSendToChat: onSendToChat);
  }

  String _modelName(VisionState v) =>
      v.capabilities?.visionModels.firstOrNull?['name'] as String? ?? 'vision model';
}

// ── Ask Tab ───────────────────────────────────────────────────────────────────

class _AskTab extends StatelessWidget {
  final VisionState vision;
  final TextEditingController questionCtrl;
  final VoidCallback onAsk;

  const _AskTab({
    required this.vision,
    required this.questionCtrl,
    required this.onAsk,
  });

  @override
  Widget build(BuildContext context) {
    final c = AppTheme.colors(context);

    if (!vision.hasResult) {
      return Center(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(Icons.image_not_supported_rounded, size: 40, color: c.textMuted),
            const SizedBox(height: 12),
            Text('Analyze an image first', style: TextStyle(color: c.textMuted, fontSize: 14)),
          ],
        ),
      );
    }

    return Padding(
      padding: const EdgeInsets.all(20),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            'Ask Kora a question about this image',
            style: TextStyle(
              fontWeight: FontWeight.w600,
              fontSize: 14,
              color: c.textPrimary,
            ),
          ),
          const SizedBox(height: 6),
          Text(
            'The vision model will answer based on the analyzed image content.',
            style: TextStyle(fontSize: 12, color: c.textSecondary),
          ),
          const SizedBox(height: 16),
          Row(
            children: [
              Expanded(
                child: TextField(
                  controller: questionCtrl,
                  enabled: !vision.isWorking,
                  decoration: InputDecoration(
                    hintText: 'e.g. "What buttons are visible?" or "What text is on the screen?"',
                    hintStyle: TextStyle(color: c.textMuted, fontSize: 13),
                    border: OutlineInputBorder(
                      borderRadius: BorderRadius.circular(8),
                      borderSide: BorderSide(color: c.border),
                    ),
                    contentPadding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
                  ),
                  onSubmitted: (_) => onAsk(),
                  style: TextStyle(color: c.textPrimary, fontSize: 13),
                ),
              ),
              const SizedBox(width: 8),
              ElevatedButton.icon(
                onPressed: vision.isWorking ? null : onAsk,
                icon: vision.phase == VisionPhase.asking
                    ? const SizedBox(
                        width: 14,
                        height: 14,
                        child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white),
                      )
                    : const Icon(Icons.send_rounded, size: 16),
                label: const Text('Ask'),
                style: ElevatedButton.styleFrom(
                  backgroundColor: c.primary,
                  foregroundColor: Colors.white,
                  padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
                  shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
                ),
              ),
            ],
          ),
          if (vision.lastAnswer != null) ...[
            const SizedBox(height: 20),
            Container(
              padding: const EdgeInsets.all(14),
              decoration: BoxDecoration(
                color: c.surfaceHighlight,
                borderRadius: BorderRadius.circular(10),
                border: Border.all(color: c.border),
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  if (vision.lastAnswerQuestion != null)
                    Row(
                      children: [
                        Icon(Icons.person_outline_rounded, size: 14, color: c.textSecondary),
                        const SizedBox(width: 6),
                        Expanded(
                          child: Text(
                            vision.lastAnswerQuestion!,
                            style: TextStyle(
                              fontSize: 12,
                              color: c.textSecondary,
                              fontStyle: FontStyle.italic,
                            ),
                          ),
                        ),
                      ],
                    ),
                  const SizedBox(height: 8),
                  Row(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Icon(Icons.smart_toy_rounded, size: 14, color: c.primary),
                      const SizedBox(width: 6),
                      Expanded(
                        child: MarkdownBody(
                          data: vision.lastAnswer!,
                          styleSheet: MarkdownStyleSheet(
                            p: TextStyle(fontSize: 13, color: c.textPrimary),
                          ),
                        ),
                      ),
                    ],
                  ),
                ],
              ),
            ),
          ],
        ],
      ),
    );
  }
}

// ── OCR & Elements Tab ────────────────────────────────────────────────────────

class _OcrElementsTab extends StatelessWidget {
  final VisionState vision;

  const _OcrElementsTab({required this.vision});

  @override
  Widget build(BuildContext context) {
    final c = AppTheme.colors(context);

    if (!vision.hasResult) {
      return Center(
        child: Text('Analyze an image first', style: TextStyle(color: c.textMuted, fontSize: 14)),
      );
    }

    final analysis = vision.currentAnalysis!;

    return SingleChildScrollView(
      padding: const EdgeInsets.all(20),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // OCR Text Section
          _SectionHeader(icon: Icons.text_fields_rounded, title: 'Extracted Text (OCR)', c: c),
          const SizedBox(height: 8),
          if (analysis.detectedText.isEmpty)
            _EmptySection(c: c, message: 'No text detected in this image')
          else
            Container(
              width: double.infinity,
              padding: const EdgeInsets.all(12),
              decoration: BoxDecoration(
                color: c.surfaceHighlight,
                borderRadius: BorderRadius.circular(8),
                border: Border.all(color: c.border),
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: analysis.detectedText
                    .map((t) => Padding(
                          padding: const EdgeInsets.symmetric(vertical: 2),
                          child: Row(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Icon(Icons.text_snippet_outlined,
                                  size: 12, color: c.textMuted),
                              const SizedBox(width: 6),
                              Expanded(
                                child: SelectableText(
                                  t,
                                  style: TextStyle(
                                    fontSize: 12,
                                    color: c.textPrimary,
                                    fontFamily: 'monospace',
                                  ),
                                ),
                              ),
                            ],
                          ),
                        ))
                    .toList(),
              ),
            ),

          const SizedBox(height: 24),

          // Detected UI Elements
          _SectionHeader(
            icon: Icons.widgets_rounded,
            title: 'Detected UI Elements (${analysis.detectedElements.length})',
            c: c,
          ),
          const SizedBox(height: 8),
          if (analysis.detectedElements.isEmpty)
            _EmptySection(c: c, message: 'No UI elements detected')
          else
            ...analysis.detectedElements.map((el) => _ElementCard(el: el, c: c)),
        ],
      ),
    );
  }
}

// ── Sub-widgets ───────────────────────────────────────────────────────────────

class _EmptyState extends StatelessWidget {
  final KoraColors c;
  final VoidCallback onPickFile;
  final VoidCallback onCapture;

  const _EmptyState({required this.c, required this.onPickFile, required this.onCapture});

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          Container(
            width: 80,
            height: 80,
            decoration: BoxDecoration(
              color: c.primaryLight,
              shape: BoxShape.circle,
            ),
            child: Icon(Icons.visibility_rounded, size: 36, color: c.primary),
          ),
          const SizedBox(height: 20),
          Text(
            'Vision Workspace',
            style: TextStyle(
              fontSize: 20,
              fontWeight: FontWeight.w700,
              color: c.textPrimary,
            ),
          ),
          const SizedBox(height: 8),
          Text(
            'Analyze images, capture your screen, extract text,\nand ask Kora questions about what it sees.',
            textAlign: TextAlign.center,
            style: TextStyle(fontSize: 13, color: c.textSecondary, height: 1.5),
          ),
          const SizedBox(height: 28),
          Wrap(
            spacing: 12,
            children: [
              _ActionChip(
                icon: Icons.upload_file_rounded,
                label: 'Upload Image',
                onTap: onPickFile,
                c: c,
                primary: true,
              ),
              _ActionChip(
                icon: Icons.screenshot_monitor_rounded,
                label: 'Capture Screen',
                onTap: onCapture,
                c: c,
              ),
            ],
          ),
        ],
      ),
    );
  }
}

class _LoadingState extends StatelessWidget {
  final KoraColors c;
  final String message;

  const _LoadingState({required this.c, required this.message});

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          SizedBox(
            width: 40,
            height: 40,
            child: CircularProgressIndicator(
              strokeWidth: 3,
              valueColor: AlwaysStoppedAnimation<Color>(c.primary),
            ),
          ),
          const SizedBox(height: 16),
          Text(message, style: TextStyle(fontSize: 14, color: c.textSecondary)),
        ],
      ),
    );
  }
}

class _ErrorState extends StatelessWidget {
  final KoraColors c;
  final String message;

  const _ErrorState({required this.c, required this.message});

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(Icons.error_outline_rounded, size: 40, color: Colors.red.shade400),
            const SizedBox(height: 12),
            Text(
              'Vision Error',
              style: TextStyle(
                fontSize: 16,
                fontWeight: FontWeight.w600,
                color: c.textPrimary,
              ),
            ),
            const SizedBox(height: 8),
            Text(
              message,
              textAlign: TextAlign.center,
              style: TextStyle(fontSize: 13, color: c.textSecondary),
            ),
          ],
        ),
      ),
    );
  }
}

class _ResultView extends StatelessWidget {
  final KoraColors c;
  final VisionAnalysisResult analysis;
  final VoidCallback onSendToChat;

  const _ResultView({
    required this.c,
    required this.analysis,
    required this.onSendToChat,
  });

  @override
  Widget build(BuildContext context) {
    return Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        // Left: Image preview
        Expanded(
          flex: 5,
          child: Padding(
            padding: const EdgeInsets.all(16),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                _SectionHeader(icon: Icons.image_rounded, title: 'Image', c: c),
                const SizedBox(height: 8),
                Expanded(
                  child: Container(
                    decoration: BoxDecoration(
                      border: Border.all(color: c.border),
                      borderRadius: BorderRadius.circular(10),
                      color: c.surfaceHighlight,
                    ),
                    child: ClipRRect(
                      borderRadius: BorderRadius.circular(9),
                      child: analysis.imageUrl != null
                          ? Image.network(
                              analysis.imageUrl!,
                              fit: BoxFit.contain,
                              loadingBuilder: (_, child, progress) {
                                if (progress == null) return child;
                                return Center(
                                  child: CircularProgressIndicator(
                                    value: progress.expectedTotalBytes != null
                                        ? progress.cumulativeBytesLoaded /
                                            progress.expectedTotalBytes!
                                        : null,
                                    strokeWidth: 2,
                                    color: c.primary,
                                  ),
                                );
                              },
                              errorBuilder: (_, __, ___) => Center(
                                child: Column(
                                  mainAxisSize: MainAxisSize.min,
                                  children: [
                                    Icon(Icons.broken_image_rounded,
                                        size: 32, color: c.textMuted),
                                    const SizedBox(height: 8),
                                    Text('Preview unavailable',
                                        style: TextStyle(color: c.textMuted, fontSize: 12)),
                                  ],
                                ),
                              ),
                            )
                          : Center(
                              child: Icon(Icons.image_rounded, size: 40, color: c.textMuted),
                            ),
                    ),
                  ),
                ),
              ],
            ),
          ),
        ),

        // Right: Analysis summary
        Expanded(
          flex: 4,
          child: SingleChildScrollView(
            padding: const EdgeInsets.fromLTRB(0, 16, 16, 16),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                _SectionHeader(icon: Icons.insights_rounded, title: 'Analysis', c: c),
                const SizedBox(height: 8),
                _InfoCard(c: c, children: [
                  _InfoRow(
                    label: 'Model',
                    value: analysis.modelUsed.isNotEmpty ? analysis.modelUsed : 'Unknown',
                    c: c,
                  ),
                  _InfoRow(
                    label: 'Confidence',
                    value: '${(analysis.confidence * 100).toStringAsFixed(0)}%',
                    c: c,
                  ),
                  _InfoRow(
                    label: 'Elements',
                    value: '${analysis.detectedElements.length}',
                    c: c,
                  ),
                  _InfoRow(
                    label: 'Text blocks',
                    value: '${analysis.detectedText.length}',
                    c: c,
                  ),
                  if (analysis.activeWindow != null)
                    _InfoRow(label: 'Window', value: analysis.activeWindow!, c: c),
                ]),

                const SizedBox(height: 12),
                _SectionHeader(icon: Icons.summarize_rounded, title: 'Summary', c: c),
                const SizedBox(height: 8),
                Container(
                  padding: const EdgeInsets.all(12),
                  decoration: BoxDecoration(
                    color: c.surfaceHighlight,
                    borderRadius: BorderRadius.circular(8),
                    border: Border.all(color: c.border),
                  ),
                  child: Text(
                    analysis.summary,
                    style: TextStyle(fontSize: 13, color: c.textPrimary, height: 1.5),
                  ),
                ),

                if (analysis.description.isNotEmpty &&
                    analysis.description != analysis.summary) ...[
                  const SizedBox(height: 12),
                  _SectionHeader(
                      icon: Icons.description_rounded, title: 'Description', c: c),
                  const SizedBox(height: 8),
                  Container(
                    padding: const EdgeInsets.all(12),
                    decoration: BoxDecoration(
                      color: c.surfaceHighlight,
                      borderRadius: BorderRadius.circular(8),
                      border: Border.all(color: c.border),
                    ),
                    child: Text(
                      analysis.description,
                      style:
                          TextStyle(fontSize: 12, color: c.textSecondary, height: 1.5),
                    ),
                  ),
                ],

                const SizedBox(height: 16),
                // Send to Chat CTA
                SizedBox(
                  width: double.infinity,
                  child: ElevatedButton.icon(
                    onPressed: onSendToChat,
                    icon: const Icon(Icons.send_to_mobile_rounded, size: 16),
                    label: const Text('Send Visual Context to Chat'),
                    style: ElevatedButton.styleFrom(
                      backgroundColor: c.primary,
                      foregroundColor: Colors.white,
                      padding: const EdgeInsets.symmetric(vertical: 12),
                      shape: RoundedRectangleBorder(
                          borderRadius: BorderRadius.circular(8)),
                    ),
                  ),
                ),
              ],
            ),
          ),
        ),
      ],
    );
  }
}

class _RecentPanel extends StatelessWidget {
  final KoraColors c;
  final List<RecentVisionItem> recentItems;
  final String? currentAnalysisId;
  final VoidCallback onClose;

  const _RecentPanel({
    required this.c,
    required this.recentItems,
    required this.currentAnalysisId,
    required this.onClose,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      width: 220,
      decoration: BoxDecoration(
        border: Border(left: BorderSide(color: c.border)),
        color: c.bg,
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Container(
            height: 44,
            padding: const EdgeInsets.symmetric(horizontal: 12),
            decoration: BoxDecoration(
              border: Border(bottom: BorderSide(color: c.border)),
            ),
            child: Row(
              children: [
                Icon(Icons.history_rounded, size: 15, color: c.textSecondary),
                const SizedBox(width: 6),
                Text(
                  'Recent',
                  style: TextStyle(
                    fontSize: 12,
                    fontWeight: FontWeight.w600,
                    color: c.textSecondary,
                  ),
                ),
                const Spacer(),
                IconButton(
                  icon: Icon(Icons.close_rounded, size: 14, color: c.textMuted),
                  onPressed: onClose,
                  padding: EdgeInsets.zero,
                  constraints: const BoxConstraints(),
                ),
              ],
            ),
          ),
          Expanded(
            child: recentItems.isEmpty
                ? Center(
                    child: Text(
                      'No recent analyses',
                      style: TextStyle(fontSize: 11, color: c.textMuted),
                    ),
                  )
                : ListView.builder(
                    padding: const EdgeInsets.symmetric(vertical: 4),
                    itemCount: recentItems.length,
                    itemBuilder: (ctx, i) {
                      final item = recentItems[i];
                      final isActive = item.analysisId == currentAnalysisId;
                      return Consumer(builder: (ctx, ref, _) {
                        return InkWell(
                          onTap: () async {
                            // Load the full analysis from backend and set as current
                            try {
                              final full = await ref
                                  .read(visionServiceProvider)
                                  .getAnalysis(item.analysisId);
                              ref.read(visionProvider.notifier).loadStoredAnalysis(full);
                            } catch (_) {}
                          },
                          child: Container(
                            padding: const EdgeInsets.symmetric(
                                horizontal: 12, vertical: 8),
                            decoration: BoxDecoration(
                              color: isActive ? c.primaryLight : null,
                              border: Border(
                                  left: BorderSide(
                                color: isActive ? c.primary : Colors.transparent,
                                width: 2,
                              )),
                            ),
                            child: Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                Text(
                                  item.summary.isEmpty
                                      ? 'Analysis ${item.analysisId.substring(0, 8)}'
                                      : item.summary,
                                  maxLines: 2,
                                  overflow: TextOverflow.ellipsis,
                                  style: TextStyle(
                                    fontSize: 11,
                                    color: isActive ? c.primaryDark : c.textPrimary,
                                    fontWeight: isActive
                                        ? FontWeight.w600
                                        : FontWeight.w400,
                                  ),
                                ),
                                const SizedBox(height: 2),
                                Text(
                                  '${item.elementCount} elements • '
                                  '${item.ocrTextCount} text blocks',
                                  style: TextStyle(
                                      fontSize: 10, color: c.textMuted),
                                ),
                              ],
                            ),
                          ),
                        );
                      });
                    },
                  ),
          ),
        ],
      ),
    );
  }
}

// ── Micro-widgets ─────────────────────────────────────────────────────────────

class _ToolbarButton extends StatelessWidget {
  final IconData icon;
  final String label;
  final bool enabled;
  final VoidCallback onTap;
  final KoraColors c;
  final bool primary;

  const _ToolbarButton({
    required this.icon,
    required this.label,
    required this.enabled,
    required this.onTap,
    required this.c,
    this.primary = false,
  });

  @override
  Widget build(BuildContext context) {
    return Material(
      color: primary ? c.primary : c.surfaceHighlight,
      borderRadius: BorderRadius.circular(7),
      child: InkWell(
        onTap: enabled ? onTap : null,
        borderRadius: BorderRadius.circular(7),
        child: Container(
          padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
          child: Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              Icon(icon,
                  size: 14,
                  color: !enabled
                      ? c.textMuted
                      : primary
                          ? Colors.white
                          : c.textSecondary),
              const SizedBox(width: 5),
              Text(
                label,
                style: TextStyle(
                  fontSize: 12,
                  fontWeight: FontWeight.w500,
                  color: !enabled
                      ? c.textMuted
                      : primary
                          ? Colors.white
                          : c.textSecondary,
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _ActionChip extends StatelessWidget {
  final IconData icon;
  final String label;
  final VoidCallback onTap;
  final KoraColors c;
  final bool primary;

  const _ActionChip({
    required this.icon,
    required this.label,
    required this.onTap,
    required this.c,
    this.primary = false,
  });

  @override
  Widget build(BuildContext context) {
    return ElevatedButton.icon(
      onPressed: onTap,
      icon: Icon(icon, size: 16),
      label: Text(label),
      style: ElevatedButton.styleFrom(
        backgroundColor: primary ? c.primary : c.surface,
        foregroundColor: primary ? Colors.white : c.textSecondary,
        elevation: 0,
        side: BorderSide(color: primary ? Colors.transparent : c.border),
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
      ),
    );
  }
}

class _SectionHeader extends StatelessWidget {
  final IconData icon;
  final String title;
  final KoraColors c;

  const _SectionHeader({required this.icon, required this.title, required this.c});

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        Icon(icon, size: 14, color: c.primary),
        const SizedBox(width: 6),
        Text(
          title,
          style: TextStyle(
            fontSize: 12,
            fontWeight: FontWeight.w700,
            color: c.textSecondary,
            letterSpacing: 0.3,
          ),
        ),
      ],
    );
  }
}

class _InfoCard extends StatelessWidget {
  final KoraColors c;
  final List<Widget> children;

  const _InfoCard({required this.c, required this.children});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: c.surfaceHighlight,
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: c.border),
      ),
      child: Column(children: children),
    );
  }
}

class _InfoRow extends StatelessWidget {
  final String label;
  final String value;
  final KoraColors c;

  const _InfoRow({required this.label, required this.value, required this.c});

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 2),
      child: Row(
        children: [
          SizedBox(
            width: 72,
            child: Text(
              label,
              style: TextStyle(fontSize: 11, color: c.textMuted),
            ),
          ),
          Expanded(
            child: Text(
              value,
              style: TextStyle(
                fontSize: 11,
                color: c.textPrimary,
                fontWeight: FontWeight.w500,
              ),
              overflow: TextOverflow.ellipsis,
            ),
          ),
        ],
      ),
    );
  }
}

class _ElementCard extends StatelessWidget {
  final DetectedElement el;
  final KoraColors c;

  const _ElementCard({required this.el, required this.c});

  @override
  Widget build(BuildContext context) {
    final typeColors = {
      'button': Colors.blue,
      'input_field': Colors.green,
      'text': Colors.grey,
      'menu': Colors.purple,
      'link': Colors.cyan,
      'dialog': Colors.orange,
      'icon': Colors.amber,
      'checkbox': Colors.teal,
      'table': Colors.indigo,
      'window': Colors.brown,
    };
    final typeColor = typeColors[el.elementType] ?? Colors.grey;

    return Container(
      margin: const EdgeInsets.only(bottom: 6),
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
      decoration: BoxDecoration(
        color: c.surfaceHighlight,
        borderRadius: BorderRadius.circular(7),
        border: Border.all(color: c.border),
      ),
      child: Row(
        children: [
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
            decoration: BoxDecoration(
              color: typeColor.withValues(alpha: 0.12),
              borderRadius: BorderRadius.circular(4),
              border: Border.all(color: typeColor.withValues(alpha: 0.3)),
            ),
            child: Text(
              el.elementType.toUpperCase(),
              style: TextStyle(
                fontSize: 9,
                fontWeight: FontWeight.w700,
                color: typeColor,
                letterSpacing: 0.5,
              ),
            ),
          ),
          const SizedBox(width: 8),
          Expanded(
            child: Text(
              el.label,
              style: TextStyle(fontSize: 12, color: c.textPrimary),
              overflow: TextOverflow.ellipsis,
            ),
          ),
          Text(
            '${(el.confidence * 100).toStringAsFixed(0)}%',
            style: TextStyle(fontSize: 11, color: c.textMuted),
          ),
        ],
      ),
    );
  }
}

class _EmptySection extends StatelessWidget {
  final KoraColors c;
  final String message;

  const _EmptySection({required this.c, required this.message});

  @override
  Widget build(BuildContext context) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.symmetric(vertical: 12, horizontal: 12),
      decoration: BoxDecoration(
        color: c.surfaceHighlight,
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: c.border),
      ),
      child: Text(message, style: TextStyle(fontSize: 12, color: c.textMuted)),
    );
  }
}
