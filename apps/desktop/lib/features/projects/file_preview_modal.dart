import 'dart:io' show File;
import 'package:flutter/foundation.dart' show kIsWeb;
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:path/path.dart' as p;

import '../../core/theme/app_theme.dart';
import '../../models/project_file_data.dart';
import '../../services/project/file_type_detector.dart';
import '../../services/project/project_launcher.dart';
import '../../services/project/project_service.dart';
import '../../services/project/syntax_highlighter.dart';
import '../../state/projects_state.dart';

/// Modal dialog for inspecting and previewing real filesystem files.
class FilePreviewModal extends ConsumerStatefulWidget {
  final String projectPath;
  final ProjectTreeEntry entry;

  const FilePreviewModal({
    super.key,
    required this.projectPath,
    required this.entry,
  });

  /// Opens the modal dialog over the current screen.
  static Future<void> show(BuildContext context, {required String projectPath, required ProjectTreeEntry entry}) {
    return showDialog<void>(
      context: context,
      barrierDismissible: true,
      barrierColor: Colors.black.withValues(alpha: 0.5),
      builder: (ctx) => FilePreviewModal(projectPath: projectPath, entry: entry),
    );
  }

  @override
  ConsumerState<FilePreviewModal> createState() => _FilePreviewModalState();
}

class _FilePreviewModalState extends ConsumerState<FilePreviewModal> {
  ProjectFileData? _fileData;
  bool _isLoading = true;
  String? _errorMessage;
  int? _imageWidth;
  int? _imageHeight;

  @override
  void initState() {
    super.initState();
    _loadFile();
  }

  Future<void> _loadFile() async {
    setState(() {
      _isLoading = true;
      _errorMessage = null;
    });

    try {
      final data = await ref.read(projectsProvider.notifier).readFile(
        projectPath: widget.projectPath,
        relativePath: widget.entry.relativePath,
      );

      if (mounted) {
        setState(() {
          _fileData = data;
          _isLoading = false;
        });

        if (data.category == FileCategory.image) {
          _resolveImageDimensions(data);
        }
      }
    } catch (e) {
      if (mounted) {
        setState(() {
          _errorMessage = e.toString().replaceFirst('Exception: ', '');
          _isLoading = false;
        });
      }
    }
  }

  void _resolveImageDimensions(ProjectFileData data) {
    try {
      ImageProvider provider;
      if (!kIsWeb && File(data.absolutePath).existsSync()) {
        provider = FileImage(File(data.absolutePath));
      } else if (data.rawContentUrl != null && data.rawContentUrl!.isNotEmpty) {
        provider = NetworkImage(data.rawContentUrl!);
      } else {
        return;
      }

      final config = ImageConfiguration.empty;
      final stream = provider.resolve(config);
      stream.addListener(
        ImageStreamListener((info, _) {
          if (mounted) {
            setState(() {
              _imageWidth = info.image.width;
              _imageHeight = info.image.height;
            });
          }
        }),
      );
    } catch (_) {}
  }

  String _formatBytes(int bytes) {
    if (bytes <= 0) return '0 B';
    if (bytes < 1024) return '$bytes B';
    if (bytes < 1024 * 1024) return '${(bytes / 1024).toStringAsFixed(1)} KB';
    return '${(bytes / (1024 * 1024)).toStringAsFixed(1)} MB';
  }

