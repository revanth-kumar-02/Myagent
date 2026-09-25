import 'dart:convert';
import 'dart:io';
import 'package:file_picker/file_picker.dart';
import 'package:flutter/foundation.dart' show debugPrint, kIsWeb;
import 'package:http/http.dart' as http;
import 'package:path/path.dart' as p;
import 'package:shared_preferences/shared_preferences.dart';

import '../../models/project.dart';
import '../../models/project_file_data.dart';
import 'file_type_detector.dart';
import 'project_scanner.dart';

/// ProjectTreeEntry
class ProjectTreeEntry {
  final String name;
  final String relativePath;
  final String absolutePath;
  final bool isDirectory;
  final int sizeBytes;

  const ProjectTreeEntry({
    required this.name,
    required this.relativePath,
    required this.absolutePath,
    required this.isDirectory,
    this.sizeBytes = 0,
  });

  factory ProjectTreeEntry.fromJson(Map<String, dynamic> json) {
    return ProjectTreeEntry(
      name: json['name'] as String? ?? '',
      relativePath: json['relative_path'] as String? ?? '',
      absolutePath: json['absolute_path'] as String? ?? '',
      isDirectory: json['is_directory'] as bool? ?? false,
      sizeBytes: json['size_bytes'] as int? ?? 0,
    );
  }

  Map<String, dynamic> toJson() => {
    'name': name,
    'relative_path': relativePath,
    'absolute_path': absolutePath,
    'is_directory': isDirectory,
    'size_bytes': sizeBytes,
  };
}

/// ProjectService
///
/// Coordinates workspace selection, filesystem discovery, project creation,
/// and detail tree generation.
class ProjectService {
  static const String _prefKeyWorkspace = 'kora_projects_workspace_path';
  static const String _backendFsUrl = 'http://127.0.0.1:8765/api/projects/fs';

  /// Default suggestion workspace path for quick selection
  static const String defaultWorkspaceSuggestion = '/home/rev/My_Personal_Space/Projects/Unfinished';

  /// Loads the persisted workspace path.
  Future<String?> getPersistedWorkspace() async {
    try {
      final prefs = await SharedPreferences.getInstance();
      final path = prefs.getString(_prefKeyWorkspace);
      if (path != null && path.trim().isNotEmpty) {
        return path.trim();
      }
    } catch (e) {
      debugPrint('[ProjectService] Failed to load workspace pref: $e');
    }
    return null;
  }

  /// Persists the selected workspace path.
  Future<void> saveWorkspace(String path) async {
    try {
      final prefs = await SharedPreferences.getInstance();
      await prefs.setString(_prefKeyWorkspace, path.trim());
    } catch (e) {
      debugPrint('[ProjectService] Failed to save workspace pref: $e');
    }
  }

  /// Opens the native OS directory picker.
  Future<String?> pickDirectory({String? initialDirectory}) async {
    if (!kIsWeb) {
      try {
        final selected = await FilePicker.platform.getDirectoryPath(
          dialogTitle: 'Select Projects Workspace Directory',
          initialDirectory: initialDirectory,
        );
        if (selected != null && selected.trim().isNotEmpty) {
          final clean = selected.trim();
          await saveWorkspace(clean);
          return clean;
        }
      } catch (e) {
        debugPrint('[ProjectService] Native picker error: $e');
      }
    }
    return null;
  }

  /// Scans projects inside a workspace directory.
  Future<List<Project>> scanProjects(String workspacePath) async {
    final cleanPath = workspacePath.trim();
    if (cleanPath.isEmpty) return [];

    // Native desktop scanning (offline-first, no backend needed)
    if (!kIsWeb) {
      final dir = Directory(cleanPath);
      if (!dir.existsSync()) {
        throw Exception('Workspace directory does not exist: $cleanPath');
      }
      return ProjectScanner.scanWorkspace(cleanPath);
    }

    // Web runtime: Bridge to local backend filesystem endpoint
    try {
      final uri = Uri.parse('$_backendFsUrl/scan').replace(
        queryParameters: {'workspace_path': cleanPath},
      );
      final res = await http.get(uri);
      if (res.statusCode == 200) {
        final data = jsonDecode(res.body) as Map<String, dynamic>;
        final list = data['projects'] as List<dynamic>? ?? [];
        return list.map((item) => Project.fromJson(item as Map<String, dynamic>)).toList();
      } else {
        throw Exception('Backend filesystem scan returned HTTP ${res.statusCode}: ${res.body}');
      }
    } catch (e) {
      debugPrint('[ProjectService] Web backend scan failed: $e');
      // If backend is unavailable on web, check if we can still try native fallback or report
      rethrow;
    }
  }

