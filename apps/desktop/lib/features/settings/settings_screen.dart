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
    final c = AppTheme.colors(context);

    return Container(
      color: c.bg,
      child: SingleChildScrollView(
        padding: const EdgeInsets.all(24),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              'Settings & Configuration',
              style: TextStyle(
                fontSize: 20,
                fontWeight: FontWeight.bold,
                letterSpacing: -0.3,
                color: c.textPrimary,
              ),
            ),
            const SizedBox(height: 4),
            Text(
              'Manage agent network gateway, interface themes, and inspect active model capabilities.',
              style: TextStyle(fontSize: 12, color: c.textSecondary),
            ),
            const SizedBox(height: 24),

            // Appearance Section
            _buildSectionHeader('Appearance & Theme', c),
            const SizedBox(height: 10),
            Container(
              padding: const EdgeInsets.all(18),
              decoration: BoxDecoration(
                color: c.surface,
                borderRadius: BorderRadius.circular(12),
                border: Border.all(color: c.border),
                boxShadow: [
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
                  Row(
                    children: [
                      Container(
                        padding: const EdgeInsets.all(8),
                        decoration: BoxDecoration(
                          color: c.primary.withValues(alpha: 0.12),
                          borderRadius: BorderRadius.circular(8),
                        ),
                        child: Icon(
                          switch (settings.themeMode) {
                            ThemeMode.dark => Icons.dark_mode_rounded,
                            ThemeMode.light => Icons.light_mode_rounded,
                            ThemeMode.system => Icons.brightness_auto_rounded,
                          },
                          size: 20,
                          color: c.primary,
                        ),
                      ),
                      const SizedBox(width: 14),
                      Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            'Interface Theme',
                            style: TextStyle(
                              fontSize: 13,
                              fontWeight: FontWeight.w600,
                              color: c.textPrimary,
                            ),
                          ),
                          Text(
                            switch (settings.themeMode) {
                              ThemeMode.dark => 'Dark Charcoal & Olive',
                              ThemeMode.light => 'Warm Ivory & Sage (Default)',
                              ThemeMode.system => 'Follow Operating System',
                            },
                            style: TextStyle(fontSize: 11, color: c.textSecondary),
                          ),
                        ],
                      ),
                    ],
                  ),
                  const SizedBox(height: 16),

                  // Three-Way Theme Mode Selector: Light, Dark, System
                  Row(
                    children: [
                      Expanded(
                        child: _buildThemeOption(
                          mode: ThemeMode.light,
                          currentMode: settings.themeMode,
                          label: 'Light',
                          subtitle: 'Warm Ivory',
                          icon: Icons.light_mode_rounded,
                          colors: c,
                          onTap: () => ref.read(settingsProvider.notifier).setThemeMode(ThemeMode.light),
                        ),
                      ),
                      const SizedBox(width: 10),
                      Expanded(
                        child: _buildThemeOption(
                          mode: ThemeMode.dark,
                          currentMode: settings.themeMode,
                          label: 'Dark',
                          subtitle: 'Deep Charcoal',
                          icon: Icons.dark_mode_rounded,
                          colors: c,
                          onTap: () => ref.read(settingsProvider.notifier).setThemeMode(ThemeMode.dark),
                        ),
                      ),
                      const SizedBox(width: 10),
                      Expanded(
                        child: _buildThemeOption(
                          mode: ThemeMode.system,
                          currentMode: settings.themeMode,
                          label: 'System',
                          subtitle: 'Automatic',
                          icon: Icons.brightness_auto_rounded,
                          colors: c,
                          onTap: () => ref.read(settingsProvider.notifier).setThemeMode(ThemeMode.system),
                        ),
                      ),
                    ],
                  ),
                ],
              ),
            ),
            const SizedBox(height: 24),

            // Backend Connection
            _buildSectionHeader('Agent Gateway Connection', c),
            const SizedBox(height: 10),
            Container(
              padding: const EdgeInsets.all(18),
              decoration: BoxDecoration(
                color: c.surface,
                borderRadius: BorderRadius.circular(12),
                border: Border.all(color: c.border),
                boxShadow: [
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
                    style: TextStyle(color: c.textPrimary, fontSize: 13),
                    decoration: InputDecoration(
                      labelText: 'REST API Endpoint URL',
                      labelStyle: TextStyle(color: c.textSecondary, fontSize: 12),
                      hintText: 'http://127.0.0.1:8765',
                      fillColor: c.surfaceHighlight,
                      border: OutlineInputBorder(
                        borderRadius: BorderRadius.circular(10),
                        borderSide: BorderSide(color: c.border),
                      ),
                      enabledBorder: OutlineInputBorder(
                        borderRadius: BorderRadius.circular(10),
                        borderSide: BorderSide(color: c.border),
                      ),
                      focusedBorder: OutlineInputBorder(
                        borderRadius: BorderRadius.circular(10),
                        borderSide: BorderSide(color: c.primary, width: 1.5),
                      ),
                    ),
                  ),
                  const SizedBox(height: 14),
                  TextField(
                    controller: _wsUrlCtrl,
                    style: TextStyle(color: c.textPrimary, fontSize: 13),
                    decoration: InputDecoration(
                      labelText: 'WebSocket Realtime Gateway URL',
                      labelStyle: TextStyle(color: c.textSecondary, fontSize: 12),
                      hintText: 'ws://127.0.0.1:8765/ws',
                      fillColor: c.surfaceHighlight,
                      border: OutlineInputBorder(
                        borderRadius: BorderRadius.circular(10),
                        borderSide: BorderSide(color: c.border),
                      ),
                      enabledBorder: OutlineInputBorder(
                        borderRadius: BorderRadius.circular(10),
                        borderSide: BorderSide(color: c.border),
                      ),
                      focusedBorder: OutlineInputBorder(
                        borderRadius: BorderRadius.circular(10),
                        borderSide: BorderSide(color: c.primary, width: 1.5),
                      ),
                    ),
                  ),
                  const SizedBox(height: 16),
                  Row(
                    children: [
                      ElevatedButton(
                        style: ElevatedButton.styleFrom(
                          backgroundColor: c.primary,
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
                          color: (conn.status == BackendStatus.online ? c.success : c.accent)
                              .withValues(alpha: 0.12),
                          borderRadius: BorderRadius.circular(6),
                        ),
                        child: Row(
                          mainAxisSize: MainAxisSize.min,
                          children: [
                            Icon(
                              conn.status == BackendStatus.online ? Icons.check_circle_outline : Icons.error_outline,
                              size: 13,
                              color: conn.status == BackendStatus.online ? c.success : c.accent,
                            ),
                            const SizedBox(width: 6),
                            Text(
                              conn.status == BackendStatus.online ? 'Server reachable & verified' : 'Server offline / unreachable',
                              style: TextStyle(
                                fontSize: 11,
                                fontWeight: FontWeight.w600,
                                color: conn.status == BackendStatus.online ? c.success : c.accent,
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
                _buildSectionHeader('Model Registry Capabilities', c),
                const Spacer(),
                IconButton(
                  icon: Icon(Icons.refresh, size: 16, color: c.textSecondary),
                  tooltip: 'Reload Registry Info',
                  onPressed: () => ref.read(settingsProvider.notifier).loadModelInfo(),
                ),
              ],
            ),
            const SizedBox(height: 8),
            Container(
              padding: const EdgeInsets.all(18),
              decoration: BoxDecoration(
                color: c.surface,
                borderRadius: BorderRadius.circular(12),
                border: Border.all(color: c.border),
                boxShadow: [
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
                      style: TextStyle(fontSize: 12, color: c.textSecondary),
                    )
                  : Column(
                      children: settings.availableModels.map((m) => Container(
                        margin: const EdgeInsets.symmetric(vertical: 4),
                        padding: const EdgeInsets.all(12),
                        decoration: BoxDecoration(
                          color: c.surfaceHighlight,
                          borderRadius: BorderRadius.circular(8),
                          border: Border.all(color: c.borderSubtle),
                        ),
                        child: Row(
                          children: [
                            Container(
                              padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                              decoration: BoxDecoration(
                                color: c.primary.withValues(alpha: 0.15),
                                borderRadius: BorderRadius.circular(6),
                              ),
                              child: Text(
                                m.name,
                                style: TextStyle(fontSize: 11, fontWeight: FontWeight.bold, color: c.primary),
                              ),
                            ),
                            const SizedBox(width: 12),
                            Expanded(
                              child: Text(
                                'Capabilities: [${m.capabilities.join(", ")}] • Context: ${m.contextWindow} tokens • Provider: ${m.provider}',
                                style: TextStyle(
                                  fontSize: 11,
                                  fontFamily: 'monospace',
                                  color: c.textPrimary,
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
      ),
    );
  }

  Widget _buildSectionHeader(String title, KoraColors c) {
    return Text(
      title,
      style: TextStyle(
        fontSize: 13,
        fontWeight: FontWeight.bold,
        letterSpacing: -0.2,
        color: c.textPrimary,
      ),
    );
  }

  Widget _buildThemeOption({
    required ThemeMode mode,
    required ThemeMode currentMode,
    required String label,
    required String subtitle,
    required IconData icon,
    required KoraColors colors,
    required VoidCallback onTap,
  }) {
    final isSelected = mode == currentMode;
    return InkWell(
      onTap: onTap,
      borderRadius: BorderRadius.circular(10),
      child: AnimatedContainer(
        duration: const Duration(milliseconds: 150),
        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
        decoration: BoxDecoration(
          color: isSelected ? colors.primary.withValues(alpha: 0.12) : colors.surfaceHighlight,
          borderRadius: BorderRadius.circular(10),
          border: Border.all(
            color: isSelected ? colors.primary : colors.border,
            width: isSelected ? 1.5 : 1,
          ),
        ),
        child: Row(
          children: [
            Icon(
              icon,
              size: 18,
              color: isSelected ? colors.primary : colors.textSecondary,
            ),
            const SizedBox(width: 10),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                mainAxisSize: MainAxisSize.min,
                children: [
                  Text(
                    label,
                    style: TextStyle(
                      fontSize: 12,
                      fontWeight: isSelected ? FontWeight.w700 : FontWeight.w500,
                      color: isSelected ? colors.primary : colors.textPrimary,
                    ),
                  ),
                  Text(
                    subtitle,
                    style: TextStyle(
                      fontSize: 10,
                      color: colors.textMuted,
                    ),
                  ),
                ],
              ),
            ),
            if (isSelected)
              Icon(
                Icons.check_circle_rounded,
                size: 16,
                color: colors.primary,
              ),
          ],
        ),
      ),
    );
  }
}
