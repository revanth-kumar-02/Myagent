import 'package:flutter/material.dart';
import 'package:path/path.dart' as p;

/// High-level categorization of files for preview and handling.
enum FileCategory {
  text,
  image,
  pdf,
  binary,
}

/// Metadata and presentation details for a detected file type.
class FileTypeInfo {
  final FileCategory category;
  final String language;
  final String mimeType;
  final IconData icon;
  final String extension;
  final bool isCode;

  const FileTypeInfo({
    required this.category,
    required this.language,
    required this.mimeType,
    required this.icon,
    required this.extension,
    this.isCode = false,
  });

  bool get isText => category == FileCategory.text;
  bool get isImage => category == FileCategory.image;
  bool get isPdf => category == FileCategory.pdf;
  bool get isBinary => category == FileCategory.binary;
}

/// Reusable detector for file types, icons, MIME types, and languages.
class FileTypeDetector {
  static const Set<String> _imageExtensions = {
    '.png',
    '.jpg',
    '.jpeg',
    '.webp',
    '.gif',
    '.bmp',
    '.ico',
    '.svg',
  };

  static const Set<String> _pdfExtensions = {
    '.pdf',
  };

  static const Map<String, ({String lang, String mime, IconData icon, bool code})> _knownExtensions = {
    // Dart / Flutter
    '.dart': (lang: 'Dart', mime: 'application/dart', icon: Icons.flutter_dash_rounded, code: true),

    // Python
    '.py': (lang: 'Python', mime: 'text/x-python', icon: Icons.code_rounded, code: true),
    '.pyw': (lang: 'Python', mime: 'text/x-python', icon: Icons.code_rounded, code: true),

    // TypeScript & JavaScript
    '.ts': (lang: 'TypeScript', mime: 'text/typescript', icon: Icons.javascript_rounded, code: true),
    '.tsx': (lang: 'TypeScript (React)', mime: 'text/typescript-jsx', icon: Icons.javascript_rounded, code: true),
    '.js': (lang: 'JavaScript', mime: 'text/javascript', icon: Icons.javascript_rounded, code: true),
    '.jsx': (lang: 'JavaScript (React)', mime: 'text/javascript-jsx', icon: Icons.javascript_rounded, code: true),
    '.mjs': (lang: 'JavaScript Module', mime: 'text/javascript', icon: Icons.javascript_rounded, code: true),
    '.cjs': (lang: 'CommonJS', mime: 'text/javascript', icon: Icons.javascript_rounded, code: true),

    // Rust
    '.rs': (lang: 'Rust', mime: 'text/rust', icon: Icons.build_circle_outlined, code: true),

    // JVM (Java / Kotlin / Scala / Groovy)
    '.java': (lang: 'Java', mime: 'text/x-java-source', icon: Icons.coffee_rounded, code: true),
    '.kt': (lang: 'Kotlin', mime: 'text/x-kotlin', icon: Icons.code_rounded, code: true),
    '.kts': (lang: 'Kotlin Script', mime: 'text/x-kotlin', icon: Icons.code_rounded, code: true),
    '.gradle': (lang: 'Gradle', mime: 'text/x-groovy', icon: Icons.settings_applications_rounded, code: true),

    // C / C++ / Objective-C
    '.c': (lang: 'C', mime: 'text/x-c', icon: Icons.code_rounded, code: true),
    '.h': (lang: 'C/C++ Header', mime: 'text/x-c', icon: Icons.code_rounded, code: true),
    '.cpp': (lang: 'C++', mime: 'text/x-c++', icon: Icons.code_rounded, code: true),
    '.cc': (lang: 'C++', mime: 'text/x-c++', icon: Icons.code_rounded, code: true),
    '.cxx': (lang: 'C++', mime: 'text/x-c++', icon: Icons.code_rounded, code: true),
    '.hpp': (lang: 'C++ Header', mime: 'text/x-c++', icon: Icons.code_rounded, code: true),

    // Go
    '.go': (lang: 'Go', mime: 'text/x-go', icon: Icons.code_rounded, code: true),

    // Swift
    '.swift': (lang: 'Swift', mime: 'text/x-swift', icon: Icons.code_rounded, code: true),

    // Web & Styles
    '.html': (lang: 'HTML', mime: 'text/html', icon: Icons.html_rounded, code: true),
    '.htm': (lang: 'HTML', mime: 'text/html', icon: Icons.html_rounded, code: true),
    '.css': (lang: 'CSS', mime: 'text/css', icon: Icons.css_rounded, code: true),
    '.scss': (lang: 'SCSS', mime: 'text/x-scss', icon: Icons.css_rounded, code: true),
    '.sass': (lang: 'Sass', mime: 'text/x-sass', icon: Icons.css_rounded, code: true),
    '.less': (lang: 'Less', mime: 'text/x-less', icon: Icons.css_rounded, code: true),

    // Data, Config & Serialization
    '.json': (lang: 'JSON', mime: 'application/json', icon: Icons.data_object_rounded, code: true),
    '.yaml': (lang: 'YAML', mime: 'text/yaml', icon: Icons.settings_rounded, code: true),
    '.yml': (lang: 'YAML', mime: 'text/yaml', icon: Icons.settings_rounded, code: true),
    '.toml': (lang: 'TOML', mime: 'text/x-toml', icon: Icons.settings_rounded, code: true),
    '.xml': (lang: 'XML', mime: 'application/xml', icon: Icons.code_rounded, code: true),
    '.sql': (lang: 'SQL', mime: 'text/x-sql', icon: Icons.table_chart_outlined, code: true),
    '.csv': (lang: 'CSV', mime: 'text/csv', icon: Icons.table_rows_rounded, code: false),
    '.tsv': (lang: 'TSV', mime: 'text/tab-separated-values', icon: Icons.table_rows_rounded, code: false),

    // Shell & Scripting
    '.sh': (lang: 'Shell Script', mime: 'text/x-shellscript', icon: Icons.terminal_rounded, code: true),
    '.bash': (lang: 'Bash Script', mime: 'text/x-shellscript', icon: Icons.terminal_rounded, code: true),
    '.zsh': (lang: 'Zsh Script', mime: 'text/x-shellscript', icon: Icons.terminal_rounded, code: true),
    '.bat': (lang: 'Batch File', mime: 'application/x-bat', icon: Icons.terminal_rounded, code: true),
    '.ps1': (lang: 'PowerShell', mime: 'text/x-powershell', icon: Icons.terminal_rounded, code: true),

    // Documentation & Text
    '.md': (lang: 'Markdown', mime: 'text/markdown', icon: Icons.article_rounded, code: true),
    '.markdown': (lang: 'Markdown', mime: 'text/markdown', icon: Icons.article_rounded, code: true),
    '.txt': (lang: 'Plain Text', mime: 'text/plain', icon: Icons.description_outlined, code: false),
    '.log': (lang: 'Log File', mime: 'text/plain', icon: Icons.receipt_long_rounded, code: false),
    '.env': (lang: 'Environment Config', mime: 'text/plain', icon: Icons.lock_outline_rounded, code: false),
    '.gitignore': (lang: 'Git Ignore', mime: 'text/plain', icon: Icons.source_rounded, code: false),
    '.gitattributes': (lang: 'Git Attributes', mime: 'text/plain', icon: Icons.source_rounded, code: false),
    '.dockerignore': (lang: 'Docker Ignore', mime: 'text/plain', icon: Icons.layers_outlined, code: false),
    '.ini': (lang: 'INI Config', mime: 'text/plain', icon: Icons.settings_rounded, code: false),
    '.cfg': (lang: 'Config', mime: 'text/plain', icon: Icons.settings_rounded, code: false),
    '.conf': (lang: 'Config', mime: 'text/plain', icon: Icons.settings_rounded, code: false),
    '.properties': (lang: 'Properties', mime: 'text/plain', icon: Icons.settings_rounded, code: false),
    '.lock': (lang: 'Lock File', mime: 'text/plain', icon: Icons.lock_clock_rounded, code: false),
  };