  /// Creates a real new project directory on the filesystem.
  Future<Project> createProject({
    required String workspacePath,
    required String name,
    String? template,
  }) async {
    final cleanName = name.trim();
    if (cleanName.isEmpty) {
      throw Exception('Project name cannot be empty');
    }

    // Safety checks against path traversal
    if (cleanName.contains('/') ||
        cleanName.contains('\\') ||
        cleanName.contains('..') ||
        cleanName.contains('\x00')) {
      throw Exception('Invalid project name: path traversal characters are forbidden');
    }

    if (!kIsWeb) {
      final parentDir = Directory(workspacePath);
      if (!parentDir.existsSync()) {
        throw Exception('Workspace directory does not exist: $workspacePath');
      }

      final targetPath = p.join(workspacePath, cleanName);
      final targetDir = Directory(targetPath);
      if (targetDir.existsSync()) {
        throw Exception('A directory named "$cleanName" already exists in $workspacePath');
      }

      // Physically create folder
      targetDir.createSync(recursive: true);

      // Create starter README.md
      final readme = File(p.join(targetPath, 'README.md'));
      readme.writeAsStringSync('# $cleanName\n\nCreated with Kora Workspace.\n');

      final inspected = ProjectScanner.inspectDirectory(targetDir, relativeTo: workspacePath);
      if (inspected != null) return inspected;

      return Project(
        id: targetPath,
        name: cleanName,
        rootPath: targetPath,
        relativePath: cleanName,
        exists: true,
        isDirectory: true,
        topLevelFolders: [],
        detectedLanguages: [],
        gitStatus: 'Not a Git repository',
        projectType: template ?? 'Generic Project',
        lastModified: 'Just now',
      );
    }

    // Web runtime: call backend create
    final res = await http.post(
      Uri.parse('$_backendFsUrl/create'),
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode({
        'workspace_path': workspacePath,
        'name': cleanName,
        'template': template,
      }),
    );

    if (res.statusCode == 200) {
      final data = jsonDecode(res.body) as Map<String, dynamic>;
      return Project.fromJson(data);
    } else {
      final err = jsonDecode(res.body)['detail'] ?? 'Failed to create project';
      throw Exception(err.toString());
    }
  }

  /// Fetches real folder tree for a project (shallow/lazy).
  Future<List<ProjectTreeEntry>> getProjectTree(String projectPath, {String subPath = ''}) async {
    final targetPath = subPath.isEmpty ? projectPath : p.join(projectPath, subPath);

    if (!kIsWeb) {
      final dir = Directory(targetPath);
      if (!dir.existsSync()) return [];

      final entries = <ProjectTreeEntry>[];
      try {
        final list = dir.listSync(followLinks: false);
        for (final item in list) {
          final baseName = p.basename(item.path);
          if (baseName.startsWith('.') || ProjectScanner.ignoredDirectories.contains(baseName)) {
            continue;
          }
          final isDir = item is Directory;
          int size = 0;
          if (!isDir && item is File) {
            try {
              size = item.lengthSync();
            } catch (_) {}
          }
          entries.add(ProjectTreeEntry(
            name: baseName,
            relativePath: p.relative(item.path, from: projectPath),
            absolutePath: item.path,
            isDirectory: isDir,
            sizeBytes: size,
          ));
        }
      } catch (_) {}

      // Folders first, then files alphabetically
      entries.sort((a, b) {
        if (a.isDirectory && !b.isDirectory) return -1;
        if (!a.isDirectory && b.isDirectory) return 1;
        return a.name.toLowerCase().compareTo(b.name.toLowerCase());
      });
      return entries;
    }

    // Web runtime: call backend tree endpoint
    try {
      final uri = Uri.parse('$_backendFsUrl/tree').replace(
        queryParameters: {
          'project_path': projectPath,
          'sub_path': subPath,
        },
      );
      final res = await http.get(uri);
      if (res.statusCode == 200) {
        final data = jsonDecode(res.body) as Map<String, dynamic>;
        final list = data['entries'] as List<dynamic>? ?? [];
        return list.map((item) => ProjectTreeEntry.fromJson(item as Map<String, dynamic>)).toList();
      }
    } catch (_) {}
    return [];
  }

