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
          const Text('Settings & Configuration', style: TextStyle(fontSize: 20, fontWeight: FontWeight.bold)),
          const SizedBox(height: 4),
          Text(
            'Configure server connections, UI theme, and review Model Registry capabilities.',
            style: TextStyle(fontSize: 12, color: isDark ? AppTheme.textSecondaryDark : AppTheme.textSecondaryLight),
          ),
          const SizedBox(height: 24),

          // Appearance
          const Text('Appearance', style: TextStyle(fontSize: 14, fontWeight: FontWeight.bold)),
          const SizedBox(height: 10),
          Container(
            padding: const EdgeInsets.all(16),
            decoration: BoxDecoration(
              color: isDark ? AppTheme.surfaceDark : AppTheme.surfaceLight,
              borderRadius: BorderRadius.circular(8),
              border: Border.all(color: isDark ? AppTheme.borderDark : AppTheme.borderLight),
            ),
            child: Row(
              children: [
                Icon(
                  settings.themeMode == ThemeMode.dark ? Icons.dark_mode_outlined : Icons.light_mode_outlined,
                  size: 20,
                  color: AppTheme.primary,
                ),
                const SizedBox(width: 12),
                Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Text('Theme Mode', style: TextStyle(fontSize: 13, fontWeight: FontWeight.w600)),
                    Text(
                      settings.themeMode == ThemeMode.dark ? 'Dark Slate' : 'Light Clean',
                      style: TextStyle(fontSize: 11, color: isDark ? AppTheme.textSecondaryDark : AppTheme.textSecondaryLight),
                    ),
                  ],
                ),
                const Spacer(),
                Switch(
                  value: settings.themeMode == ThemeMode.dark,
                  activeColor: AppTheme.primary,
                  onChanged: (_) => ref.read(settingsProvider.notifier).toggleTheme(),
                ),
              ],
            ),
          ),
          const SizedBox(height: 24),

          // Backend Connection
          const Text('Backend Connection', style: TextStyle(fontSize: 14, fontWeight: FontWeight.bold)),
          const SizedBox(height: 10),
          Container(
            padding: const EdgeInsets.all(16),
            decoration: BoxDecoration(
              color: isDark ? AppTheme.surfaceDark : AppTheme.surfaceLight,
              borderRadius: BorderRadius.circular(8),
              border: Border.all(color: isDark ? AppTheme.borderDark : AppTheme.borderLight),
            ),
            child: Column(
              children: [
                TextField(
                  controller: _httpUrlCtrl,
                  decoration: const InputDecoration(labelText: 'REST API Endpoint URL'),
                ),
                const SizedBox(height: 12),
                TextField(
                  controller: _wsUrlCtrl,
                  decoration: const InputDecoration(labelText: 'WebSocket Endpoint URL'),
                ),
                const SizedBox(height: 14),
                Row(
                  children: [
                    ElevatedButton(
                      style: ElevatedButton.styleFrom(backgroundColor: AppTheme.primary, foregroundColor: Colors.white),
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
                    const SizedBox(width: 12),
                    Text(
                      conn.status == BackendStatus.online ? '✓ Server reachable' : '✗ Server offline',
                      style: TextStyle(
                        fontSize: 12,
                        color: conn.status == BackendStatus.online ? AppTheme.success : AppTheme.error,
                      ),
                    ),
                  ],
                ),
              ],
            ),
          ),
          const SizedBox(height: 24),

          // Registered Model Capabilities (No Secrets)
          Row(
            children: [
              const Text('Model Registry Capabilities', style: TextStyle(fontSize: 14, fontWeight: FontWeight.bold)),
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
            padding: const EdgeInsets.all(16),
            decoration: BoxDecoration(
              color: isDark ? AppTheme.surfaceDark : AppTheme.surfaceLight,
              borderRadius: BorderRadius.circular(8),
              border: Border.all(color: isDark ? AppTheme.borderDark : AppTheme.borderLight),
            ),
            child: settings.availableModels.isEmpty
                ? const Text('No model metadata available from backend.', style: TextStyle(fontSize: 12, color: Colors.grey))
                : Column(
                    children: settings.availableModels.map((m) => Padding(
                      padding: const EdgeInsets.symmetric(vertical: 6),
                      child: Row(
                        children: [
                          Container(
                            padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                            decoration: BoxDecoration(
                              color: AppTheme.primary.withValues(alpha: 0.15),
                              borderRadius: BorderRadius.circular(4),
                            ),
                            child: Text(
                              m.name,
                              style: const TextStyle(fontSize: 11, fontWeight: FontWeight.bold, color: AppTheme.primary),
                            ),
                          ),
                          const SizedBox(width: 12),
                          Expanded(
                            child: Text(
                              'Capabilities: [${m.capabilities.join(", ")}] • Context: ${m.contextWindow} tokens • Provider: ${m.provider}',
                              style: const TextStyle(fontSize: 11, fontFamily: 'monospace'),
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
}