  static const Map<String, ({String lang, String mime, IconData icon})> _knownFilenames = {
    'dockerfile': (lang: 'Dockerfile', mime: 'text/x-dockerfile', icon: Icons.layers_rounded),
    'makefile': (lang: 'Makefile', mime: 'text/x-makefile', icon: Icons.build_circle_rounded),
    'cmakelists.txt': (lang: 'CMake', mime: 'text/x-cmake', icon: Icons.build_circle_rounded),
    'license': (lang: 'License', mime: 'text/plain', icon: Icons.gavel_rounded),
    'procfile': (lang: 'Procfile', mime: 'text/plain', icon: Icons.settings_rounded),
  };

  /// Detects type, language, mime, and category from a filename or path.
  static FileTypeInfo detect(String pathOrFilename) {
    final baseName = p.basename(pathOrFilename).trim();
    final lowerBase = baseName.toLowerCase();
    final ext = p.extension(baseName).toLowerCase();

    // 1. Exact known filenames without standard extension (or special cases)
    if (_knownFilenames.containsKey(lowerBase)) {
      final info = _knownFilenames[lowerBase]!;
      return FileTypeInfo(
        category: FileCategory.text,
        language: info.lang,
        mimeType: info.mime,
        icon: info.icon,
        extension: ext,
        isCode: true,
      );
    }

    // 2. Images
    if (_imageExtensions.contains(ext)) {
      String mime = 'image/${ext.replaceFirst('.', '')}';
      if (ext == '.svg') mime = 'image/svg+xml';
      if (ext == '.jpg') mime = 'image/jpeg';
      return FileTypeInfo(
        category: FileCategory.image,
        language: ext.toUpperCase().replaceFirst('.', ''),
        mimeType: mime,
        icon: Icons.image_rounded,
        extension: ext,
        isCode: false,
      );
    }

    // 3. PDF
    if (_pdfExtensions.contains(ext)) {
      return FileTypeInfo(
        category: FileCategory.pdf,
        language: 'PDF Document',
        mimeType: 'application/pdf',
        icon: Icons.picture_as_pdf_rounded,
        extension: ext,
        isCode: false,
      );
    }

    // 4. Known code & text extensions
    if (_knownExtensions.containsKey(ext)) {
      final item = _knownExtensions[ext]!;
      return FileTypeInfo(
        category: FileCategory.text,
        language: item.lang,
        mimeType: item.mime,
        icon: item.icon,
        extension: ext,
        isCode: item.code,
      );
    }

    // 5. Common binary extensions
    const binaryExts = {
      '.zip', '.tar', '.gz', '.tgz', '.bz2', '.7z', '.rar',
      '.exe', '.dll', '.so', '.dylib', '.bin', '.class', '.pyc', '.o', '.a',
      '.db', '.sqlite', '.sqlite3', '.parquet', '.iso', '.dmg',
      '.mp3', '.wav', '.ogg', '.flac', '.mp4', '.mkv', '.avi', '.mov',
      '.ttf', '.otf', '.woff', '.woff2', '.eot',
    };

    if (binaryExts.contains(ext)) {
      return FileTypeInfo(
        category: FileCategory.binary,
        language: ext.toUpperCase().replaceFirst('.', ''),
        mimeType: 'application/octet-stream',
        icon: Icons.inventory_2_outlined,
        extension: ext,
        isCode: false,
      );
    }

    // 6. Fallback: treat as plain text if has no extension or unknown
    return FileTypeInfo(
      category: FileCategory.text,
      language: ext.isEmpty ? 'Plain Text' : ext.replaceFirst('.', '').toUpperCase(),
      mimeType: 'text/plain',
      icon: Icons.insert_drive_file_outlined,
      extension: ext,
      isCode: false,
    );
  }

  /// Convenience getter for an icon.
  static IconData getIcon(String pathOrFilename) {
    return detect(pathOrFilename).icon;
  }
}
