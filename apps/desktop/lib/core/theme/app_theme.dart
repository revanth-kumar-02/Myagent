import 'package:flutter/material.dart';

/// Semantic color tokens for Kora Design System
class KoraColors extends ThemeExtension<KoraColors> {
  final Color bg;
  final Color surface;
  final Color surfaceHighlight;
  final Color surfaceTertiary;
  final Color border;
  final Color borderSubtle;
  final Color borderFocus;
  final Color textPrimary;
  final Color textSecondary;
  final Color textMuted;

  final Color primary;
  final Color primaryHover;
  final Color primaryLight;
  final Color primaryDark;

  final Color secondary;
  final Color secondaryLight;
  final Color secondaryDark;

  final Color accent;
  final Color accentLight;
  final Color accentDark;

  final Color success;
  final Color successLight;
  final Color warning;
  final Color warningLight;
  final Color error;
  final Color errorLight;

  final Color statusThinking;
  final Color statusSearching;
  final Color statusReading;
  final Color statusUsingTool;
  final Color statusVerifying;
  final Color statusCompleted;

  const KoraColors({
    required this.bg,
    required this.surface,
    required this.surfaceHighlight,
    required this.surfaceTertiary,
    required this.border,
    required this.borderSubtle,
    required this.borderFocus,
    required this.textPrimary,
    required this.textSecondary,
    required this.textMuted,
    required this.primary,
    required this.primaryHover,
    required this.primaryLight,
    required this.primaryDark,
    required this.secondary,
    required this.secondaryLight,
    required this.secondaryDark,
    required this.accent,
    required this.accentLight,
    required this.accentDark,
    required this.success,
    required this.successLight,
    required this.warning,
    required this.warningLight,
    required this.error,
    required this.errorLight,
    required this.statusThinking,
    required this.statusSearching,
    required this.statusReading,
    required this.statusUsingTool,
    required this.statusVerifying,
    required this.statusCompleted,
  });

  @override
  ThemeExtension<KoraColors> copyWith({
    Color? bg,
    Color? surface,
    Color? surfaceHighlight,
    Color? surfaceTertiary,
    Color? border,
    Color? borderSubtle,
    Color? borderFocus,
    Color? textPrimary,
    Color? textSecondary,
    Color? textMuted,
    Color? primary,
    Color? primaryHover,
    Color? primaryLight,
    Color? primaryDark,
    Color? secondary,
    Color? secondaryLight,
    Color? secondaryDark,
    Color? accent,
    Color? accentLight,
    Color? accentDark,
    Color? success,
    Color? successLight,
    Color? warning,
    Color? warningLight,
    Color? error,
    Color? errorLight,
    Color? statusThinking,
    Color? statusSearching,
    Color? statusReading,
    Color? statusUsingTool,
    Color? statusVerifying,
    Color? statusCompleted,
  }) {
    return KoraColors(
      bg: bg ?? this.bg,
      surface: surface ?? this.surface,
      surfaceHighlight: surfaceHighlight ?? this.surfaceHighlight,
      surfaceTertiary: surfaceTertiary ?? this.surfaceTertiary,
      border: border ?? this.border,
      borderSubtle: borderSubtle ?? this.borderSubtle,
      borderFocus: borderFocus ?? this.borderFocus,
      textPrimary: textPrimary ?? this.textPrimary,
      textSecondary: textSecondary ?? this.textSecondary,
      textMuted: textMuted ?? this.textMuted,
      primary: primary ?? this.primary,
      primaryHover: primaryHover ?? this.primaryHover,
      primaryLight: primaryLight ?? this.primaryLight,
      primaryDark: primaryDark ?? this.primaryDark,
      secondary: secondary ?? this.secondary,
      secondaryLight: secondaryLight ?? this.secondaryLight,
      secondaryDark: secondaryDark ?? this.secondaryDark,
      accent: accent ?? this.accent,
      accentLight: accentLight ?? this.accentLight,
      accentDark: accentDark ?? this.accentDark,
      success: success ?? this.success,
      successLight: successLight ?? this.successLight,
      warning: warning ?? this.warning,
      warningLight: warningLight ?? this.warningLight,
      error: error ?? this.error,
      errorLight: errorLight ?? this.errorLight,
      statusThinking: statusThinking ?? this.statusThinking,
      statusSearching: statusSearching ?? this.statusSearching,
      statusReading: statusReading ?? this.statusReading,
      statusUsingTool: statusUsingTool ?? this.statusUsingTool,
      statusVerifying: statusVerifying ?? this.statusVerifying,
      statusCompleted: statusCompleted ?? this.statusCompleted,
    );
  }

