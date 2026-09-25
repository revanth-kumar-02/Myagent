import 'dart:async';
import 'dart:convert';
import 'dart:io';
import 'package:flutter/foundation.dart';
import 'package:http/http.dart' as http;

enum LocalRuntimeState {
  stopped,
  starting,
  running,
  failed,
}

/// LocalRuntimeManager
///
/// Supervises the local Kora backend process on desktop platforms.
///
/// Responsibilities:
///   - Detect existing local backend on port 8765
///   - Start local Python FastAPI backend automatically when needed
///   - Health check with polling
///   - Cleanly terminate backend process on application close
///   - Prevent duplicate instances
class LocalRuntimeManager {
  static final LocalRuntimeManager instance = LocalRuntimeManager._internal();
  LocalRuntimeManager._internal();

  Process? _process;
  LocalRuntimeState _state = LocalRuntimeState.stopped;
  final _stateController = StreamController<LocalRuntimeState>.broadcast();

  LocalRuntimeState get state => _state;
  Stream<LocalRuntimeState> get stateStream => _stateController.stream;
  bool get isRunning => _state == LocalRuntimeState.running;

  void _setState(LocalRuntimeState s) {
    if (_state != s) {
      _state = s;
      debugPrint('[LocalRuntimeManager] State changed to: $s');
      if (!_stateController.isClosed) {
        _stateController.add(s);
      }
    }
  }

  /// Check if local runtime HTTP endpoint is responding to health checks.
  Future<bool> probeHealth({String baseUrl = 'http://127.0.0.1:8765', Duration timeout = const Duration(seconds: 2)}) async {
    try {
      final res = await http.get(Uri.parse('$baseUrl/api/health')).timeout(timeout);
      return res.statusCode == 200;
    } catch (_) {
      return false;
    }
  }

  /// Check if Ollama daemon is reachable.
  Future<bool> probeOllama({String baseUrl = 'http://127.0.0.1:11434', Duration timeout = const Duration(seconds: 2)}) async {
    try {
      final res = await http.get(Uri.parse('$baseUrl/api/tags')).timeout(timeout);
      return res.statusCode == 200;
    } catch (_) {
      return false;
    }
  }

  /// Ensure local runtime is running. If not already up, launch it.
  Future<bool> ensureStarted({String baseUrl = 'http://127.0.0.1:8765'}) async {
    if (kIsWeb) return false;
    if (Platform.environment.containsKey('FLUTTER_TEST')) return false;

    // 1. Probe if already running
    final alreadyHealthy = await probeHealth(baseUrl: baseUrl);
    if (alreadyHealthy) {
      _setState(LocalRuntimeState.running);
      return true;
    }

    if (_state == LocalRuntimeState.starting) {
      // Already starting, wait for completion
      for (int i = 0; i < 20; i++) {
        await Future.delayed(const Duration(milliseconds: 500));
        if (_state == LocalRuntimeState.running) return true;
        if (_state == LocalRuntimeState.failed) return false;
      }
    }

    _setState(LocalRuntimeState.starting);

    // 2. Discover Python and agent main.py path
    final agentDir = _findAgentDirectory();
    final pythonExe = _findPythonExecutable(agentDir);

    if (agentDir == null || pythonExe == null) {
      debugPrint('[LocalRuntimeManager] Cannot locate Python agent directory or executable');
      _setState(LocalRuntimeState.failed);
      return false;
    }

    try {
      debugPrint('[LocalRuntimeManager] Launching backend: $pythonExe main.py in $agentDir');
      _process = await Process.start(
        pythonExe,
        ['main.py'],
        workingDirectory: agentDir,
        environment: {
          ...Platform.environment,
          'PYTHONPATH': '.',
          'KORA_HOST': '127.0.0.1',
          'KORA_PORT': '8765',
        },
        mode: ProcessStartMode.normal,
      );

      _process!.stdout.transform(utf8.decoder).listen((line) {
        debugPrint('[LocalBackend] $line');
      });
      _process!.stderr.transform(utf8.decoder).listen((line) {
        debugPrint('[LocalBackend ERR] $line');
      });

      _process!.exitCode.then((code) async {
        debugPrint('[LocalRuntimeManager] Backend process exited with code $code');
        _process = null;
        final healthy = await probeHealth(baseUrl: baseUrl);
        if (healthy) {
          debugPrint('[LocalRuntimeManager] Existing backend active on port, keeping running state');
          _setState(LocalRuntimeState.running);
        } else if (_state != LocalRuntimeState.stopped) {
          _setState(LocalRuntimeState.stopped);
        }
      });

      // 3. Poll health until ready (up to 15 seconds)
      for (int i = 0; i < 30; i++) {
        await Future.delayed(const Duration(milliseconds: 500));
        if (await probeHealth(baseUrl: baseUrl)) {
          debugPrint('[LocalRuntimeManager] Local backend is healthy and ready!');
          _setState(LocalRuntimeState.running);
          return true;
        }
      }

      debugPrint('[LocalRuntimeManager] Backend startup timed out');
      _setState(LocalRuntimeState.failed);
      return false;
    } catch (e) {
      debugPrint('[LocalRuntimeManager] Failed to launch local backend process: $e');
      _setState(LocalRuntimeState.failed);
      return false;
    }
  }

  /// Stop local process cleanly on shutdown.
  Future<void> stop() async {
    if (_process != null) {
      debugPrint('[LocalRuntimeManager] Terminating local backend process...');
      try {
        _process!.kill(ProcessSignal.sigterm);
      } catch (_) {
        _process!.kill();
      }
      _process = null;
    }
    _setState(LocalRuntimeState.stopped);
  }

  String? _findAgentDirectory() {
    final candidates = [
      Directory.current.path,
      '${Directory.current.path}/apps/agent',
      '${Directory.current.parent.path}/agent',
      '${Directory.current.path}/../agent',
      '/home/rev/My_Personal_Space/Projects/Unfinished/Myagent/apps/agent',
    ];

    for (final c in candidates) {
      final f = File('$c/main.py');
      if (f.existsSync()) return Directory(c).absolute.path;
    }
    return null;
  }

  String? _findPythonExecutable(String? agentDir) {
    if (agentDir != null) {
      final venvPython = File('$agentDir/.venv/bin/python');
      if (venvPython.existsSync()) return venvPython.path;
    }

    final envVenv = Platform.environment['VIRTUAL_ENV'];
    if (envVenv != null) {
      final p = File('$envVenv/bin/python');
      if (p.existsSync()) return p.path;
    }

    for (final bin in ['python3', 'python', '/usr/bin/python3']) {
      final f = File(bin);
      if (f.existsSync()) return bin;
    }
    return 'python3';
  }

  void dispose() {
    stop();
    _stateController.close();
  }
}
