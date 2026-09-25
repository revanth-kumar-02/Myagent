/// Language & Framework Detector for Kora Projects
///
/// Inspects real files and extensions to determine languages and frameworks.
/// Does not guess based on directory name alone.

class LanguageDetector {
  static const Map<String, String> _extensionMap = {
    // Python
    'py': 'Python',
    'pyw': 'Python',
    'ipynb': 'Python (Jupyter)',
    // Dart / Flutter
    'dart': 'Dart',
    // JavaScript / TypeScript
    'ts': 'TypeScript',
    'tsx': 'TypeScript (React)',
    'js': 'JavaScript',
    'jsx': 'JavaScript (React)',
    'mjs': 'JavaScript',
    'cjs': 'JavaScript',
    // Systems & Native
    'rs': 'Rust',
    'go': 'Go',
    'c': 'C',
    'h': 'C/C++ Header',
    'cpp': 'C++',
    'hpp': 'C++',
    'cc': 'C++',
    'cxx': 'C++',
    'swift': 'Swift',
    // JVM
    'java': 'Java',
    'kt': 'Kotlin',
    'kts': 'Kotlin',
    'scala': 'Scala',
    // Data & Web
    'sql': 'SQL',
    'html': 'HTML',
    'htm': 'HTML',
    'css': 'CSS',
    'scss': 'SCSS',
    'sass': 'SASS',
    'less': 'LESS',
    // Scripting
    'sh': 'Shell',
    'bash': 'Bash',
    'zsh': 'Zsh',
    'rb': 'Ruby',
    'php': 'PHP',
  };

  /// Detects unique programming languages from a list of relative or base file paths.
  static List<String> detectLanguages(Iterable<String> filePaths) {
    final languageCounts = <String, int>{};

    for (final path in filePaths) {
      final dotIdx = path.lastIndexOf('.');
      if (dotIdx == -1 || dotIdx == path.length - 1) continue;

      final ext = path.substring(dotIdx + 1).toLowerCase();
      final lang = _extensionMap[ext];
      if (lang != null) {
        languageCounts[lang] = (languageCounts[lang] ?? 0) + 1;
      }
    }

    // Sort by prevalence descending
    final sorted = languageCounts.keys.toList()
      ..sort((a, b) => (languageCounts[b] ?? 0).compareTo(languageCounts[a] ?? 0));

    return sorted;
  }

  /// Detects frameworks and project types from files and configuration files.
  static String detectProjectType({
    required List<String> topLevelFiles,
    required List<String> detectedLanguages,
    Map<String, String> fileSnippets = const {},
  }) {
    final fileSet = topLevelFiles.map((f) => f.toLowerCase()).toSet();

    // Flutter / Dart
    if (fileSet.contains('pubspec.yaml')) {
      final pubspec = fileSnippets['pubspec.yaml'] ?? '';
      if (pubspec.contains('flutter:')) {
        return 'Flutter Application';
      }
      return 'Dart Package';
    }

    // Node / Web / JavaScript / TypeScript
    if (fileSet.contains('package.json')) {
      final pkg = fileSnippets['package.json'] ?? '';
      if (pkg.contains('"next"')) return 'Next.js Project';
      if (pkg.contains('"react"')) return 'React Application';
      if (pkg.contains('"vue"')) return 'Vue.js Application';
      if (pkg.contains('"express"')) return 'Express.js Backend';
      if (fileSet.contains('tsconfig.json')) return 'TypeScript / Node.js';
      return 'Node.js Project';
    }

    // Rust
    if (fileSet.contains('cargo.toml')) {
      return 'Rust / Cargo Project';
    }

    // Go
    if (fileSet.contains('go.mod')) {
      return 'Go Module';
    }

    // Python
    if (fileSet.contains('pyproject.toml') || fileSet.contains('requirements.txt') || fileSet.contains('setup.py')) {
      final reqs = (fileSnippets['requirements.txt'] ?? '') + (fileSnippets['pyproject.toml'] ?? '');
      if (reqs.contains('fastapi')) return 'FastAPI / Python';
      if (reqs.contains('django')) return 'Django / Python';
      if (reqs.contains('flask')) return 'Flask / Python';
      return 'Python Project';
    }

    // Java / Kotlin / Gradle / Maven
    if (fileSet.contains('pom.xml')) return 'Maven / Java Project';
    if (fileSet.contains('build.gradle') || fileSet.contains('build.gradle.kts')) {
      if (detectedLanguages.contains('Kotlin')) return 'Gradle / Kotlin Project';
      return 'Gradle / Java Project';
    }

    // C / C++
    if (fileSet.contains('cmakelists.txt')) return 'CMake / C++ Project';
    if (fileSet.contains('makefile')) return 'C / C++ Project';

    // Primary language fallback
    if (detectedLanguages.isNotEmpty) {
      return '${detectedLanguages.first} Project';
    }

    return 'Generic Project';
  }

  /// Detects specific frameworks
  static List<String> detectFrameworks({
    required List<String> topLevelFiles,
    Map<String, String> fileSnippets = const {},
  }) {
    final frameworks = <String>{};
    final fileSet = topLevelFiles.map((f) => f.toLowerCase()).toSet();

    if (fileSet.contains('pubspec.yaml')) {
      final content = fileSnippets['pubspec.yaml'] ?? '';
      if (content.contains('flutter:')) frameworks.add('Flutter');
      if (content.contains('riverpod')) frameworks.add('Riverpod');
    }

    if (fileSet.contains('package.json')) {
      final content = fileSnippets['package.json'] ?? '';
      if (content.contains('"next"')) frameworks.add('Next.js');
      if (content.contains('"react"')) frameworks.add('React');
      if (content.contains('"vue"')) frameworks.add('Vue');
      if (content.contains('"tailwind"')) frameworks.add('TailwindCSS');
      if (content.contains('"vite"')) frameworks.add('Vite');
      if (content.contains('"express"')) frameworks.add('Express');
    }

    if (fileSet.contains('requirements.txt') || fileSet.contains('pyproject.toml')) {
      final content = (fileSnippets['requirements.txt'] ?? '') + (fileSnippets['pyproject.toml'] ?? '');
      if (content.contains('fastapi')) frameworks.add('FastAPI');
      if (content.contains('uvicorn')) frameworks.add('Uvicorn');
      if (content.contains('django')) frameworks.add('Django');
      if (content.contains('flask')) frameworks.add('Flask');
      if (content.contains('torch')) frameworks.add('PyTorch');
      if (content.contains('tensorflow')) frameworks.add('TensorFlow');
    }

    return frameworks.toList();
  }
}
