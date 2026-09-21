import 'package:flutter/material.dart';
import 'project_overview_widget.dart';
import 'project_health_widget.dart';
import 'project_activity_widget.dart';

/// Workspace desktop view coordinating projects, health, and activities.
class WorkspaceView extends StatefulWidget {
  const WorkspaceView({super.key});

  @override
  State<WorkspaceView> createState() => _WorkspaceViewState();
}

class _WorkspaceViewState extends State<WorkspaceView> {
  String _selectedProjectId = 'p1';

  final List<Map<String, dynamic>> _projects = [
    {
      'id': 'p1',
      'name': 'Myagent (Kora)',
      'root_path': '/home/rev/My_Personal_Space/Projects/Unfinished/Myagent',
      'status': 'active',
      'technologies': ['Flutter', 'FastAPI', 'PostgreSQL', 'pgvector', 'Redis', 'Riverpod'],
      'entry_points': ['apps/agent/main.py', 'apps/desktop/lib/main.dart'],
      'health_status': 'healthy',
      'indexing_status': 'indexed',
      'total_files': 142,
      'total_chunks': 480,
      'active_tasks': 2,
      'failed_tasks': 0,
      'active_goals': 3,
      'doc_coverage_ratio': 0.85,
      'issues': <String>[],
    }
  ];

  final List<ActivityItem> _activities = [
    ActivityItem(
      title: 'Workspace Initialized',
      description: 'Connected to local FastAPI backend & pgvector store.',
      activityType: 'indexing',
      timestamp: DateTime.now().subtract(const Duration(minutes: 15)),
    ),
    ActivityItem(
      title: 'Goal Progress Updated',
      description: 'Goal "Personal Knowledge Layer" reached 100%.',
      activityType: 'goal',
      timestamp: DateTime.now().subtract(const Duration(minutes: 5)),
    ),
  ];

  @override
  Widget build(BuildContext context) {
    final activeProject = _projects.firstWhere(
      (p) => p['id'] == _selectedProjectId,
      orElse: () => _projects.first,
    );

    return Scaffold(
      appBar: AppBar(
        title: const Text('Workspace & Projects', style: TextStyle(fontWeight: FontWeight.bold)),
        actions: [
          DropdownButton<String>(
            value: _selectedProjectId,
            underline: const SizedBox(),
            items: _projects.map((p) {
              return DropdownMenuItem<String>(
                value: p['id'] as String,
                child: Text(p['name'] as String, style: const TextStyle(fontWeight: FontWeight.w600)),
              );
            }).toList(),
            onChanged: (val) {
              if (val != null) {
                setState(() => _selectedProjectId = val);
              }
            },
          ),
          const SizedBox(width: 16),
          IconButton(
            icon: const Icon(Icons.add_circle_outline),
            tooltip: 'Register New Project',
            onPressed: () {
              // Open new project registration modal
            },
          ),
          const SizedBox(width: 16),
        ],
      ),
      body: SingleChildScrollView(
        padding: const EdgeInsets.symmetric(vertical: 12.0),
        child: Column(
          children: [
            ProjectOverviewWidget(
              projectName: activeProject['name'] as String,
              rootPath: activeProject['root_path'] as String,
              status: activeProject['status'] as String,
              technologies: List<String>.from(activeProject['technologies'] as List),
              entryPoints: List<String>.from(activeProject['entry_points'] as List),
              onIndexRequested: () {
                ScaffoldMessenger.of(context).showSnackBar(
                  const SnackBar(content: Text('Triggering background RAG indexing...')),
                );
              },
              onArchiveRequested: () {
                ScaffoldMessenger.of(context).showSnackBar(
                  const SnackBar(content: Text('Project archived.')),
                );
              },
            ),
            ProjectHealthWidget(
              healthStatus: activeProject['health_status'] as String,
              indexingStatus: activeProject['indexing_status'] as String,
              totalFiles: activeProject['total_files'] as int,
              totalChunks: activeProject['total_chunks'] as int,
              activeTasks: activeProject['active_tasks'] as int,
              failedTasks: activeProject['failed_tasks'] as int,
              activeGoals: activeProject['active_goals'] as int,
              docCoverageRatio: (activeProject['doc_coverage_ratio'] as num).toDouble(),
              issues: List<String>.from(activeProject['issues'] as List),
            ),
            ProjectActivityWidget(activities: _activities),
          ],
        ),
      ),
    );
  }
}
