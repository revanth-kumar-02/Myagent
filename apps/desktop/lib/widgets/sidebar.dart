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
    final isDark = Theme.of(context).brightness == Brightness.dark;
    final bg = isDark ? const Color(0xFF0F172A) : const Color(0xFFF8FAFC);
    final borderColor = isDark ? const Color(0xFF334155) : const Color(0xFFE2E8F0);

    return Container(
      width: isCollapsed ? 64 : 220,
      decoration: BoxDecoration(
        color: bg,
        border: Border(right: BorderSide(color: borderColor, width: 1)),
      ),
      child: Column(
        children: [
          // App Brand Header
          Container(
            height: 56,
            padding: const EdgeInsets.symmetric(horizontal: 16),
            alignment: Alignment.centerLeft,
            child: Row(
              children: [
                Container(
                  width: 28,
                  height: 28,
                  decoration: BoxDecoration(
                    color: AppTheme.primary,
                    borderRadius: BorderRadius.circular(6),
                  ),
                  child: const Center(
                    child: Text(
                      'K',
                      style: TextStyle(
                        color: Colors.white,
                        fontWeight: FontWeight.bold,
                        fontSize: 16,
                      ),
                    ),
                  ),
                ),
                if (!isCollapsed) ...[
                  const SizedBox(width: 10),
                  const Text(
                    'KORA',
                    style: TextStyle(
                      fontSize: 16,
                      fontWeight: FontWeight.w800,
                      letterSpacing: 1.2,
                    ),
                  ),
                ],
              ],
            ),
          ),
          const Divider(height: 1),
          const SizedBox(height: 12),

          // Nav Items
          _buildNavItem(NavigationTab.home, Icons.dashboard_outlined, 'Home'),
          _buildNavItem(NavigationTab.chat, Icons.chat_bubble_outline, 'Chat'),
          _buildNavItem(NavigationTab.projects, Icons.folder_outlined, 'Projects'),
          _buildNavItem(NavigationTab.tasks, Icons.check_box_outlined, 'Tasks'),
          _buildNavItem(NavigationTab.research, Icons.travel_explore_outlined, 'Research'),
          _buildNavItem(NavigationTab.activity, Icons.show_chart_outlined, 'Activity'),
          _buildNavItem(NavigationTab.memory, Icons.psychology_outlined, 'Memory'),

          const Spacer(),
          const Divider(height: 1),
          _buildNavItem(NavigationTab.settings, Icons.settings_outlined, 'Settings'),
          const SizedBox(height: 12),
        ],
      ),
    );
  }

  Widget _buildNavItem(NavigationTab tab, IconData icon, String label) {
    final isSelected = currentTab == tab;

    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 2),
      child: InkWell(
        onTap: () => onTabSelected(tab),
        borderRadius: BorderRadius.circular(6),
        child: Container(
          height: 38,
          padding: const EdgeInsets.symmetric(horizontal: 12),
          decoration: BoxDecoration(
            color: isSelected
                ? AppTheme.primary.withValues(alpha: 0.15)
                : Colors.transparent,
            borderRadius: BorderRadius.circular(6),
          ),
          child: Row(
            children: [
              Icon(
                icon,
                size: 18,
                color: isSelected ? AppTheme.primary : Colors.grey,
              ),
              if (!isCollapsed) ...[
                const SizedBox(width: 12),
                Text(
                  label,
                  style: TextStyle(
                    fontSize: 13,
                    fontWeight: isSelected ? FontWeight.w600 : FontWeight.w500,
                    color: isSelected ? AppTheme.primary : null,
                  ),
                ),
              ],
            ],
          ),
        ),
      ),
    );
  }
}
