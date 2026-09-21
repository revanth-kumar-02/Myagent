import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/theme/app_theme.dart';
import '../../models/model_info.dart';
import '../../state/connection_state.dart';
import '../../state/settings_state.dart';

class SettingsScreen extends ConsumerStatefulWidget {
  const SettingsScreen({super.key});

  @override
  ConsumerState<SettingsScreen> createState() => _SettingsScreenState();
}

class _SettingsScreenState extends ConsumerState<SettingsScreen> {
  late final TextEditingController _httpUrlCtrl;
  late final TextEditingController _wsUrlCtrl;

  @override
  void initState() {
    super.initState();
    final settings = ref.read(settingsProvider);
    _httpUrlCtrl = TextEditingController(text: settings.backendHttpUrl);
    _wsUrlCtrl = TextEditingController(text: settings.backendWsUrl);
  }

  @override
  void dispose() {
    _httpUrlCtrl.dispose();
    _wsUrlCtrl.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final settings = ref.watch(settingsProvider);
    final conn = ref.watch(connectionProvider);
    final isDark = Theme.of(context).brightness == Brightness.dark;

    return SingleChildScrollView(
      padding: const EdgeInsets.all(24),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text(
            'Settings & Configuration',
            style: TextStyle(fontSize: 20, fontWeight: FontWeight.bold, letterSpacing: -0.3),
          ),
          const SizedBox(height: 4),
          Text(
            'Manage agent network gateway, interface themes, and inspect active model capabilities.',
            style: TextStyle(fontSize: 12, color: isDark ? AppTheme.textSecondaryDark : AppTheme.textSecondaryLight),
          ),
          const SizedBox(height: 24),

          // Appearance Section
          _buildSectionHeader('Appearance & Theme'),
          const SizedBox(height: 10),
          Container(
            padding: const EdgeInsets.all(18),
            decoration: BoxDecoration(
              color: isDark ? AppTheme.surfaceDark : AppTheme.cardLight,
              borderRadius: BorderRadius.circular(12),
              border: Border.all(color: isDark ? AppTheme.borderDark : AppTheme.borderLight),
              boxShadow: isDark
                  ? []
                  : [
                      BoxShadow(
                        color: Colors.black.withValues(alpha: 0.02),
                        blurRadius: 4,
                        offset: const Offset(0, 1),
                      ),
                    ],
            ),
            child: Row(
              children: [
                Container(
                  padding: const EdgeInsets.all(8),
                  decoration: BoxDecoration(
                    color: AppTheme.sageGreen.withValues(alpha: 0.12),
                    borderRadius: BorderRadius.circular(8),
                  ),
                  child: Icon(
                    settings.themeMode == ThemeMode.dark ? Icons.dark_mode_outlined : Icons.light_mode_outlined,
                    size: 20,
                    color: AppTheme.sageGreen,
                  ),
                ),
                const SizedBox(width: 14),
                Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Text('Theme Mode', style: TextStyle(fontSize: 13, fontWeight: FontWeight.w600)),
                    Text(
                      settings.themeMode == ThemeMode.dark ? 'Dark Slate' : 'Warm Ivory / Cream (Default)',
                      style: TextStyle(fontSize: 11, color: isDark ? AppTheme.textSecondaryDark : AppTheme.textSecondaryLight),
                    ),
                  ],
                ),
                const Spacer(),
                Switch(
                  value: settings.themeMode == ThemeMode.dark,
                  activeColor: AppTheme.sageGreen,
                  onChanged: (_) => ref.read(settingsProvider.notifier).toggleTheme(),
                ),
              ],
            ),
          ),
          const SizedBox(height: 24),