  /// Reads a file from a project directory with strict path traversal security.
  Future<ProjectFileData> readFile({
    required String projectPath,
    required String relativePath,
  }) async {
    final cleanProj = p.canonicalize(projectPath.trim());
    final cleanRel = relativePath.trim().replaceFirst(RegExp(r'^[/\\]+'), '');

    // 1. Native Desktop: direct offline filesystem access
    if (!kIsWeb) {
      final fullPath = p.canonicalize(p.join(cleanProj, cleanRel));

      // Path traversal security check
      if (!fullPath.startsWith(cleanProj + p.separator) && fullPath != cleanProj) {
        throw Exception('Access denied: path traversal detected');
      }

      final file = File(fullPath);
      if (!file.existsSync()) {
        throw Exception('File not found: $cleanRel');
      }

      final size = file.lengthSync();
      final typeInfo = FileTypeDetector.detect(fullPath);

      String? content;
      bool truncated = false;
      int lineCount = 0;

      if (typeInfo.category == FileCategory.text) {
        const maxBytes = 2 * 1024 * 1024; // 2MB preview limit
        try {
          final bytes = file.readAsBytesSync();
          // Null-byte check for disguised binary files
          final checkSlice = bytes.take(1024);
          if (checkSlice.contains(0)) {
            return ProjectFileData(
              name: p.basename(fullPath),
              relativePath: p.relative(fullPath, from: cleanProj),
              absolutePath: fullPath,
              extension: p.extension(fullPath).toLowerCase(),
              category: FileCategory.binary,
              mimeType: 'application/octet-stream',
              sizeBytes: size,
            );
          }

          if (bytes.length > maxBytes) {
            truncated = true;
            content = utf8.decode(bytes.sublist(0, maxBytes), allowMalformed: true);
          } else {
            content = utf8.decode(bytes, allowMalformed: true);
          }
          lineCount = '\n'.allMatches(content).length + 1;
        } catch (e) {
          content = 'Failed to read file: $e';
        }
      }

      return ProjectFileData(
        name: p.basename(fullPath),
        relativePath: p.relative(fullPath, from: cleanProj),
        absolutePath: fullPath,
        extension: p.extension(fullPath).toLowerCase(),
        category: typeInfo.category,
        mimeType: typeInfo.mimeType,
        sizeBytes: size,
        content: content,
        truncated: truncated,
        lineCount: lineCount,
        rawContentUrl: null,
      );
    }

    // 2. Web runtime: call backend filesystem endpoint
    final uri = Uri.parse('$_backendFsUrl/file').replace(
      queryParameters: {
        'project_path': cleanProj,
        'path': cleanRel,
      },
    );

    final res = await http.get(uri);
    if (res.statusCode == 200) {
      final data = jsonDecode(res.body) as Map<String, dynamic>;
      final rawUrl = Uri.parse('$_backendFsUrl/file/raw').replace(
        queryParameters: {
          'project_path': cleanProj,
          'path': cleanRel,
        },
      ).toString();

      return ProjectFileData.fromJson(data, rawContentUrl: rawUrl);
    } else {
      final err = jsonDecode(res.body)['detail'] ?? 'Failed to read file';
      throw Exception(err.toString());
    }
  }
}
