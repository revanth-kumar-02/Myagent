import 'package:flutter/material.dart';
import '../core/theme/app_theme.dart';

enum NavigationTab {
  home,
  chat,
  projects,
  tasks,
  research,
  activity,
  memory,
  settings,
}

class Sidebar extends StatelessWidget {
  final NavigationTab currentTab;
  final ValueChanged<NavigationTab> onTabSelected;
  final bool isCollapsed;

  const Sidebar({
    super.key,
    required this.currentTab,
    required this.onTabSelected,
    this.isCollapsed = false,
  });

  @override
  Widget build(BuildContext context) {
    const bg = AppTheme.bgLight;
    const borderColor = AppTheme.borderLight;

    return Container(
      width: isCollapsed ? 68 : 224,
      decoration: const BoxDecoration(
        color: bg,
        border: Border(right: BorderSide(color: borderColor, width: 1)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // App Brand Header
          Container(
            height: 64,
            padding: const EdgeInsets.symmetric(horizontal: 16),
            alignment: Alignment.centerLeft,
            child: Row(
              children: [
                Container(
                  width: 32,
                  height: 32,
                  decoration: BoxDecoration(
                    color: AppTheme.primary,
                    borderRadius: BorderRadius.circular(8),
                    boxShadow: [
                      BoxShadow(
                        color: AppTheme.primary.withValues(alpha: 0.2),
                        blurRadius: 6,
                        offset: const Offset(0, 2),
                      ),
                    ],
                  ),
                  child: const Center(
                    child: Text(
                      'K',
                      style: TextStyle(
                        color: Colors.white,
                        fontWeight: FontWeight.w700,
                        fontSize: 17,
                        letterSpacing: -0.5,
                      ),
                    ),
                  ),
                ),
                if (!isCollapsed) ...[
                  const SizedBox(width: 12),
                  const Expanded(
                    child: Column(
                      mainAxisSize: MainAxisSize.min,
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          'KORA',
                          style: TextStyle(
                            fontSize: 15,
                            fontWeight: FontWeight.w800,
                            letterSpacing: 1.5,
                            color: AppTheme.textPrimaryLight,
                          ),
                        ),
                        Text(
                          'Workspace Agent',
                          style: TextStyle(
                            fontSize: 10,
                            fontWeight: FontWeight.w500,
                            color: AppTheme.textMuted,
                            letterSpacing: 0.2,
                          ),
                          overflow: TextOverflow.ellipsis,
                        ),
                      ],
                    ),
                  ),
                ],
              ],
            ),
          ),
          const Divider(height: 1, color: AppTheme.borderLight),
          const SizedBox(height: 12),

          // Nav Items
          _buildNavItem(NavigationTab.home, Icons.dashboard_rounded, 'Home'),
          _buildNavItem(NavigationTab.chat, Icons.chat_bubble_rounded, 'Chat'),
          _buildNavItem(NavigationTab.projects, Icons.folder_rounded, 'Projects'),
          _buildNavItem(NavigationTab.tasks, Icons.task_alt_rounded, 'Tasks'),
          _buildNavItem(NavigationTab.research, Icons.travel_explore_rounded, 'Research'),
          _buildNavItem(NavigationTab.activity, Icons.insights_rounded, 'Activity'),
          _buildNavItem(NavigationTab.memory, Icons.psychology_rounded, 'Memory'),

          const Spacer(),
          const Divider(height: 1, color: AppTheme.borderLight),
          const SizedBox(height: 6),
          _buildNavItem(NavigationTab.settings, Icons.tune_rounded, 'Settings'),
          const SizedBox(height: 12),
        ],
      ),
    );
  }

  Widget _buildNavItem(NavigationTab tab, IconData icon, String label) {
    final isSelected = currentTab == tab;

    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 3),
      child: Material(
        color: Colors.transparent,
        child: InkWell(
          onTap: () => onTabSelected(tab),
          borderRadius: BorderRadius.circular(8),
          hoverColor: AppTheme.surfaceHighlightLight,
          child: AnimatedContainer(
            duration: const Duration(milliseconds: 150),
            height: 40,
            padding: const EdgeInsets.symmetric(horizontal: 12),
            decoration: BoxDecoration(
              color: isSelected ? AppTheme.primaryLight : Colors.transparent,
              borderRadius: BorderRadius.circular(8),
              border: isSelected
                  ? Border.all(color: AppTheme.primary.withValues(alpha: 0.3), width: 1)
                  : null,
            ),
            child: Row(
              children: [
                Icon(
                  icon,
                  size: 19,
                  color: isSelected ? AppTheme.primary : AppTheme.textSecondaryLight,
                ),
                if (!isCollapsed) ...[
                  const SizedBox(width: 12),
                  Text(
                    label,
                    style: TextStyle(
                      fontSize: 13,
                      fontWeight: isSelected ? FontWeight.w600 : FontWeight.w500,
                      color: isSelected ? AppTheme.primaryDark : AppTheme.textSecondaryLight,
                    ),
                  ),
                ],
              ],
            ),
          ),
        ),
      ),
    );
  }
}