          // Backend Connection
          _buildSectionHeader('Agent Gateway Connection'),
          const SizedBox(height: 10),
          Container(
            padding: const EdgeInsets.all(18),
            decoration: BoxDecoration(
              color: isDark ? AppTheme.surfaceDark : AppTheme.cardLight,
              borderRadius: BorderRadius.circular(12),
              border: Border.all(color: isDark ? AppTheme.borderDark : AppTheme.borderLight),
              boxShadow: isDark
                  ? []
                  : [
                      BoxShadow(
                        color: Colors.black.withValues(alpha: 0.02),
                        blurRadius: 4,
                        offset: const Offset(0, 1),
                      ),
                    ],
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                TextField(
                  controller: _httpUrlCtrl,
                  decoration: InputDecoration(
                    labelText: 'REST API Endpoint URL',
                    hintText: 'http://127.0.0.1:8765',
                    border: OutlineInputBorder(borderRadius: BorderRadius.circular(10)),
                  ),
                ),
                const SizedBox(height: 14),
                TextField(
                  controller: _wsUrlCtrl,
                  decoration: InputDecoration(
                    labelText: 'WebSocket Realtime Gateway URL',
                    hintText: 'ws://127.0.0.1:8765/ws',
                    border: OutlineInputBorder(borderRadius: BorderRadius.circular(10)),
                  ),
                ),
                const SizedBox(height: 16),
                Row(
                  children: [
                    ElevatedButton(
                      style: ElevatedButton.styleFrom(
                        backgroundColor: AppTheme.sageGreen,
                        foregroundColor: Colors.white,
                        elevation: 0,
                        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
                      ),
                      child: const Text('Save & Test Connection'),
                      onPressed: () {
                        ref.read(settingsProvider.notifier).updateBackendUrls(
                          httpUrl: _httpUrlCtrl.text.trim(),
                          wsUrl: _wsUrlCtrl.text.trim(),
                        );
                        ref.read(connectionProvider.notifier).checkConnection();
                        ref.read(settingsProvider.notifier).loadModelInfo();
                      },
                    ),
                    const SizedBox(width: 14),
                    Container(
                      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 5),
                      decoration: BoxDecoration(
                        color: (conn.status == BackendStatus.online ? AppTheme.statusCompleted : AppTheme.terracotta)
                            .withValues(alpha: 0.12),
                        borderRadius: BorderRadius.circular(6),
                      ),
                      child: Row(
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          Icon(
                            conn.status == BackendStatus.online ? Icons.check_circle_outline : Icons.error_outline,
                            size: 13,
                            color: conn.status == BackendStatus.online ? AppTheme.statusCompleted : AppTheme.terracotta,
                          ),
                          const SizedBox(width: 6),
                          Text(
                            conn.status == BackendStatus.online ? 'Server reachable & verified' : 'Server offline / unreachable',
                            style: TextStyle(
                              fontSize: 11,
                              fontWeight: FontWeight.w600,
                              color: conn.status == BackendStatus.online ? AppTheme.statusCompleted : AppTheme.terracotta,
                            ),
                          ),
                        ],
                      ),
                    ),
                  ],
                ),
              ],
            ),
          ),
          const SizedBox(height: 24),

          // Registered Model Capabilities
          Row(
            children: [
              _buildSectionHeader('Model Registry Capabilities'),
              const Spacer(),
              IconButton(
                icon: const Icon(Icons.refresh, size: 16),
                tooltip: 'Reload Registry Info',
                onPressed: () => ref.read(settingsProvider.notifier).loadModelInfo(),
              ),
            ],
          ),
          const SizedBox(height: 8),
          Container(
            padding: const EdgeInsets.all(18),
            decoration: BoxDecoration(
              color: isDark ? AppTheme.surfaceDark : AppTheme.cardLight,
              borderRadius: BorderRadius.circular(12),
              border: Border.all(color: isDark ? AppTheme.borderDark : AppTheme.borderLight),
              boxShadow: isDark
                  ? []
                  : [
                      BoxShadow(
                        color: Colors.black.withValues(alpha: 0.02),
                        blurRadius: 4,
                        offset: const Offset(0, 1),
                      ),
                    ],
            ),
            child: settings.availableModels.isEmpty
                ? Text(
                    'No model metadata available from backend.',
                    style: TextStyle(fontSize: 12, color: isDark ? AppTheme.textSecondaryDark : AppTheme.textSecondaryLight),
                  )
                : Column(
                    children: settings.availableModels.map((m) => Container(
                      margin: const EdgeInsets.symmetric(vertical: 4),
                      padding: const EdgeInsets.all(12),
                      decoration: BoxDecoration(
                        color: isDark ? AppTheme.cardDark : AppTheme.warmIvory,
                        borderRadius: BorderRadius.circular(8),
                        border: Border.all(
                          color: isDark ? AppTheme.borderDark : AppTheme.borderLight,
                        ),
                      ),
                      child: Row(
                        children: [
                          Container(
                            padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                            decoration: BoxDecoration(
                              color: AppTheme.sageGreen.withValues(alpha: 0.15),
                              borderRadius: BorderRadius.circular(6),
                            ),
                            child: Text(
                              m.name,
                              style: const TextStyle(fontSize: 11, fontWeight: FontWeight.bold, color: AppTheme.sageGreen),
                            ),
                          ),
                          const SizedBox(width: 12),
                          Expanded(
                            child: Text(
                              'Capabilities: [${m.capabilities.join(", ")}] • Context: ${m.contextWindow} tokens • Provider: ${m.provider}',
                              style: TextStyle(
                                fontSize: 11,
                                fontFamily: 'monospace',
                                color: isDark ? AppTheme.textPrimaryDark : AppTheme.charcoalText,
                              ),
                            ),
                          ),
                        ],
                      ),
                    )).toList(),
                  ),
          ),
        ],
      ),
    );
  }

  Widget _buildSectionHeader(String title) {
    return Text(
      title,
      style: const TextStyle(fontSize: 13, fontWeight: FontWeight.bold, letterSpacing: -0.2),
    );
  }
}
