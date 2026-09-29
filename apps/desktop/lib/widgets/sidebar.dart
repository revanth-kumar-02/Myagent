import 'package:flutter/material.dart';
import '../core/theme/app_theme.dart';

enum NavigationTab {
  home,
  chat,
  vision,
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
    final c = AppTheme.colors(context);

    return Container(
      width: isCollapsed ? 68 : 224,
      decoration: BoxDecoration(
        color: c.bg,
        border: Border(right: BorderSide(color: c.border, width: 1)),
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
                    color: c.primary,
                    borderRadius: BorderRadius.circular(8),
                    boxShadow: [
                      BoxShadow(
                        color: c.primary.withValues(alpha: 0.25),
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
                  Expanded(
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
                            color: c.textPrimary,
                          ),
                        ),
                        Text(
                          'Workspace Agent',
                          style: TextStyle(
                            fontSize: 10,
                            fontWeight: FontWeight.w500,
                            color: c.textMuted,
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
          Divider(height: 1, color: c.border),
          const SizedBox(height: 12),

          // + New Chat CTA
          if (!isCollapsed)
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 4),
              child: ElevatedButton.icon(
                icon: const Icon(Icons.add_rounded, size: 18),
                label: const Text('New Chat'),
                style: ElevatedButton.styleFrom(
                  backgroundColor: c.primary,
                  foregroundColor: Colors.white,
                  minimumSize: const Size.fromHeight(40),
                  padding: const EdgeInsets.symmetric(horizontal: 14),
                  shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
                  elevation: 0,
                ),
                onPressed: () => onTabSelected(NavigationTab.chat),
              ),
            )
          else
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
              child: IconButton(
                icon: Icon(Icons.add_rounded, color: c.primary),
                tooltip: 'New Chat',
                style: IconButton.styleFrom(
                  backgroundColor: c.primaryLight,
                  shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
                ),
                onPressed: () => onTabSelected(NavigationTab.chat),
              ),
            ),
          const SizedBox(height: 8),

          // Nav Items
          _buildNavItem(context, NavigationTab.home, Icons.dashboard_rounded, 'Home'),
          _buildNavItem(context, NavigationTab.chat, Icons.chat_bubble_rounded, 'Chat'),
          _buildNavItem(context, NavigationTab.vision, Icons.visibility_rounded, 'Vision'),
          _buildNavItem(context, NavigationTab.projects, Icons.folder_rounded, 'Projects'),
          _buildNavItem(context, NavigationTab.tasks, Icons.task_alt_rounded, 'Tasks'),
          _buildNavItem(context, NavigationTab.research, Icons.travel_explore_rounded, 'Research'),
          _buildNavItem(context, NavigationTab.activity, Icons.insights_rounded, 'Activity'),
          _buildNavItem(context, NavigationTab.memory, Icons.psychology_rounded, 'Memory'),

          const Spacer(),
          Divider(height: 1, color: c.border),
          const SizedBox(height: 6),
          _buildNavItem(context, NavigationTab.settings, Icons.tune_rounded, 'Settings'),
          const SizedBox(height: 12),
        ],
      ),
    );
  }

  Widget _buildNavItem(BuildContext context, NavigationTab tab, IconData icon, String label) {
    final c = AppTheme.colors(context);
    final isSelected = currentTab == tab;

    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 3),
      child: Material(
        color: Colors.transparent,
        child: InkWell(
          onTap: () => onTabSelected(tab),
          borderRadius: BorderRadius.circular(8),
          hoverColor: c.surfaceHighlight,
          child: AnimatedContainer(
            duration: const Duration(milliseconds: 150),
            height: 40,
            padding: const EdgeInsets.symmetric(horizontal: 12),
            decoration: BoxDecoration(
              color: isSelected ? c.primaryLight : Colors.transparent,
              borderRadius: BorderRadius.circular(8),
              border: isSelected
                  ? Border.all(color: c.primary.withValues(alpha: 0.35), width: 1)
                  : null,
            ),
            child: Row(
              children: [
                Icon(
                  icon,
                  size: 19,
                  color: isSelected ? c.primary : c.textSecondary,
                ),
                if (!isCollapsed) ...[
                  const SizedBox(width: 12),
                  Text(
                    label,
                    style: TextStyle(
                      fontSize: 13,
                      fontWeight: isSelected ? FontWeight.w600 : FontWeight.w500,
                      color: isSelected ? (Theme.of(context).brightness == Brightness.dark ? c.textPrimary : c.primaryDark) : c.textSecondary,
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
