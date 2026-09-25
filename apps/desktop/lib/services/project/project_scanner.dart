import 'dart:io';
import 'package:intl/intl.dart';
import 'package:path/path.dart' as p;

import '../../models/project.dart';
import 'language_detector.dart';

/// ProjectScanner
///
/// Discovers and inspects real project directories on the local filesystem.
/// Excludes heavy build and generated folders from recursive scans.
class ProjectScanner {
  /// Directories to exclude from deep scanning and statistics.
  static const Set<String> ignoredDirectories = {
    '.git',
    'node_modules',
    '.dart_tool',
    'build',
    'dist',
    'target',
    '__pycache__',
    '.venv',
    'venv',
    '.cache',
    '.idea',
    '.vscode',
    '.pytest_cache',
    '.gradle',
    'obj',
    'bin',
    '.next',
    '.turbo',
    'coverage',
  };

  /// Scans a workspace directory and returns discovered projects (direct child directories).
  static List<Project> scanWorkspace(String workspacePath) {
    final workspaceDir = Directory(workspacePath);
    if (!workspaceDir.existsSync()) {
      return [];
    }

    final projects = <Project>[];
    try {
      final children = workspaceDir.listSync(followLinks: false);
      for (final entity in children) {
        if (entity is Directory) {
          final dirName = p.basename(entity.path);
          if (dirName.startsWith('.') || ignoredDirectories.contains(dirName)) {
            continue;
          }
          final project = inspectDirectory(entity, relativeTo: workspacePath);
          if (project != null) {
            projects.add(project);
          }
        }
      }
    } catch (e) {
      // Permission denied or unreadable workspace
    }

    // Sort alphabetically by project name
    projects.sort((a, b) => a.name.toLowerCase().compareTo(b.name.toLowerCase()));
    return projects;
  }

  /// Inspects a single directory and returns full metadata.
  static Project? inspectDirectory(Directory dir, {String? relativeTo}) {
    if (!dir.existsSync()) return null;

    final absolutePath = dir.path;
    final name = p.basename(absolutePath);
    final relativePath = relativeTo != null ? p.relative(absolutePath, from: relativeTo) : name;

    final topLevelFolders = <String>[];
    final topLevelFiles = <String>[];
    final configSnippets = <String, String>{};

    try {
      final topEntries = dir.listSync(followLinks: false);
      for (final entry in topEntries) {
        final entryName = p.basename(entry.path);
        if (entry is Directory) {
          if (!entryName.startsWith('.') && !ignoredDirectories.contains(entryName)) {
            topLevelFolders.add(entryName);
          }
        } else if (entry is File) {
          topLevelFiles.add(entryName);
          // Read small preview of marker config files
          final lower = entryName.toLowerCase();
          if (lower == 'pubspec.yaml' || lower == 'package.json' || lower == 'requirements.txt' || lower == 'pyproject.toml') {
            try {
              final content = entry.readAsStringSync();
              configSnippets[lower] = content.length > 4000 ? content.substring(0, 4000) : content;
            } catch (_) {}
          }
        }
      }
    } catch (_) {
      // Unreadable folder
    }

    // Count files, folders and sample file extensions (bounded depth)
    final sampledFiles = <String>[];
    int totalFiles = 0;
    int totalFolders = 0;

    _walkDirectory(
      dir,
      currentDepth: 1,
      maxDepth: 4,
      onFile: (file) {
        totalFiles++;
        if (sampledFiles.length < 500) {
          sampledFiles.add(p.basename(file.path));
        }
      },
      onDirectory: (d) {
        totalFolders++;
      },
    );

    // Detect languages and frameworks
    final detectedLanguages = LanguageDetector.detectLanguages([
      ...topLevelFiles,
      ...sampledFiles,
    ]);

    final projectType = LanguageDetector.detectProjectType(
      topLevelFiles: topLevelFiles,
      detectedLanguages: detectedLanguages,
      fileSnippets: configSnippets,
    );

    final frameworks = LanguageDetector.detectFrameworks(
      topLevelFiles: topLevelFiles,
      fileSnippets: configSnippets,
    );

    // Git Status
    final gitStatus = _detectGitStatus(dir);

    // Last modified
    String lastModified = '';
    try {
      final stat = dir.statSync();
      lastModified = _formatRelativeDate(stat.modified);
    } catch (_) {}

    return Project(
      id: absolutePath,
      name: name,
      rootPath: absolutePath,
      relativePath: relativePath,
      exists: true,
      isDirectory: true,
      fileCount: totalFiles,
      folderCount: totalFolders,
      detectedLanguages: detectedLanguages,
      topLevelFolders: topLevelFolders,
      gitStatus: gitStatus,
      lastModified: lastModified,
      projectType: projectType,
      frameworks: frameworks,
    );
  }

  static void _walkDirectory(
    Directory dir, {
    required int currentDepth,
    required int maxDepth,
    required void Function(File) onFile,
    required void Function(Directory) onDirectory,
  }) {
    if (currentDepth > maxDepth) return;

    try {
      final entries = dir.listSync(followLinks: false);
      for (final entry in entries) {
        final name = p.basename(entry.path);
        if (entry is Directory) {
          if (name.startsWith('.') || ignoredDirectories.contains(name)) {
            continue;
          }
          onDirectory(entry);
          _walkDirectory(
            entry,
            currentDepth: currentDepth + 1,
            maxDepth: maxDepth,
            onFile: onFile,
            onDirectory: onDirectory,
          );
        } else if (entry is File) {
          onFile(entry);
        }
      }
    } catch (_) {}
  }

  static String _detectGitStatus(Directory projectDir) {
    try {
      final gitDir = Directory(p.join(projectDir.path, '.git'));
      if (!gitDir.existsSync()) {
        return 'Not a Git repository';
      }

      final headFile = File(p.join(gitDir.path, 'HEAD'));
      if (headFile.existsSync()) {
        final headContent = headFile.readAsStringSync().trim();
        if (headContent.startsWith('ref: refs/heads/')) {
          final branch = headContent.replaceFirst('ref: refs/heads/', '');
          return 'Git repository ($branch)';
        }
      }
      return 'Git repository';
    } catch (_) {
      return 'Git repository';
    }
  }

  static String _formatRelativeDate(DateTime dt) {
    final now = DateTime.now();
    final diff = now.difference(dt);

    if (diff.inSeconds < 60) return 'Just now';
    if (diff.inMinutes < 60) return '${diff.inMinutes}m ago';
    if (diff.inHours < 24 && dt.day == now.day) return 'Today at ${DateFormat('HH:mm').format(dt)}';
    if (diff.inHours < 48 && dt.day == now.subtract(const Duration(days: 1)).day) {
      return 'Yesterday';
    }
    if (diff.inDays < 30) return '${diff.inDays}d ago';
    return DateFormat('MMM d, y').format(dt);
  }
}