  @override
  ThemeExtension<KoraColors> lerp(ThemeExtension<KoraColors>? other, double t) {
    if (other is! KoraColors) return this;
    return KoraColors(
      bg: Color.lerp(bg, other.bg, t)!,
      surface: Color.lerp(surface, other.surface, t)!,
      surfaceHighlight: Color.lerp(surfaceHighlight, other.surfaceHighlight, t)!,
      surfaceTertiary: Color.lerp(surfaceTertiary, other.surfaceTertiary, t)!,
      border: Color.lerp(border, other.border, t)!,
      borderSubtle: Color.lerp(borderSubtle, other.borderSubtle, t)!,
      borderFocus: Color.lerp(borderFocus, other.borderFocus, t)!,
      textPrimary: Color.lerp(textPrimary, other.textPrimary, t)!,
      textSecondary: Color.lerp(textSecondary, other.textSecondary, t)!,
      textMuted: Color.lerp(textMuted, other.textMuted, t)!,
      primary: Color.lerp(primary, other.primary, t)!,
      primaryHover: Color.lerp(primaryHover, other.primaryHover, t)!,
      primaryLight: Color.lerp(primaryLight, other.primaryLight, t)!,
      primaryDark: Color.lerp(primaryDark, other.primaryDark, t)!,
      secondary: Color.lerp(secondary, other.secondary, t)!,
      secondaryLight: Color.lerp(secondaryLight, other.secondaryLight, t)!,
      secondaryDark: Color.lerp(secondaryDark, other.secondaryDark, t)!,
      accent: Color.lerp(accent, other.accent, t)!,
      accentLight: Color.lerp(accentLight, other.accentLight, t)!,
      accentDark: Color.lerp(accentDark, other.accentDark, t)!,
      success: Color.lerp(success, other.success, t)!,
      successLight: Color.lerp(successLight, other.successLight, t)!,
      warning: Color.lerp(warning, other.warning, t)!,
      warningLight: Color.lerp(warningLight, other.warningLight, t)!,
      error: Color.lerp(error, other.error, t)!,
      errorLight: Color.lerp(errorLight, other.errorLight, t)!,
      statusThinking: Color.lerp(statusThinking, other.statusThinking, t)!,
      statusSearching: Color.lerp(statusSearching, other.statusSearching, t)!,
      statusReading: Color.lerp(statusReading, other.statusReading, t)!,
      statusUsingTool: Color.lerp(statusUsingTool, other.statusUsingTool, t)!,
      statusVerifying: Color.lerp(statusVerifying, other.statusVerifying, t)!,
      statusCompleted: Color.lerp(statusCompleted, other.statusCompleted, t)!,
    );
  }
}

/// AppTheme — Kora Design System (Light & Dark)
class AppTheme {
  // ── Light Theme Tokens ──────────────────────────────────────────────────
  static const KoraColors lightColors = KoraColors(
    bg: Color(0xFFFBF9F5), // Warm Ivory / Cream
    surface: Color(0xFFFFFFFF), // Crisp White Card
    surfaceHighlight: Color(0xFFF4F1EA), // Secondary Card / Highlight
    surfaceTertiary: Color(0xFFEDE8DF),
    border: Color(0xFFE8E4DC), // Subtle Warm Border
    borderSubtle: Color(0xFFEFECE5),
    borderFocus: Color(0xFF4A6B5B),
    textPrimary: Color(0xFF222523), // Deep Charcoal
    textSecondary: Color(0xFF5C635E), // Muted Charcoal
    textMuted: Color(0xFF8A928B), // Subtle Sage-Grey
    primary: Color(0xFF4A6B5B), // Sage Green
    primaryHover: Color(0xFF3D5B4D),
    primaryLight: Color(0xFFEAF0EC), // Soft Sage Tint
    primaryDark: Color(0xFF385244), // Deep Sage
    secondary: Color(0xFF7E8B75), // Soft Olive
    secondaryLight: Color(0xFFF0F2EE),
    secondaryDark: Color(0xFF6E7C67),
    accent: Color(0xFFC86D51), // Subtle Terracotta / Coral
    accentLight: Color(0xFFF9EFEA),
    accentDark: Color(0xFFB85B40),
    success: Color(0xFF3D6E54),
    successLight: Color(0xFFE8F2EC),
    warning: Color(0xFFC68A36),
    warningLight: Color(0xFFFBF3E3),
    error: Color(0xFFBA4736),
    errorLight: Color(0xFFFBEAE8),
    statusThinking: Color(0xFF5C7C6D),
    statusSearching: Color(0xFFC68A36),
    statusReading: Color(0xFF4A6B5B),
    statusUsingTool: Color(0xFFC86D51),
    statusVerifying: Color(0xFF6E7C67),
    statusCompleted: Color(0xFF3D6E54),
  );

