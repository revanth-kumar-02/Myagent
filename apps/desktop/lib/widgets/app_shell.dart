import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../core/theme/app_theme.dart';
import '../features/activity/activity_screen.dart';
import '../features/chat/chat_screen.dart';
import '../features/home/home_screen.dart';
import '../features/memory/memory_screen.dart';
import '../features/projects/projects_screen.dart';
import '../features/research/research_screen.dart';
import '../features/settings/settings_screen.dart';
import '../features/tasks/tasks_screen.dart';
import '../state/connection_state.dart';
import '../state/models_state.dart';
import 'sidebar.dart';
import 'status_pill.dart';

class AppShell extends ConsumerStatefulWidget {
  const AppShell({super.key});

  @override
  ConsumerState<AppShell> createState() => _AppShellState();
}

class _AppShellState extends ConsumerState<AppShell> {
  NavigationTab _currentTab = NavigationTab.chat; // Primary default
  bool _isSidebarCollapsed = false;

  @override
  Widget build(BuildContext context) {
    final conn = ref.watch(connectionProvider);
    final modelsState = ref.watch(modelsProvider);
    final c = AppTheme.colors(context);

    final currentView = switch (_currentTab) {
      NavigationTab.home     => HomeScreen(onNavigate: (t) => setState(() => _currentTab = t)),
      NavigationTab.chat     => const ChatScreen(),
      NavigationTab.projects => const ProjectsScreen(),
      NavigationTab.tasks    => const TasksScreen(),
      NavigationTab.research => const ResearchScreen(),
      NavigationTab.activity => const ActivityScreen(),
      NavigationTab.memory   => const MemoryScreen(),
      NavigationTab.settings => const SettingsScreen(),
    };

    return Scaffold(
      backgroundColor: c.bg,
      body: Row(
        children: [
          // Sidebar
          Sidebar(
            currentTab: _currentTab,
            isCollapsed: _isSidebarCollapsed,
            onTabSelected: (tab) => setState(() => _currentTab = tab),
          ),

          // Main App Content Area
          Expanded(
            child: Column(
              children: [
                // Top App Header
                Container(
                  height: 52,
                  padding: const EdgeInsets.symmetric(horizontal: 16),
                  decoration: BoxDecoration(
                    color: c.surface,
                    border: Border(
                      bottom: BorderSide(
                        color: c.border,
                        width: 1,
                      ),
                    ),
                  ),
                  child: Row(
                    children: [
                      IconButton(
                        icon: Icon(
                          _isSidebarCollapsed ? Icons.menu_open_rounded : Icons.menu_rounded,
                          size: 20,
                          color: c.textSecondary,
                        ),
                        tooltip: _isSidebarCollapsed ? 'Expand Sidebar' : 'Collapse Sidebar',
                        onPressed: () => setState(() => _isSidebarCollapsed = !_isSidebarCollapsed),
                      ),
                      const SizedBox(width: 8),
                      Container(
                        padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                        decoration: BoxDecoration(
                          color: c.surfaceHighlight,
                          borderRadius: BorderRadius.circular(6),
                          border: Border.all(color: c.borderSubtle),
                        ),
                        child: Row(
                          mainAxisSize: MainAxisSize.min,
                          children: [
                            Icon(Icons.auto_awesome_rounded, size: 14, color: c.primary),
                            const SizedBox(width: 6),
                            Text(
                              _getTabTitle(_currentTab),
                              style: TextStyle(
                                fontWeight: FontWeight.w600,
                                fontSize: 13,
                                color: c.textPrimary,
                              ),
                            ),
                          ],
                        ),
                      ),
                      const Spacer(),
                      // Dynamic Model Capability Indicator Pill
                      if (modelsState.activeChatModel != null || modelsState.models.isNotEmpty)
                        Container(
                          padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 5),
                          decoration: BoxDecoration(
                            color: c.primaryLight,
                            borderRadius: BorderRadius.circular(20),
                            border: Border.all(color: c.primary.withValues(alpha: 0.25)),
                          ),
                          child: Row(
                            mainAxisSize: MainAxisSize.min,
                            children: [
                              Icon(Icons.tune_rounded, size: 12, color: c.primary),
                              const SizedBox(width: 6),
                              Text(
                                modelsState.activeChatModel ?? (modelsState.models.isNotEmpty ? modelsState.models.first.name : 'Model Gateway'),
                                style: TextStyle(
                                  fontSize: 11,
                                  fontWeight: FontWeight.w600,
                                  color: c.primaryDark,
                                ),
                              ),
                            ],
                          ),
                        ),
                      const SizedBox(width: 12),
                      StatusPill(
                        status: conn.status,
                        onTap: () => ref.read(connectionProvider.notifier).checkConnection(),
                      ),
                    ],
                  ),
                ),

                // Active View Body
                Expanded(child: currentView),
              ],
            ),
          ),
        ],
      ),
    );
  }

  String _getTabTitle(NavigationTab tab) {
    return switch (tab) {
      NavigationTab.home     => 'Dashboard',
      NavigationTab.chat     => 'Chat Workspace',
      NavigationTab.projects => 'Knowledge Base & Projects',
      NavigationTab.tasks    => 'Autonomous Tasks',
      NavigationTab.research => 'DuckDuckGo Research',
      NavigationTab.activity => 'Observability & Traces',
      NavigationTab.memory   => 'Memory & Entities',
      NavigationTab.settings => 'Settings',
    };
  }
}
