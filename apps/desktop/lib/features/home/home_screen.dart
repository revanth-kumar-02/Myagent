import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/theme/app_theme.dart';
import '../../state/activity_state.dart';
import '../../state/connection_state.dart';
import '../../state/projects_state.dart';
import '../../state/tasks_state.dart';
import '../../widgets/sidebar.dart';

class HomeScreen extends ConsumerWidget {
  final ValueChanged<NavigationTab> onNavigate;

  const HomeScreen({
    super.key,
    required this.onNavigate,
  });

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final connState = ref.watch(connectionProvider);
    final projectsState = ref.watch(projectsProvider);
    final tasksState = ref.watch(tasksProvider);
    final activityState = ref.watch(activityProvider);

    return Container(
      color: AppTheme.bgLight,
      child: SingleChildScrollView(
        padding: const EdgeInsets.symmetric(horizontal: 28, vertical: 24),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // Welcome Header
            Row(
              children: [
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      const Text(
                        'Good day, Workspace User',
                        style: TextStyle(
                          fontSize: 22,
                          fontWeight: FontWeight.w800,
                          letterSpacing: -0.5,
                          color: AppTheme.textPrimaryLight,
                        ),
                      ),
                      const SizedBox(height: 4),
                      const Text(
                        'Autonomous agent ready with RAG document retrieval, persistent memory, and live web research.',
                        style: TextStyle(
                          fontSize: 13,
                          color: AppTheme.textSecondaryLight,
                        ),
                      ),
                    ],
                  ),
                ),
                ElevatedButton.icon(
                  icon: const Icon(Icons.chat_bubble_rounded, size: 15),
                  label: const Text('Open Chat'),
                  style: ElevatedButton.styleFrom(
                    backgroundColor: AppTheme.primary,
                    foregroundColor: Colors.white,
                    shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
                    padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
                  ),
                  onPressed: () => onNavigate(NavigationTab.chat),
                ),
              ],
            ),
            const SizedBox(height: 24),

            // Overview Stats Grid
            Row(
              children: [
                Expanded(
                  child: _buildStatCard(
                    title: 'System Status',
                    value: connState.status == BackendStatus.online ? 'Connected' : 'Offline',
                    subtitle: '${connState.modelsAvailable} Capability Models',
                    icon: Icons.check_circle_rounded,
                    color: AppTheme.success,
                  ),
                ),
                const SizedBox(width: 14),
                Expanded(
                  child: _buildStatCard(
                    title: 'Knowledge Base',
                    value: '${projectsState.projects.length}',
                    subtitle: 'Projects Indexed',
                    icon: Icons.folder_rounded,
                    color: AppTheme.secondary,
                    onTap: () => onNavigate(NavigationTab.projects),
                  ),
                ),
                const SizedBox(width: 14),
                Expanded(
                  child: _buildStatCard(
                    title: 'Agent Tasks',
                    value: '${tasksState.tasks.length}',
                    subtitle: '${tasksState.tasks.where((t) => t.status == "running").length} In Progress',
                    icon: Icons.task_alt_rounded,
                    color: AppTheme.primary,
                    onTap: () => onNavigate(NavigationTab.tasks),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 28),

            // Quick Capabilities & Actions
            const Text(
              'Agent Capabilities',
              style: TextStyle(
                fontSize: 15,
                fontWeight: FontWeight.w700,
                color: AppTheme.textPrimaryLight,
                letterSpacing: -0.2,
              ),
            ),
            const SizedBox(height: 12),
            Row(
              children: [
                Expanded(
                  child: _buildActionTile(
                    icon: Icons.travel_explore_rounded,
                    title: 'DuckDuckGo Research',
                    description: 'Extract external evidence and generate summarized reports.',
                    onTap: () => onNavigate(NavigationTab.research),
                  ),
                ),
                const SizedBox(width: 14),
                Expanded(
                  child: _buildActionTile(
                    icon: Icons.psychology_rounded,
                    title: 'Personal Memory',
                    description: 'Explore learned facts, preferences, and knowledge entities.',
                    onTap: () => onNavigate(NavigationTab.memory),
                  ),
                ),
                const SizedBox(width: 14),
                Expanded(
                  child: _buildActionTile(
                    icon: Icons.tune_rounded,
                    title: 'Model Gateway',
                    description: 'Qwen3 & Gemma-4 capability routing and telemetry.',
                    onTap: () => onNavigate(NavigationTab.settings),
                  ),
                ),
              ],
            ),

            const SizedBox(height: 28),

            // Recent Activity Feed
            Row(
              children: [
                const Text(
                  'Recent Agent Activity',
                  style: TextStyle(
                    fontSize: 15,
                    fontWeight: FontWeight.w700,
                    color: AppTheme.textPrimaryLight,
                    letterSpacing: -0.2,
                  ),
                ),
                const Spacer(),
                TextButton.icon(
                  icon: const Icon(Icons.arrow_forward_rounded, size: 14, color: AppTheme.primary),
                  label: const Text(
                    'View All Traces',
                    style: TextStyle(fontSize: 12, fontWeight: FontWeight.w600, color: AppTheme.primary),
                  ),
                  onPressed: () => onNavigate(NavigationTab.activity),
                ),
              ],
            ),
            const SizedBox(height: 10),
            Container(
              padding: const EdgeInsets.all(16),
              decoration: BoxDecoration(
                color: AppTheme.surfaceLight,
                borderRadius: BorderRadius.circular(12),
                border: Border.all(color: AppTheme.borderLight, width: 1),
                boxShadow: [
                  BoxShadow(
                    color: Colors.black.withValues(alpha: 0.02),
                    blurRadius: 6,
                    offset: const Offset(0, 2),
                  ),
                ],
              ),
              child: activityState.logs.isEmpty
                  ? const Padding(
                      padding: EdgeInsets.symmetric(vertical: 16),
                      child: Center(
                        child: Text(
                          'No recent activity logs. Send a prompt to see agent reasoning traces.',
                          style: TextStyle(fontSize: 13, color: AppTheme.textMuted),
                        ),
                      ),
                    )
                  : Column(
                      children: activityState.logs.take(4).map((log) => Container(
                        margin: const EdgeInsets.symmetric(vertical: 4),
                        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
                        decoration: BoxDecoration(
                          color: AppTheme.surfaceHighlightLight,
                          borderRadius: BorderRadius.circular(8),
                        ),
                        child: Row(
                          children: [
                            Container(
                              padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                              decoration: BoxDecoration(
                                color: AppTheme.primaryLight,
                                borderRadius: BorderRadius.circular(4),
                              ),
                              child: Text(
                                log.eventType,
                                style: const TextStyle(
                                  fontSize: 10.5,
                                  fontWeight: FontWeight.w700,
                                  color: AppTheme.primaryDark,
                                ),
                              ),
                            ),
                            const SizedBox(width: 12),
                            Expanded(
                              child: Text(
                                log.details,
                                style: const TextStyle(
                                  fontSize: 12.5,
                                  fontWeight: FontWeight.w500,
                                  color: AppTheme.textPrimaryLight,
                                ),
                                overflow: TextOverflow.ellipsis,
                              ),
                            ),
                            if (log.latencyMs > 0) ...[
                              const SizedBox(width: 8),
                              Text(
                                '${log.latencyMs}ms',
                                style: const TextStyle(fontSize: 11, color: AppTheme.textMuted),
                              ),
                            ],
                          ],
                        ),
                      )).toList(),
                    ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildStatCard({
    required String title,
    required String value,
    required String subtitle,
    required IconData icon,
    required Color color,
    VoidCallback? onTap,
  }) {
    return Material(
      color: Colors.transparent,
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(12),
        hoverColor: AppTheme.surfaceHighlightLight,
        child: Container(
          padding: const EdgeInsets.all(16),
          decoration: BoxDecoration(
            color: AppTheme.surfaceLight,
            borderRadius: BorderRadius.circular(12),
            border: Border.all(color: AppTheme.borderLight, width: 1),
            boxShadow: [
              BoxShadow(
                color: Colors.black.withValues(alpha: 0.02),
                blurRadius: 6,
                offset: const Offset(0, 2),
              ),
            ],
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  Container(
                    padding: const EdgeInsets.all(6),
                    decoration: BoxDecoration(
                      color: color.withValues(alpha: 0.12),
                      borderRadius: BorderRadius.circular(6),
                    ),
                    child: Icon(icon, size: 16, color: color),
                  ),
                  const Spacer(),
                  Text(
                    title,
                    style: const TextStyle(
                      fontSize: 12,
                      fontWeight: FontWeight.w600,
                      color: AppTheme.textSecondaryLight,
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 12),
              Text(
                value,
                style: const TextStyle(
                  fontSize: 20,
                  fontWeight: FontWeight.w800,
                  color: AppTheme.textPrimaryLight,
                  letterSpacing: -0.5,
                ),
              ),
              const SizedBox(height: 3),
              Text(
                subtitle,
                style: const TextStyle(
                  fontSize: 11,
                  color: AppTheme.textMuted,
                  fontWeight: FontWeight.w500,
                ),
                overflow: TextOverflow.ellipsis,
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildActionTile({
    required IconData icon,
    required String title,
    required String description,
    required VoidCallback onTap,
  }) {
    return Material(
      color: Colors.transparent,
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(12),
        hoverColor: AppTheme.surfaceHighlightLight,
        child: Container(
          padding: const EdgeInsets.all(16),
          decoration: BoxDecoration(
            color: AppTheme.surfaceLight,
            borderRadius: BorderRadius.circular(12),
            border: Border.all(color: AppTheme.borderLight, width: 1),
            boxShadow: [
              BoxShadow(
                color: Colors.black.withValues(alpha: 0.02),
                blurRadius: 6,
                offset: const Offset(0, 2),
              ),
            ],
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Container(
                padding: const EdgeInsets.all(8),
                decoration: BoxDecoration(
                  color: AppTheme.primaryLight,
                  borderRadius: BorderRadius.circular(8),
                ),
                child: Icon(icon, size: 18, color: AppTheme.primary),
              ),
              const SizedBox(height: 12),
              Text(
                title,
                style: const TextStyle(
                  fontSize: 13.5,
                  fontWeight: FontWeight.w700,
                  color: AppTheme.textPrimaryLight,
                ),
              ),
              const SizedBox(height: 4),
              Text(
                description,
                style: const TextStyle(
                  fontSize: 11.5,
                  color: AppTheme.textSecondaryLight,
                  height: 1.35,
                ),
                maxLines: 2,
                overflow: TextOverflow.ellipsis,
              ),
            ],
          ),
        ),
      ),
    );
  }
}

