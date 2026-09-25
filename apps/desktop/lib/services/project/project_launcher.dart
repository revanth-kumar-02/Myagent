import 'dart:convert';
import 'dart:io' show Platform, Process;
import 'package:flutter/foundation.dart' show debugPrint, kIsWeb;
import 'package:http/http.dart' as http;

/// ProjectLauncher
///
/// Safe OS process invoker to launch File Explorer, VS Code, and Terminal.
/// Uses argument lists with zero shell string interpolation.
class ProjectLauncher {
  static const String _backendLaunchUrl = 'http://127.0.0.1:8765/api/projects/fs/launch';

  /// Opens the directory in the OS native file manager.
  static Future<bool> openInFileExplorer(String path) async {
    if (kIsWeb) {
      return _callBackendLauncher(path, 'explorer');
    }

    try {
      if (Platform.isLinux) {
        final res = await Process.run('xdg-open', [path]);
        return res.exitCode == 0;
      } else if (Platform.isWindows) {
        final res = await Process.run('explorer.exe', [path]);
        return res.exitCode == 0;
      } else if (Platform.isMacOS) {
        final res = await Process.run('open', [path]);
        return res.exitCode == 0;
      }
    } catch (e) {
      debugPrint('[ProjectLauncher] Error opening file explorer: $e');
    }
    return false;
  }

  /// Opens the directory in Visual Studio Code.
  static Future<bool> openInVSCode(String path) async {
    if (kIsWeb) {
      return _callBackendLauncher(path, 'vscode');
    }

    try {
      final res = await Process.run('code', [path]);
      return res.exitCode == 0;
    } catch (e) {
      debugPrint('[ProjectLauncher] Error opening VS Code: $e');
    }
    return false;
  }

  /// Opens terminal in the directory.
  static Future<bool> openTerminal(String path) async {
    if (kIsWeb) {
      return _callBackendLauncher(path, 'terminal');
    }

    try {
      if (Platform.isLinux) {
        // Try standard desktop terminal emulators
        try {
          await Process.run('x-terminal-emulator', ['--working-directory=$path']);
          return true;
        } catch (_) {
          await Process.run('gnome-terminal', ['--working-directory=$path']);
          return true;
        }
      } else if (Platform.isMacOS) {
        await Process.run('open', ['-a', 'Terminal', path]);
        return true;
      } else if (Platform.isWindows) {
        await Process.run('cmd', ['/c', 'start', 'cmd', '/k', 'cd /d "$path"']);
        return true;
      }
    } catch (e) {
      debugPrint('[ProjectLauncher] Error opening terminal: $e');
    }
    return false;
  }

  static Future<bool> _callBackendLauncher(String path, String action) async {
    try {
      final res = await http.post(
        Uri.parse(_backendLaunchUrl),
        headers: {'Content-Type': 'application/json'},
        body: jsonEncode({'target_path': path, 'action': action}),
      );
      return res.statusCode == 200;
    } catch (e) {
      debugPrint('[ProjectLauncher] Web backend launcher error: $e');
      return false;
    }
  }
}
