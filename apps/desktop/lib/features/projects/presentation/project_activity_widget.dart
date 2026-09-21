import 'package:flutter/material.dart';

/// Activity event item model.
class ActivityItem {
  final String title;
  final String description;
  final String activityType;
  final DateTime timestamp;

  const ActivityItem({
    required this.title,
    required this.description,
    required this.activityType,
    required this.timestamp,
  });
}

/// Presentation feed showing real-time project activity events.
class ProjectActivityWidget extends StatelessWidget {
  final List<ActivityItem> activities;

  const ProjectActivityWidget({
    super.key,
    required this.activities,
  });

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    return Card(
      elevation: 2,
      margin: const EdgeInsets.symmetric(vertical: 8, horizontal: 16),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
      child: Padding(
        padding: const EdgeInsets.all(16.0),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              'Recent Project Activity',
              style: theme.textTheme.titleMedium?.copyWith(fontWeight: FontWeight.bold),
            ),
            const Divider(height: 20),
            if (activities.isEmpty)
              const Padding(
                padding: EdgeInsets.symmetric(vertical: 12.0),
                child: Center(
                  child: Text('No activity events logged yet.', style: TextStyle(color: Colors.grey)),
                ),
              )
            else
              ListView.separated(
                shrinkWrap: true,
                physics: const NeverScrollableScrollPhysics(),
                itemCount: activities.length,
                separatorBuilder: (_, __) => const Divider(height: 12),
                itemBuilder: (context, index) {
                  final item = activities[index];
                  return ListTile(
                    contentPadding: EdgeInsets.zero,
                    dense: true,
                    leading: _buildActivityIcon(item.activityType),
                    title: Text(item.title, style: const TextStyle(fontWeight: FontWeight.w600)),
                    subtitle: Text(item.description),
                    trailing: Text(
                      '${item.timestamp.hour.toString().padLeft(2, '0')}:${item.timestamp.minute.toString().padLeft(2, '0')}',
                      style: const TextStyle(fontSize: 11, color: Colors.grey),
                    ),
                  );
                },
              ),
          ],
        ),
      ),
    );
  }

  Widget _buildActivityIcon(String type) {
    IconData icon;
    Color color;

    switch (type.toLowerCase()) {
      case 'file_change':
        icon = Icons.edit_note;
        color = Colors.blue;
        break;
      case 'indexing':
        icon = Icons.auto_awesome;
        color = Colors.purple;
        break;
      case 'task':
        icon = Icons.check_circle_outline;
        color = Colors.green;
        break;
      case 'goal':
        icon = Icons.flag;
        color = Colors.amber[800]!;
        break;
      case 'decision':
        icon = Icons.psychology;
        color = Colors.teal;
        break;
      default:
        icon = Icons.circle;
        color = Colors.grey;
    }

    return CircleAvatar(
      radius: 16,
      backgroundColor: color.withOpacity(0.15),
      child: Icon(icon, size: 18, color: color),
    );
  }
}
