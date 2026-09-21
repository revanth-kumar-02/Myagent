import 'package:flutter/material.dart';

/// AppTheme — Kora Stitch Light Design System
///
/// Palette:
/// - Background: Warm Ivory / Cream (#FBF9F5)
/// - Surface: Crisp White (#FFFFFF)
/// - Surface Secondary / Highlight: Soft Warm Cream (#F4F1EA)
/// - Surface Tertiary: Muted Cream (#EDE8DF)
/// - Borders: Subtle Warm Gray (#E8E4DC)
/// - Primary: Warm Sage Green (#4A6B5B)
/// - Primary Light: Soft Sage Tint (#EAF0EC)
/// - Primary Dark: Deep Sage (#385244)
/// - Secondary: Soft Olive (#7E8B75)
/// - Secondary Light: Soft Olive Tint (#F0F2EE)
/// - Accent: Subtle Terracotta / Coral (#C86D51)
/// - Accent Light: Soft Terracotta Tint (#F9EFEA)
/// - Text Primary: Deep Charcoal (#222523)
/// - Text Secondary: Muted Charcoal (#5C635E)
/// - Text Muted: Subtle Sage-Grey (#8A928B)
class AppTheme {
  // Brand Core
  static const Color primary = Color(0xFF4A6B5B); // Sage Green
  static const Color primaryHover = Color(0xFF3D5B4D);
  static const Color primaryLight = Color(0xFFEAF0EC);
  static const Color primaryDark = Color(0xFF385244);

  static const Color secondary = Color(0xFF7E8B75); // Soft Olive
  static const Color secondaryLight = Color(0xFFF0F2EE);
  static const Color secondaryDark = Color(0xFF6E7C67);

  static const Color accent = Color(0xFFC86D51); // Subtle Terracotta
  static const Color accentLight = Color(0xFFF9EFEA);
  static const Color accentDark = Color(0xFFB85B40);

  // Background & Surfaces
  static const Color bgLight = Color(0xFFFBF9F5); // Warm Ivory
  static const Color surfaceLight = Color(0xFFFFFFFF); // Pure White Card
  static const Color surfaceHighlightLight = Color(0xFFF4F1EA); // Secondary Card / Elevated Surface
  static const Color surfaceTertiary = Color(0xFFEDE8DF);
  static const Color borderLight = Color(0xFFE8E4DC); // Subtle Warm Border
  static const Color borderSubtle = Color(0xFFEFECE5);
  static const Color borderFocus = Color(0xFF4A6B5B);

  // Text Hierarchy
  static const Color textPrimaryLight = Color(0xFF222523); // Deep Charcoal
  static const Color textSecondaryLight = Color(0xFF5C635E); // Muted Charcoal
  static const Color textMuted = Color(0xFF8A928B); // Subtle Sage-Grey

  // Feedback & Semantic Colors
  static const Color success = Color(0xFF3D6E54); // Sage Green
  static const Color successLight = Color(0xFFE8F2EC);
  static const Color warning = Color(0xFFC68A36); // Warm Amber
  static const Color warningLight = Color(0xFFFBF3E3);
  static const Color error = Color(0xFFBA4736); // Brick Red / Terracotta Alert
  static const Color errorLight = Color(0xFFFBEAE8);

  // Agent UI Semantic Activity Tokens
  static const Color statusThinking = Color(0xFF5C7C6D); // Sage Pulse
  static const Color statusSearching = Color(0xFFC68A36); // Amber/Olive
  static const Color statusReading = Color(0xFF4A6B5B); // Sage Document
  static const Color statusUsingTool = Color(0xFFC86D51); // Terracotta Tool
  static const Color statusVerifying = Color(0xFF6E7C67); // Deep Olive Check
  static const Color statusCompleted = Color(0xFF3D6E54); // Sage Confirmed

  // Dark Theme Palette fallback
  static const Color bgDark = Color(0xFF1E211F);
  static const Color surfaceDark = Color(0xFF262A27);
  static const Color surfaceHighlightDark = Color(0xFF313632);
  static const Color borderDark = Color(0xFF3D433E);
  static const Color textPrimaryDark = Color(0xFFF2F4F2);
  static const Color textSecondaryDark = Color(0xFFA2AAA3);

  static ThemeData light() {
    return ThemeData(
      useMaterial3: true,
      brightness: Brightness.light,
      scaffoldBackgroundColor: bgLight,
      colorScheme: const ColorScheme.light(
        primary: primary,
        onPrimary: Colors.white,
        primaryContainer: primaryLight,
        onPrimaryContainer: primaryDark,
        secondary: secondary,
        onSecondary: Colors.white,
        secondaryContainer: secondaryLight,
        onSecondaryContainer: secondaryDark,
        tertiary: accent,
        onTertiary: Colors.white,
        tertiaryContainer: accentLight,
        onTertiaryContainer: accentDark,
        surface: surfaceLight,
        onSurface: textPrimaryLight,
        surfaceContainerHighest: surfaceHighlightLight,
        error: error,
        onError: Colors.white,
        errorContainer: errorLight,
        onErrorContainer: error,
        outline: borderLight,
        outlineVariant: borderSubtle,
      ),
      cardTheme: CardThemeData(
        color: surfaceLight,
        elevation: 0,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(12),
          side: const BorderSide(color: borderLight, width: 1),
        ),
        margin: EdgeInsets.zero,
      ),
      dividerTheme: const DividerThemeData(
        color: borderLight,
        thickness: 1,
        space: 1,
      ),
      appBarTheme: const AppBarTheme(
        backgroundColor: bgLight,
        foregroundColor: textPrimaryLight,
        elevation: 0,
        centerTitle: false,
        scrolledUnderElevation: 0,
      ),
      inputDecorationTheme: InputDecorationTheme(
        filled: true,
        fillColor: surfaceLight,
        contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
        border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(10),
          borderSide: const BorderSide(color: borderLight),
        ),
        enabledBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(10),
          borderSide: const BorderSide(color: borderLight),
        ),
        focusedBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(10),
          borderSide: const BorderSide(color: primary, width: 1.5),
        ),
        hintStyle: const TextStyle(color: textMuted, fontSize: 14),
      ),
      elevatedButtonTheme: ElevatedButtonThemeData(
        style: ElevatedButton.styleFrom(
          backgroundColor: primary,
          foregroundColor: Colors.white,
          elevation: 0,
          padding: const EdgeInsets.symmetric(horizontal: 18, vertical: 12),
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
          textStyle: const TextStyle(fontWeight: FontWeight.w600, fontSize: 13),
        ),
      ),
      outlinedButtonTheme: OutlinedButtonThemeData(
        style: OutlinedButton.styleFrom(
          foregroundColor: textPrimaryLight,
          side: const BorderSide(color: borderLight),
          padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
          textStyle: const TextStyle(fontWeight: FontWeight.w500, fontSize: 13),
        ),
      ),
      fontFamily: 'Inter',
    );
  }

  static ThemeData dark() => light(); // Enforce light design system
}