  // ── Dark Theme Tokens ───────────────────────────────────────────────────
  static const KoraColors darkColors = KoraColors(
    bg: Color(0xFF171A18), // Deep Warm Charcoal
    surface: Color(0xFF212522), // Dark Olive/Sage Surface
    surfaceHighlight: Color(0xFF2B302C), // Elevated Dark Card
    surfaceTertiary: Color(0xFF343B36),
    border: Color(0xFF333A35), // Subtle Muted Dark Border
    borderSubtle: Color(0xFF282F2A),
    borderFocus: Color(0xFF5F8B74),
    textPrimary: Color(0xFFF3F1EC), // Warm Ivory Text
    textSecondary: Color(0xFFA6AEA6), // Muted Warm Secondary
    textMuted: Color(0xFF757E76), // Subtle Sage-Grey
    primary: Color(0xFF5F8B74), // Warm Sage Green (Enhanced for Dark Mode)
    primaryHover: Color(0xFF6FA087),
    primaryLight: Color(0xFF26362D), // Dark Sage Container
    primaryDark: Color(0xFF8CB29E),
    secondary: Color(0xFF96A38D), // Soft Olive
    secondaryLight: Color(0xFF2D352B),
    secondaryDark: Color(0xFFBDC7B7),
    accent: Color(0xFFD98268), // Muted Terracotta Accent
    accentLight: Color(0xFF3E2822),
    accentDark: Color(0xFFE89882),
    success: Color(0xFF559972),
    successLight: Color(0xFF24362A),
    warning: Color(0xFFDCA34D),
    warningLight: Color(0xFF3D3220),
    error: Color(0xFFD95D4A),
    errorLight: Color(0xFF3E2320),
    statusThinking: Color(0xFF759B88),
    statusSearching: Color(0xFFDCA34D),
    statusReading: Color(0xFF5F8B74),
    statusUsingTool: Color(0xFFD98268),
    statusVerifying: Color(0xFF96A38D),
    statusCompleted: Color(0xFF559972),
  );

  /// Resolves the active [KoraColors] dynamically from the current [BuildContext].
  static KoraColors colors(BuildContext context) {
    final ext = Theme.of(context).extension<KoraColors>();
    if (ext != null) return ext;
    return Theme.of(context).brightness == Brightness.dark ? darkColors : lightColors;
  }

  static KoraColors of(BuildContext context) => colors(context);