  void _copyPath(BuildContext context) {
    final path = _fileData?.absolutePath ?? p.join(widget.projectPath, widget.entry.relativePath);
    Clipboard.setData(ClipboardData(text: path));
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text('Copied path: $path'),
        duration: const Duration(seconds: 2),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final c = AppTheme.colors(context);
    final isDark = Theme.of(context).brightness == Brightness.dark;
    final typeInfo = FileTypeDetector.detect(widget.entry.name);
    final size = MediaQuery.of(context).size;
    final dialogWidth = (size.width * 0.88).clamp(600.0, 1020.0);
    final dialogHeight = (size.height * 0.88).clamp(450.0, 820.0);

    return Dialog(
      backgroundColor: Colors.transparent,
      insetPadding: const EdgeInsets.all(24),
      child: Focus(
        autofocus: true,
        onKeyEvent: (node, event) {
          if (event is KeyDownEvent && event.logicalKey == LogicalKeyboardKey.escape) {
            Navigator.of(context).pop();
            return KeyEventResult.handled;
          }
          return KeyEventResult.ignored;
        },
        child: Container(
          width: dialogWidth,
          height: dialogHeight,
          decoration: BoxDecoration(
            color: c.surface,
            borderRadius: BorderRadius.circular(14),
            border: Border.all(color: c.border, width: 1),
            boxShadow: [
              BoxShadow(
                color: Colors.black.withValues(alpha: 0.2),
                blurRadius: 24,
                offset: const Offset(0, 8),
              ),
            ],
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              // ── Header ──────────────────────────────────────────────────────────
              _buildHeader(context, c, typeInfo),
              const Divider(height: 1),

              // ── Content ─────────────────────────────────────────────────────────
              Expanded(
                child: _isLoading
                    ? _buildLoading(c)
                    : _errorMessage != null
                        ? _buildError(c)
                        : _buildPreviewBody(context, c, isDark, typeInfo),
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildHeader(BuildContext context, KoraColors c, FileTypeInfo typeInfo) {
    final filename = widget.entry.name;
    final relativePath = _fileData?.relativePath ?? widget.entry.relativePath;
    final absolutePath = _fileData?.absolutePath ?? p.join(widget.projectPath, widget.entry.relativePath);

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 18, vertical: 12),
      decoration: BoxDecoration(
        color: c.surface,
        borderRadius: const BorderRadius.vertical(top: Radius.circular(14)),
      ),
      child: Row(
        children: [
          Container(
            width: 36,
            height: 36,
            decoration: BoxDecoration(
              color: c.primaryLight,
              borderRadius: BorderRadius.circular(8),
            ),
            child: Icon(typeInfo.icon, size: 19, color: c.primary),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              mainAxisSize: MainAxisSize.min,
              children: [
                Text(
                  filename,
                  style: TextStyle(
                    fontSize: 15,
                    fontWeight: FontWeight.w700,
                    color: c.textPrimary,
                  ),
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                ),
                const SizedBox(height: 2),
                Text(
                  relativePath,
                  style: TextStyle(fontSize: 11.5, color: c.textMuted),
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                ),
              ],
            ),
          ),
          const SizedBox(width: 12),

          // Actions in header
          OutlinedButton.icon(
            icon: const Icon(Icons.copy_rounded, size: 13),
            label: const Text('Copy Path'),
            style: OutlinedButton.styleFrom(
              foregroundColor: c.textPrimary,
              side: BorderSide(color: c.border),
              padding: const EdgeInsets.symmetric(horizontal: 11, vertical: 7),
              visualDensity: VisualDensity.compact,
              shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(6)),
            ),
            onPressed: () => _copyPath(context),
          ),
          const SizedBox(width: 8),

          OutlinedButton.icon(
            icon: const Icon(Icons.code_rounded, size: 14),
            label: const Text('Open in VS Code'),
            style: OutlinedButton.styleFrom(
              foregroundColor: c.textPrimary,
              side: BorderSide(color: c.border),
              padding: const EdgeInsets.symmetric(horizontal: 11, vertical: 7),
              visualDensity: VisualDensity.compact,
              shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(6)),
            ),
            onPressed: () => ProjectLauncher.openInVSCode(absolutePath),
          ),
          const SizedBox(width: 8),

          IconButton(
            icon: const Icon(Icons.close_rounded, size: 20),
            color: c.textSecondary,
            tooltip: 'Close (Esc)',
            onPressed: () => Navigator.of(context).pop(),
          ),
        ],
      ),
    );
  }

  Widget _buildLoading(KoraColors c) {
    return Center(
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          CircularProgressIndicator(color: c.primary, strokeWidth: 2),
          const SizedBox(height: 14),
          Text(
            'Reading file from disk...',
            style: TextStyle(fontSize: 13, color: c.textSecondary),
          ),
        ],
      ),
    );
  }

  Widget _buildError(KoraColors c) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(Icons.error_outline_rounded, size: 36, color: c.error),
            const SizedBox(height: 12),
            Text(
              'Failed to read file',
              style: TextStyle(fontSize: 16, fontWeight: FontWeight.w700, color: c.textPrimary),
            ),
            const SizedBox(height: 6),
            Text(
              _errorMessage ?? 'Unknown error occurred',
              style: TextStyle(fontSize: 13, color: c.textSecondary),
              textAlign: TextAlign.center,
            ),
            const SizedBox(height: 18),
            ElevatedButton(
              style: ElevatedButton.styleFrom(
                backgroundColor: c.primary,
                foregroundColor: Colors.white,
              ),
              onPressed: _loadFile,
              child: const Text('Retry'),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildPreviewBody(BuildContext context, KoraColors c, bool isDark, FileTypeInfo typeInfo) {
    final data = _fileData!;
    return switch (data.category) {
      FileCategory.text => _buildTextCodePreview(c, isDark, typeInfo, data),
      FileCategory.image => _buildImagePreview(context, c, typeInfo, data),
      FileCategory.pdf => _buildPdfPreview(context, c, data),
      FileCategory.binary => _buildBinaryPreview(context, c, typeInfo, data),
    };
  }

  // ── 1. Text & Code Preview ─────────────────────────────────────────────────
  Widget _buildTextCodePreview(KoraColors c, bool isDark, FileTypeInfo typeInfo, ProjectFileData data) {
    final content = data.content ?? '';
    final lines = content.split('\n');
    final totalLines = lines.length;
    final gutterWidth = (totalLines.toString().length * 10.0 + 24.0).clamp(42.0, 72.0);

    return Column(
      children: [
        // Code viewport
        Expanded(
          child: Container(
            color: isDark ? const Color(0xFF1E222A) : const Color(0xFFFBFBF9),
            child: SingleChildScrollView(
              scrollDirection: Axis.horizontal,
              child: SizedBox(
                width: 1400,
                child: ListView.builder(
                  padding: const EdgeInsets.symmetric(vertical: 8),
                  itemCount: totalLines,
                  itemBuilder: (context, index) {
                    final line = lines[index];
                    return Container(
                      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 1.5),
                      child: Row(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          // Line number gutter
                          SizedBox(
                            width: gutterWidth,
                            child: Text(
                              '${index + 1}',
                              textAlign: TextAlign.right,
                              style: TextStyle(
                                color: c.textMuted.withValues(alpha: 0.65),
                                fontFamily: 'monospace',
                                fontSize: 12,
                                height: 1.45,
                              ),
                            ),
                          ),
                          const SizedBox(width: 16),

                          // Highlighted code line
                          Expanded(
                            child: SelectableText.rich(
                              SyntaxHighlighter.highlightLine(
                                line,
                                c,
                                language: typeInfo.language,
                                isDark: isDark,
                              ),
                              style: TextStyle(
                                fontFamily: 'monospace',
                                fontSize: 12.5,
                                height: 1.45,
                                color: c.textPrimary,
                              ),
                            ),
                          ),
                        ],
                      ),
                    );
                  },
                ),
              ),
            ),
          ),
        ),

        // Bottom status bar
        Container(
          padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
          decoration: BoxDecoration(
            color: c.surface,
            border: Border(top: BorderSide(color: c.border)),
          ),
          child: Row(
            children: [
              Text(
                typeInfo.language,
                style: TextStyle(fontSize: 11.5, fontWeight: FontWeight.w600, color: c.textSecondary),
              ),
              const SizedBox(width: 14),
              Text(
                '$totalLines lines',
                style: TextStyle(fontSize: 11.5, color: c.textMuted),
              ),
              const SizedBox(width: 14),
              Text(
                _formatBytes(data.sizeBytes),
                style: TextStyle(fontSize: 11.5, color: c.textMuted),
              ),
              if (data.truncated) ...[
                const SizedBox(width: 14),
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                  decoration: BoxDecoration(
                    color: c.warningLight,
                    borderRadius: BorderRadius.circular(4),
                  ),
                  child: Text(
                    'Preview truncated to 2 MB',
                    style: TextStyle(fontSize: 10.5, fontWeight: FontWeight.w600, color: c.warning),
                  ),
                ),
              ],
              const Spacer(),
              Text(
                'UTF-8',
                style: TextStyle(fontSize: 11, color: c.textMuted),
              ),
            ],
          ),
        ),
      ],
    );
  }

  // ── 2. Image Preview ───────────────────────────────────────────────────────
  Widget _buildImagePreview(BuildContext context, KoraColors c, FileTypeInfo typeInfo, ProjectFileData data) {
    Widget imageWidget;
    if (!kIsWeb && File(data.absolutePath).existsSync()) {
      imageWidget = Image.file(
        File(data.absolutePath),
        fit: BoxFit.contain,
        errorBuilder: (_, __, ___) => _buildImageError(c),
      );
    } else if (data.rawContentUrl != null && data.rawContentUrl!.isNotEmpty) {
      imageWidget = Image.network(
        data.rawContentUrl!,
        fit: BoxFit.contain,
        errorBuilder: (_, __, ___) => _buildImageError(c),
      );
    } else {
      imageWidget = _buildImageError(c);
    }

    final dimStr = (_imageWidth != null && _imageHeight != null)
        ? ' • ${_imageWidth} × ${_imageHeight} px'
        : '';

    return Column(
      children: [
        Expanded(
          child: Container(
            color: Theme.of(context).brightness == Brightness.dark
                ? const Color(0xFF181A1F)
                : const Color(0xFFF4F4F1),
            alignment: Alignment.center,
            padding: const EdgeInsets.all(24),
            child: InteractiveViewer(
              maxScale: 4.0,
              minScale: 0.5,
              child: imageWidget,
            ),
          ),
        ),

        // Image details footer
        Container(
          padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 12),
          decoration: BoxDecoration(
            color: c.surface,
            border: Border(top: BorderSide(color: c.border)),
          ),
          child: Row(
            children: [
              Text(
                '${typeInfo.language.toUpperCase()}$dimStr • ${_formatBytes(data.sizeBytes)}',
                style: TextStyle(fontSize: 12, fontWeight: FontWeight.w600, color: c.textSecondary),
              ),
              const Spacer(),
              ElevatedButton.icon(
                icon: const Icon(Icons.folder_open_rounded, size: 14),
                label: const Text('Open in File Explorer'),
                style: ElevatedButton.styleFrom(
                  backgroundColor: c.primary,
                  foregroundColor: Colors.white,
                  padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 9),
                  shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(6)),
                ),
                onPressed: () => ProjectLauncher.openInFileExplorer(p.dirname(data.absolutePath)),
              ),
            ],
          ),
        ),
      ],
    );
  }

  Widget _buildImageError(KoraColors c) {
    return Column(
      mainAxisSize: MainAxisSize.min,
      children: [
        Icon(Icons.broken_image_rounded, size: 48, color: c.textMuted),
        const SizedBox(height: 10),
        Text('Unable to render image preview', style: TextStyle(color: c.textSecondary)),
      ],
    );
  }

  // ── 3. PDF Preview ─────────────────────────────────────────────────────────
  Widget _buildPdfPreview(BuildContext context, KoraColors c, ProjectFileData data) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(32),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Container(
              width: 72,
              height: 72,
              decoration: BoxDecoration(
                color: const Color(0xFFFEE2E2),
                borderRadius: BorderRadius.circular(16),
              ),
              child: const Icon(Icons.picture_as_pdf_rounded, size: 38, color: Color(0xFFDC2626)),
            ),
            const SizedBox(height: 16),
            Text(
              data.name,
              style: TextStyle(fontSize: 18, fontWeight: FontWeight.w700, color: c.textPrimary),
            ),
            const SizedBox(height: 6),
            Text(
              'PDF Document • ${_formatBytes(data.sizeBytes)}',
              style: TextStyle(fontSize: 13, color: c.textSecondary),
            ),
            const SizedBox(height: 12),
            Text(
              'PDF documents can be opened with your system\'s default viewer or editor.',
              style: TextStyle(fontSize: 12, color: c.textMuted),
            ),
            const SizedBox(height: 24),
            Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                ElevatedButton.icon(
                  icon: const Icon(Icons.folder_open_rounded, size: 15),
                  label: const Text('Open in File Explorer'),
                  style: ElevatedButton.styleFrom(
                    backgroundColor: c.primary,
                    foregroundColor: Colors.white,
                    padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
                    shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
                  ),
                  onPressed: () => ProjectLauncher.openInFileExplorer(p.dirname(data.absolutePath)),
                ),
                const SizedBox(width: 12),
                OutlinedButton(
                  style: OutlinedButton.styleFrom(
                    foregroundColor: c.textPrimary,
                    side: BorderSide(color: c.border),
                    padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
                    shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
                  ),
                  child: const Text('Close'),
                  onPressed: () => Navigator.of(context).pop(),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }

  // ── 4. Binary / Unsupported Preview ────────────────────────────────────────
  Widget _buildBinaryPreview(BuildContext context, KoraColors c, FileTypeInfo typeInfo, ProjectFileData data) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(32),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Container(
              width: 72,
              height: 72,
              decoration: BoxDecoration(
                color: c.surfaceHighlight,
                borderRadius: BorderRadius.circular(16),
              ),
              child: Icon(Icons.inventory_2_outlined, size: 36, color: c.textSecondary),
            ),
            const SizedBox(height: 16),
            Text(
              'File Preview Unavailable',
              style: TextStyle(fontSize: 18, fontWeight: FontWeight.w700, color: c.textPrimary),
            ),
            const SizedBox(height: 6),
            Text(
              '${data.name} (${typeInfo.language}) • ${_formatBytes(data.sizeBytes)}',
              style: TextStyle(fontSize: 13, color: c.textSecondary),
            ),
            const SizedBox(height: 8),
            Text(
              'This binary or unsupported file cannot be displayed as plain text.',
              style: TextStyle(fontSize: 12, color: c.textMuted),
            ),
            const SizedBox(height: 24),
            Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                ElevatedButton.icon(
                  icon: const Icon(Icons.folder_open_rounded, size: 15),
                  label: const Text('Open in File Explorer'),
                  style: ElevatedButton.styleFrom(
                    backgroundColor: c.primary,
                    foregroundColor: Colors.white,
                    padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
                    shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
                  ),
                  onPressed: () => ProjectLauncher.openInFileExplorer(p.dirname(data.absolutePath)),
                ),
                const SizedBox(width: 10),
                OutlinedButton.icon(
                  icon: const Icon(Icons.copy_rounded, size: 14),
                  label: const Text('Copy Path'),
                  style: OutlinedButton.styleFrom(
                    foregroundColor: c.textPrimary,
                    side: BorderSide(color: c.border),
                    padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
                    shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
                  ),
                  onPressed: () => _copyPath(context),
                ),
                const SizedBox(width: 10),
                OutlinedButton(
                  style: OutlinedButton.styleFrom(
                    foregroundColor: c.textPrimary,
                    side: BorderSide(color: c.border),
                    padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
                    shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
                  ),
                  child: const Text('Close'),
                  onPressed: () => Navigator.of(context).pop(),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }
}
