import 'package:flutter/material.dart';

class ToolCommand {
  final String name;
  final String title;
  final String description;
  final String category;
  final IconData icon;

  const ToolCommand({
    required this.name,
    required this.title,
    required this.description,
    required this.category,
    required this.icon,
  });

  factory ToolCommand.fromJson(Map<String, dynamic> json) {
    final name = json['name'] as String? ?? '';
    final title = json['title'] as String? ?? '/$name';
    final description = json['description'] as String? ?? '';
    final category = json['category'] as String? ?? 'general';

    IconData iconData = Icons.build_circle_rounded;
    if (category == 'research' || name == 'search' || name == 'web') {
      iconData = Icons.travel_explore_rounded;
    } else if (name == 'research') {
      iconData = Icons.bolt_rounded;
    } else if (category == 'rag' || name == 'rag') {
      iconData = Icons.folder_open_rounded;
    } else if (category == 'dev' || name.contains('git') || name.contains('terminal')) {
      iconData = Icons.terminal_rounded;
    } else if (category == 'files' || name.contains('file') || name.contains('dir')) {
      iconData = Icons.description_rounded;
    } else if (category == 'computer' || name.contains('mouse') || name.contains('keyboard') || name.contains('screen')) {
      iconData = Icons.computer_rounded;
    } else if (category == 'scheduler' || name.contains('task')) {
      iconData = Icons.schedule_rounded;
    } else if (name.contains('db')) {
      iconData = Icons.storage_rounded;
    }

    return ToolCommand(
      name: name,
      title: title.startsWith('/') ? title : '/$title',
      description: description,
      category: category,
      icon: iconData,
    );
  }
}

const List<ToolCommand> defaultToolCommands = [
  ToolCommand(
    name: 'search',
    title: '/search',
    description: 'Query DuckDuckGo for live external evidence & articles',
    category: 'research',
    icon: Icons.travel_explore_rounded,
  ),
  ToolCommand(
    name: 'research',
    title: '/research',
    description: 'Deep multi-source web research and synthesis',
    category: 'research',
    icon: Icons.bolt_rounded,
  ),
  ToolCommand(
    name: 'rag',
    title: '/rag',
    description: 'Query indexed local workspace code and knowledge',
    category: 'rag',
    icon: Icons.folder_open_rounded,
  ),
  ToolCommand(
    name: 'terminal_exec',
    title: '/terminal_exec',
    description: 'Execute shell commands in the workspace environment',
    category: 'dev',
    icon: Icons.terminal_rounded,
  ),
  ToolCommand(
    name: 'file_read',
    title: '/file_read',
    description: 'Read contents of a file in the workspace',
    category: 'files',
    icon: Icons.description_rounded,
  ),
  ToolCommand(
    name: 'file_create',
    title: '/file_create',
    description: 'Create a new file in the workspace directory',
    category: 'files',
    icon: Icons.note_add_rounded,
  ),
  ToolCommand(
    name: 'git_ops',
    title: '/git_ops',
    description: 'Perform git operations (status, diff, commit, log)',
    category: 'dev',
    icon: Icons.source_rounded,
  ),
  ToolCommand(
    name: 'db_ops',
    title: '/db_ops',
    description: 'Execute database queries against the workspace schema',
    category: 'dev',
    icon: Icons.storage_rounded,
  ),
  ToolCommand(
    name: 'task_list',
    title: '/task_list',
    description: 'Inspect active and historical background tasks',
    category: 'scheduler',
    icon: Icons.checklist_rounded,
  ),
];