  // Backward-compatible static references (defaulting to canonical brand colors)
  static const Color primary = Color(0xFF4A6B5B);
  static const Color primaryHover = Color(0xFF3D5B4D);
  static const Color primaryLight = Color(0xFFEAF0EC);
  static const Color primaryDark = Color(0xFF385244);
  static const Color secondary = Color(0xFF7E8B75);
  static const Color secondaryLight = Color(0xFFF0F2EE);
  static const Color secondaryDark = Color(0xFF6E7C67);
  static const Color accent = Color(0xFFC86D51);
  static const Color accentLight = Color(0xFFF9EFEA);
  static const Color accentDark = Color(0xFFB85B40);
  static const Color bgLight = Color(0xFFFBF9F5);
  static const Color surfaceLight = Color(0xFFFFFFFF);
  static const Color surfaceHighlightLight = Color(0xFFF4F1EA);
  static const Color surfaceTertiary = Color(0xFFEDE8DF);
  static const Color borderLight = Color(0xFFE8E4DC);
  static const Color borderSubtle = Color(0xFFEFECE5);
  static const Color textPrimaryLight = Color(0xFF222523);
  static const Color textSecondaryLight = Color(0xFF5C635E);
  static const Color textMuted = Color(0xFF8A928B);
  static const Color success = Color(0xFF3D6E54);
  static const Color successLight = Color(0xFFE8F2EC);
  static const Color warning = Color(0xFFC68A36);
  static const Color warningLight = Color(0xFFFBF3E3);
  static const Color error = Color(0xFFBA4736);
  static const Color errorLight = Color(0xFFFBEAE8);
  static const Color statusCompleted = Color(0xFF3D6E54);
  static const Color statusSearching = Color(0xFFC68A36);
  static const Color sageGreen = primary;
  static const Color softOlive = secondary;
  static const Color terracotta = accent;
  static const Color warmIvory = bgLight;
  static const Color cardLight = surfaceLight;
  static const Color cardDark = Color(0xFF212522);
  static const Color charcoalText = textPrimaryLight;
  static const Color bgDark = Color(0xFF171A18);
  static const Color surfaceDark = Color(0xFF212522);
  static const Color surfaceHighlightDark = Color(0xFF2B302C);
  static const Color borderDark = Color(0xFF333A35);
  static const Color textPrimaryDark = Color(0xFFF3F1EC);
  static const Color textSecondaryDark = Color(0xFFA6AEA6);

