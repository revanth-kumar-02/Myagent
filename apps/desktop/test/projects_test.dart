import 'dart:io';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:path/path.dart' as p;
import 'package:shared_preferences/shared_preferences.dart';

import 'package:kora_desktop/core/theme/app_theme.dart';
import 'package:kora_desktop/features/projects/file_preview_modal.dart';
import 'package:kora_desktop/features/projects/project_detail_screen.dart';
import 'package:kora_desktop/features/projects/projects_screen.dart';
import 'package:kora_desktop/models/project.dart';
import 'package:kora_desktop/services/project/file_type_detector.dart';
import 'package:kora_desktop/services/project/language_detector.dart';
import 'package:kora_desktop/services/project/project_service.dart';
import 'package:kora_desktop/state/projects_state.dart';

void main() {
  setUp(() {
    SharedPreferences.setMockInitialValues({});
  });

  group('Language and Framework Detection', () {
    test('detects programming languages from real extensions', () {
      final langs = LanguageDetector.detectLanguages({
        'main.dart',
        'app.py',
        'index.ts',
        'lib.rs',
        'Main.java',
        'script.sql',
        'native.cpp',
      });

      expect(langs, containsAll(['Dart', 'Python', 'TypeScript', 'Rust', 'Java', 'SQL', 'C++']));
    });

    test('detects project types and frameworks from signature files', () {
      final flutterType = LanguageDetector.detectProjectType(
        topLevelFiles: ['pubspec.yaml', 'lib/main.dart'],
        detectedLanguages: ['Dart'],
        fileSnippets: {'pubspec.yaml': 'dependencies:\n  flutter:\n    sdk: flutter'},
      );
      expect(flutterType, 'Flutter Application');

      final frameworks = LanguageDetector.detectFrameworks(
        topLevelFiles: ['pubspec.yaml'],
        fileSnippets: {'pubspec.yaml': 'dependencies:\n  flutter:\n    sdk: flutter'},
      );
      expect(frameworks, contains('Flutter'));

      final reactType = LanguageDetector.detectProjectType(
        topLevelFiles: ['package.json'],
        detectedLanguages: ['TypeScript'],
        fileSnippets: {'package.json': '{"dependencies": {"react": "^18.0.0"}}'},
      );
      expect(reactType, 'React Application');

      final pythonType = LanguageDetector.detectProjectType(
        topLevelFiles: ['pyproject.toml', 'main.py'],
        detectedLanguages: ['Python'],
      );
      expect(pythonType, 'Python Project');

      final rustType = LanguageDetector.detectProjectType(
        topLevelFiles: ['Cargo.toml', 'src/main.rs'],
        detectedLanguages: ['Rust'],
      );
      expect(rustType, 'Rust / Cargo Project');
    });
  });

  group('File Type Detector', () {
    test('categorizes text and code files accurately', () {
      final dartInfo = FileTypeDetector.detect('lib/main.dart');
      expect(dartInfo.category, FileCategory.text);
      expect(dartInfo.language, 'Dart');
      expect(dartInfo.isCode, true);

      final pyInfo = FileTypeDetector.detect('server/app.py');
      expect(pyInfo.category, FileCategory.text);
      expect(pyInfo.language, 'Python');
      expect(pyInfo.isCode, true);

      final tsInfo = FileTypeDetector.detect('src/index.tsx');
      expect(tsInfo.category, FileCategory.text);
      expect(tsInfo.language, 'TypeScript (React)');

      final mdInfo = FileTypeDetector.detect('README.md');
      expect(mdInfo.category, FileCategory.text);
      expect(mdInfo.language, 'Markdown');

      final jsonInfo = FileTypeDetector.detect('package.json');
      expect(jsonInfo.category, FileCategory.text);
      expect(jsonInfo.language, 'JSON');
    });

    test('categorizes image files accurately', () {
      final pngInfo = FileTypeDetector.detect('assets/logo.png');
      expect(pngInfo.category, FileCategory.image);
      expect(pngInfo.mimeType, 'image/png');

      final svgInfo = FileTypeDetector.detect('icons/star.svg');
      expect(svgInfo.category, FileCategory.image);
      expect(svgInfo.mimeType, 'image/svg+xml');

      final jpgInfo = FileTypeDetector.detect('photos/cover.jpg');
      expect(jpgInfo.category, FileCategory.image);
    });

    test('categorizes PDF files accurately', () {
      final pdfInfo = FileTypeDetector.detect('docs/manual.pdf');
      expect(pdfInfo.category, FileCategory.pdf);
      expect(pdfInfo.mimeType, 'application/pdf');
    });

    test('categorizes binary and unsupported files accurately', () {
      final zipInfo = FileTypeDetector.detect('archive.zip');
      expect(zipInfo.category, FileCategory.binary);

      final exeInfo = FileTypeDetector.detect('build/app.exe');
      expect(exeInfo.category, FileCategory.binary);

      final soInfo = FileTypeDetector.detect('lib/libnative.so');
      expect(soInfo.category, FileCategory.binary);
    });
  });

  group('Project Model & Safety', () {
    test('Project model correctly serializes and deserializes', () {
      const project = Project(
        id: 'p-1',
        name: 'MyAgent',
        rootPath: '/home/user/workspace/MyAgent',
        relativePath: 'MyAgent',
        exists: true,
        isDirectory: true,
        fileCount: 42,
        folderCount: 5,
        detectedLanguages: ['Python', 'Dart'],
        topLevelFolders: ['lib', 'backend', 'tests'],
        gitStatus: 'main',
        lastModified: 'Today',
        projectType: 'Python',
        frameworks: ['FastAPI'],
      );

      final json = project.toJson();
      expect(json['name'], 'MyAgent');
      expect(json['file_count'], 42);
      expect(json['detected_languages'], ['Python', 'Dart']);
      expect(json['top_level_folders'], ['lib', 'backend', 'tests']);

      final restored = Project.fromJson(json);
      expect(restored.name, 'MyAgent');
      expect(restored.fileCount, 42);
      expect(restored.detectedLanguages, ['Python', 'Dart']);
      expect(restored.topLevelFolders, ['lib', 'backend', 'tests']);
      expect(restored.projectType, 'Python');
    });

    test('ProjectService rejects path traversal in project creation', () async {
      final service = ProjectService();

      expect(
        () => service.createProject(workspacePath: '/tmp', name: '../evil'),
        throwsA(isA<Exception>()),
      );

      expect(
        () => service.createProject(workspacePath: '/tmp', name: 'sub/dir'),
        throwsA(isA<Exception>()),
      );

      expect(
        () => service.createProject(workspacePath: '/tmp', name: ''),
        throwsA(isA<Exception>()),
      );
    });

    test('ProjectService.readFile enforces traversal security on filesystem', () async {
      final service = ProjectService();
      final tempDir = Directory.systemTemp.createTempSync('kora_fs_test_');

      try {
        final testFile = File(p.join(tempDir.path, 'sample.py'));
        testFile.writeAsStringSync('print("Hello Kora")\n');

        // Reading legal file inside project
        final fileData = await service.readFile(
          projectPath: tempDir.path,
          relativePath: 'sample.py',
        );

        expect(fileData.name, 'sample.py');
        expect(fileData.category, FileCategory.text);
        expect(fileData.content, contains('Hello Kora'));
        expect(fileData.lineCount, 2);

        // Path traversal attack must be rejected
        expect(
          () => service.readFile(
            projectPath: tempDir.path,
            relativePath: '../../../../etc/passwd',
          ),
          throwsA(isA<Exception>()),
        );
      } finally {
        tempDir.deleteSync(recursive: true);
      }
    });
  });

  group('ProjectsScreen & Detail UI', () {
    testWidgets('shows "No workspace selected" empty state when no path is set', (tester) async {
      tester.view.physicalSize = const Size(1200, 800);
      tester.view.devicePixelRatio = 1.0;
      addTearDown(tester.view.resetPhysicalSize);

      await tester.pumpWidget(
        ProviderScope(
          overrides: [
            projectsProvider.overrideWith((ref) {
              final notifier = ProjectsNotifier(ProjectService());
              notifier.state = const ProjectsState(
                workspacePath: null,
                projects: [],
                isLoading: false,
              );
              return notifier;
            }),
          ],
          child: MaterialApp(
            theme: AppTheme.light(),
            home: const Scaffold(body: ProjectsScreen()),
          ),
        ),
      );

      await tester.pumpAndSettle();

      expect(find.text('Kora Projects'), findsWidgets);
      expect(find.text('No workspace selected'), findsOneWidget);
      expect(find.text('Choose Directory'), findsWidgets);
    });

    testWidgets('renders project cards with real filesystem metadata and action buttons', (tester) async {
      tester.view.physicalSize = const Size(1200, 800);
      tester.view.devicePixelRatio = 1.0;
      addTearDown(tester.view.resetPhysicalSize);

      const mockProject = Project(
        id: 'mock-1',
        name: 'KoraAgent',
        rootPath: '/home/user/Projects/KoraAgent',
        relativePath: 'KoraAgent',
        exists: true,
        isDirectory: true,
        fileCount: 312,
        folderCount: 24,
        detectedLanguages: ['Python', 'Dart', 'SQL'],
        topLevelFolders: ['apps', 'backend', 'docs'],
        gitStatus: 'Git: main',
        lastModified: 'Today',
        projectType: 'Flutter / Dart',
        frameworks: ['Flutter', 'FastAPI'],
      );

      await tester.pumpWidget(
        ProviderScope(
          overrides: [
            projectsProvider.overrideWith((ref) {
              final notifier = ProjectsNotifier(ProjectService());
              notifier.state = const ProjectsState(
                workspacePath: '/home/user/Projects',
                projects: [mockProject],
                isLoading: false,
              );
              return notifier;
            }),
          ],
          child: MaterialApp(
            theme: AppTheme.light(),
            home: const Scaffold(body: ProjectsScreen()),
          ),
        ),
      );

      await tester.pumpAndSettle();

      expect(find.text('KoraAgent'), findsOneWidget);
      expect(find.text('/home/user/Projects/KoraAgent'), findsOneWidget);
      expect(find.text('Flutter / Dart'), findsOneWidget);
      expect(find.textContaining('Python · Dart · SQL'), findsOneWidget);
      expect(find.textContaining('apps/'), findsOneWidget);
      expect(find.textContaining('backend/'), findsOneWidget);
      expect(find.textContaining('docs/'), findsOneWidget);
      expect(find.textContaining('312 files'), findsOneWidget);
      expect(find.textContaining('24 folders'), findsOneWidget);
      expect(find.text('Git: main'), findsOneWidget);

      expect(find.text('Open'), findsOneWidget);
      expect(find.text('VS Code'), findsOneWidget);
      expect(find.text('File Explorer'), findsOneWidget);
    });

    testWidgets('ProjectDetailScreen displays tree and tapping file triggers FilePreviewModal', (tester) async {
      tester.view.physicalSize = const Size(1200, 800);
      tester.view.devicePixelRatio = 1.0;
      addTearDown(tester.view.resetPhysicalSize);

      final tempDir = Directory.systemTemp.createTempSync('kora_detail_ui_');
      final sampleFile = File(p.join(tempDir.path, 'app.py'));
      sampleFile.writeAsStringSync('from fastapi import FastAPI\n\napp = FastAPI()\n');

      try {
        final mockProject = Project(
          id: 'test-p',
          name: 'TestApp',
          rootPath: tempDir.path,
          relativePath: 'TestApp',
          exists: true,
          isDirectory: true,
          fileCount: 1,
          folderCount: 0,
          detectedLanguages: ['Python'],
          topLevelFolders: [],
          gitStatus: 'None',
          lastModified: 'Today',
          projectType: 'Python',
          frameworks: [],
        );

        await tester.pumpWidget(
          ProviderScope(
            child: MaterialApp(
              theme: AppTheme.light(),
              home: Scaffold(
                body: ProjectDetailScreen(project: mockProject),
              ),
            ),
          ),
        );

        await tester.pumpAndSettle();

        expect(find.text('Filesystem Structure'), findsOneWidget);
        expect(find.text('app.py'), findsOneWidget);

        // Tap the file to open preview
        await tester.tap(find.text('app.py'));
        await tester.pumpAndSettle();

        // Verify FilePreviewModal opens
        expect(find.byType(FilePreviewModal), findsOneWidget);
        expect(find.text('Copy Path'), findsWidgets);
        expect(find.text('Open in VS Code'), findsWidgets);
        expect(find.textContaining('FastAPI'), findsWidgets);

        // Close modal with close button
        await tester.tap(find.byTooltip('Close (Esc)'));
        await tester.pumpAndSettle();

        expect(find.byType(FilePreviewModal), findsNothing);
      } finally {
        tempDir.deleteSync(recursive: true);
      }
    });
  });
}
