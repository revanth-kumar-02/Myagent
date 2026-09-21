import 'package:flutter/foundation.dart' show kIsWeb;
import 'package:path/path.dart' as p;
import 'package:path_provider/path_provider.dart';
import 'dart:io' show Platform;

/// PlatformAbstraction
///
/// Single interface for all OS-specific capabilities.
/// All platform-specific code is routed through this class.
/// No widget or feature code calls Platform.* directly.
abstract class PlatformAbstraction {
  /// Path to application data directory (for SQLite, settings, etc.)
  Future<String> get appDataDir;

  /// Path to user documents directory
  Future<String> get documentsDir;

  /// Open a native file picker and return selected paths
  Future<List<String>> pickFiles({bool allowMultiple = false});

  /// Open a native directory picker and return selected path
  Future<String?> pickDirectory();

  /// Show a desktop notification
  Future<void> showNotification({required String title, required String body});

  /// Factory constructor: returns the correct platform implementation
  factory PlatformAbstraction() {
    if (kIsWeb) return WebPlatform();
    if (Platform.isWindows) return WindowsPlatform();
    if (Platform.isMacOS)   return MacOSPlatform();
    if (Platform.isLinux)   return LinuxPlatform();
    throw UnsupportedError('Platform not supported');
  }
}

/// Web implementation fallback
class WebPlatform implements PlatformAbstraction {
  @override
  Future<String> get appDataDir async => '/';

  @override
  Future<String> get documentsDir async => '/';

  @override
  Future<List<String>> pickFiles({bool allowMultiple = false}) async => [];

  @override
  Future<String?> pickDirectory() async => null;

  @override
  Future<void> showNotification({required String title, required String body}) async {}
}


/// Linux implementation
class LinuxPlatform implements PlatformAbstraction {
  @override
  Future<String> get appDataDir async {
    final dir = await getApplicationSupportDirectory();
    return dir.path;
  }

  @override
  Future<String> get documentsDir async {
    final dir = await getApplicationDocumentsDirectory();
    return dir.path;
  }

  @override
  Future<List<String>> pickFiles({bool allowMultiple = false}) async {
    throw UnimplementedError(); // TODO: file_picker in feature phase
  }

  @override
  Future<String?> pickDirectory() async {
    throw UnimplementedError(); // TODO: file_picker in feature phase
  }

  @override
  Future<void> showNotification({required String title, required String body}) async {
    throw UnimplementedError(); // TODO: local_notifier in feature phase
  }
}

/// Windows implementation
class WindowsPlatform extends LinuxPlatform {}

/// macOS implementation
class MacOSPlatform extends LinuxPlatform {}