  /// Builds the complete Light ThemeData
  static ThemeData light() {
    final c = lightColors;
    return ThemeData(
      useMaterial3: true,
      brightness: Brightness.light,
      scaffoldBackgroundColor: c.bg,
      colorScheme: ColorScheme.light(
        primary: c.primary,
        onPrimary: Colors.white,
        primaryContainer: c.primaryLight,
        onPrimaryContainer: c.primaryDark,
        secondary: c.secondary,
        onSecondary: Colors.white,
        secondaryContainer: c.secondaryLight,
        onSecondaryContainer: c.secondaryDark,
        tertiary: c.accent,
        onTertiary: Colors.white,
        tertiaryContainer: c.accentLight,
        onTertiaryContainer: c.accentDark,
        surface: c.surface,
        onSurface: c.textPrimary,
        surfaceContainerHighest: c.surfaceHighlight,
        error: c.error,
        onError: Colors.white,
        errorContainer: c.errorLight,
        onErrorContainer: c.error,
        outline: c.border,
        outlineVariant: c.borderSubtle,
      ),
      cardTheme: CardThemeData(
        color: c.surface,
        elevation: 0,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(12),
          side: BorderSide(color: c.border, width: 1),
        ),
        margin: EdgeInsets.zero,
      ),
      dividerTheme: DividerThemeData(
        color: c.border,
        thickness: 1,
        space: 1,
      ),
      appBarTheme: AppBarTheme(
        backgroundColor: c.bg,
        foregroundColor: c.textPrimary,
        elevation: 0,
        centerTitle: false,
        scrolledUnderElevation: 0,
      ),
      inputDecorationTheme: InputDecorationTheme(
        filled: true,
        fillColor: c.surface,
        contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
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
        hintStyle: TextStyle(color: c.textMuted, fontSize: 14),
      ),
      elevatedButtonTheme: ElevatedButtonThemeData(
        style: ElevatedButton.styleFrom(
          backgroundColor: c.primary,
          foregroundColor: Colors.white,
          elevation: 0,
          padding: const EdgeInsets.symmetric(horizontal: 18, vertical: 12),
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
          textStyle: const TextStyle(fontWeight: FontWeight.w600, fontSize: 13),
        ),
      ),
      outlinedButtonTheme: OutlinedButtonThemeData(
        style: OutlinedButton.styleFrom(
          foregroundColor: c.textPrimary,
          side: BorderSide(color: c.border),
          padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
          textStyle: const TextStyle(fontWeight: FontWeight.w500, fontSize: 13),
        ),
      ),
      scrollbarTheme: ScrollbarThemeData(
        thumbColor: WidgetStateProperty.resolveWith((states) {
          if (states.contains(WidgetState.dragged)) {
            return c.secondary.withValues(alpha: 0.65);
          }
          if (states.contains(WidgetState.hovered)) {
            return c.secondary.withValues(alpha: 0.50);
          }
          return c.secondary.withValues(alpha: 0.25);
        }),
        trackColor: const WidgetStatePropertyAll(Colors.transparent),
        trackBorderColor: const WidgetStatePropertyAll(Colors.transparent),
        thickness: const WidgetStatePropertyAll(5.0),
        radius: const Radius.circular(8),
        crossAxisMargin: 2.0,
        mainAxisMargin: 4.0,
        interactive: true,
      ),
      fontFamily: 'Inter',
      extensions: const [lightColors],
    );
  }

  /// Builds the complete Dark ThemeData
  static ThemeData dark() {
    final c = darkColors;
    return ThemeData(
      useMaterial3: true,
      brightness: Brightness.dark,
      scaffoldBackgroundColor: c.bg,
      colorScheme: ColorScheme.dark(
        primary: c.primary,
        onPrimary: Colors.white,
        primaryContainer: c.primaryLight,
        onPrimaryContainer: c.primaryDark,
        secondary: c.secondary,
        onSecondary: Colors.white,
        secondaryContainer: c.secondaryLight,
        onSecondaryContainer: c.secondaryDark,
        tertiary: c.accent,
        onTertiary: Colors.white,
        tertiaryContainer: c.accentLight,
        onTertiaryContainer: c.accentDark,
        surface: c.surface,
        onSurface: c.textPrimary,
        surfaceContainerHighest: c.surfaceHighlight,
        error: c.error,
        onError: Colors.white,
        errorContainer: c.errorLight,
        onErrorContainer: c.error,
        outline: c.border,
        outlineVariant: c.borderSubtle,
      ),
      cardTheme: CardThemeData(
        color: c.surface,
        elevation: 0,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(12),
          side: BorderSide(color: c.border, width: 1),
        ),
        margin: EdgeInsets.zero,
      ),
      dividerTheme: DividerThemeData(
        color: c.border,
        thickness: 1,
        space: 1,
      ),
      appBarTheme: AppBarTheme(
        backgroundColor: c.bg,
        foregroundColor: c.textPrimary,
        elevation: 0,
        centerTitle: false,
        scrolledUnderElevation: 0,
      ),
      inputDecorationTheme: InputDecorationTheme(
        filled: true,
        fillColor: c.surface,
        contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
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
        hintStyle: TextStyle(color: c.textMuted, fontSize: 14),
      ),
      elevatedButtonTheme: ElevatedButtonThemeData(
        style: ElevatedButton.styleFrom(
          backgroundColor: c.primary,
          foregroundColor: Colors.white,
          elevation: 0,
          padding: const EdgeInsets.symmetric(horizontal: 18, vertical: 12),
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
          textStyle: const TextStyle(fontWeight: FontWeight.w600, fontSize: 13),
        ),
      ),
      outlinedButtonTheme: OutlinedButtonThemeData(
        style: OutlinedButton.styleFrom(
          foregroundColor: c.textPrimary,
          side: BorderSide(color: c.border),
          padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
          textStyle: const TextStyle(fontWeight: FontWeight.w500, fontSize: 13),
        ),
      ),
      scrollbarTheme: ScrollbarThemeData(
        thumbColor: WidgetStateProperty.resolveWith((states) {
          if (states.contains(WidgetState.dragged)) {
            return c.secondary.withValues(alpha: 0.65);
          }
          if (states.contains(WidgetState.hovered)) {
            return c.secondary.withValues(alpha: 0.50);
          }
          return c.secondary.withValues(alpha: 0.25);
        }),
        trackColor: const WidgetStatePropertyAll(Colors.transparent),
        trackBorderColor: const WidgetStatePropertyAll(Colors.transparent),
        thickness: const WidgetStatePropertyAll(5.0),
        radius: const Radius.circular(8),
        crossAxisMargin: 2.0,
        mainAxisMargin: 4.0,
        interactive: true,
      ),
      fontFamily: 'Inter',
      extensions: const [darkColors],
    );
  }
}

/// Convenience extension on BuildContext for effortless token access
extension KoraThemeContext on BuildContext {
  KoraColors get koraColors => AppTheme.colors(this);
  KoraColors get colors => AppTheme.colors(this);
}
