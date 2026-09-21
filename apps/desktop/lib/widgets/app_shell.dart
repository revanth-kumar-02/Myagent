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
import 'sidebar.dart';
import 'status_pill.dart';

class AppShell extends ConsumerStatefulWidget {
  const AppShell({super.key});

  @override
  ConsumerState<AppShell> createState() => _AppShellState();
}

class _AppShellState extends ConsumerState<AppShell> {
  NavigationTab _currentTab = NavigationTab.home;
  bool _isSidebarCollapsed = false;

  @override
  Widget build(BuildContext context) {
    final conn = ref.watch(connectionProvider);
    final isDark = Theme.of(context).brightness == Brightness.dark;

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
                  height: 48,
                  padding: const EdgeInsets.symmetric(horizontal: 16),
                  decoration: BoxDecoration(
                    color: isDark ? AppTheme.surfaceDark : AppTheme.surfaceLight,
                    border: Border(
                      bottom: BorderSide(
                        color: isDark ? AppTheme.borderDark : AppTheme.borderLight,
                        width: 1,
                      ),
                    ),
                  ),
                  child: Row(
                    children: [
                      IconButton(
                        icon: Icon(
                          _isSidebarCollapsed ? Icons.menu_open : Icons.menu,
                          size: 18,
                        ),
                        tooltip: _isSidebarCollapsed ? 'Expand Sidebar' : 'Collapse Sidebar',
                        onPressed: () => setState(() => _isSidebarCollapsed = !_isSidebarCollapsed),
                      ),
                      const SizedBox(width: 8),
                      Text(
                        _getTabTitle(_currentTab),
                        style: const TextStyle(fontWeight: FontWeight.w600, fontSize: 13),
                      ),
                      const Spacer(),
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
      NavigationTab.home     => 'Dashboard & Overview',
      NavigationTab.chat     => 'Primary Chat Interaction',
      NavigationTab.projects => 'Workspace Projects',
      NavigationTab.tasks    => 'Agent Task Board',
      NavigationTab.research => 'DuckDuckGo Web Research',
      NavigationTab.activity => 'System Observability',
      NavigationTab.memory   => 'Agent Memory Bank',
      NavigationTab.settings => 'Settings & Model Registry',
    };
  }
}
