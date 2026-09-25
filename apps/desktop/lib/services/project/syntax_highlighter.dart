import 'package:flutter/material.dart';
import '../../core/theme/app_theme.dart';

/// Lightweight syntax tokenizer that generates highlighted TextSpans
/// preserving all indentation and whitespace.
class SyntaxHighlighter {
  static const Set<String> _keywords = {
    // Control flow
    'if', 'else', 'elif', 'for', 'while', 'do', 'switch', 'case', 'default',
    'break', 'continue', 'return', 'yield', 'try', 'catch', 'finally', 'throw',
    'raise', 'except', 'with', 'match',

    // Declarations & OOP
    'class', 'struct', 'enum', 'trait', 'interface', 'extends', 'implements',
    'mixin', 'type', 'typedef', 'def', 'fn', 'function', 'pub',
    'static', 'final', 'const', 'var', 'let', 'val', 'mut', 'abstract',
    'override', 'operator', 'getter', 'setter',

    // Imports & namespaces
    'import', 'export', 'from', 'as', 'package', 'library', 'part', 'use', 'mod',
    'namespace', 'include', 'require',

    // Visibility & modifiers
    'public', 'private', 'protected', 'internal', 'async', 'await', 'sync',
    'native', 'extern', 'inline', 'virtual', 'explicit',

    // Literals & primitives
    'true', 'false', 'null', 'nil', 'None', 'undefined', 'this', 'self', 'super',
    'void', 'int', 'float', 'double', 'bool', 'char', 'string', 'str',
    'int32', 'int64', 'uint', 'usize', 'isize',
  };

  /// Builds a List of highlighted TextSpans for a given single line of code.
  static TextSpan highlightLine(
    String line,
    KoraColors c, {
    String language = '',
    bool isDark = false,
  }) {
    if (line.isEmpty) {
      return const TextSpan(text: '\n');
    }

    final spans = <TextSpan>[];
    final commentChar = (language.toLowerCase() == 'python' || language.toLowerCase() == 'yaml' || language.toLowerCase() == 'toml')
        ? '#'
        : '//';

    int i = 0;
    final len = line.length;

    // Palette tokens
    final keywordColor = isDark ? const Color(0xFF68D391) : c.primary;
    final stringColor = isDark ? const Color(0xFFF6AD55) : const Color(0xFF2D6A4F);
    final commentColor = isDark ? const Color(0xFF718096) : const Color(0xFF8D99AE);
    final numberColor = isDark ? const Color(0xFFFAF089) : const Color(0xFFC05621);
    final typeColor = isDark ? const Color(0xFF63B3ED) : const Color(0xFF0F766E);
    final plainColor = c.textPrimary;

    while (i < len) {
      // 1. Check for single-line comments
      if (line.startsWith(commentChar, i) || (commentChar == '//' && line.startsWith('#', i) && language.isEmpty)) {
        spans.add(TextSpan(
          text: line.substring(i),
          style: TextStyle(color: commentColor, fontStyle: FontStyle.italic),
        ));
        break;
      }

      final char = line[i];

      // 2. Check for strings (single, double, or backtick)
      if (char == '"' || char == "'" || char == '`') {
        final quote = char;
        int end = i + 1;
        while (end < len) {
          if (line[end] == '\\') {
            end += 2; // skip escaped character
            continue;
          }
          if (line[end] == quote) {
            end++;
            break;
          }
          end++;
        }
        if (end > len) end = len;
        spans.add(TextSpan(
          text: line.substring(i, end),
          style: TextStyle(color: stringColor),
        ));
        i = end;
        continue;
      }

      // 3. Check for numbers
      if (_isDigit(char) && (i == 0 || !_isIdentChar(line[i - 1]))) {
        int end = i + 1;
        while (end < len && (_isDigit(line[end]) || line[end] == '.' || line[end] == 'x' || _isHexDigit(line[end]))) {
          end++;
        }
        spans.add(TextSpan(
          text: line.substring(i, end),
          style: TextStyle(color: numberColor),
        ));
        i = end;
        continue;
      }

      // 4. Check for identifiers and keywords
      if (_isIdentStart(char)) {
        int end = i + 1;
        while (end < len && _isIdentChar(line[end])) {
          end++;
        }
        final word = line.substring(i, end);

        if (_keywords.contains(word)) {
          spans.add(TextSpan(
            text: word,
            style: TextStyle(color: keywordColor, fontWeight: FontWeight.w600),
          ));
        } else if (_isType(word)) {
          spans.add(TextSpan(
            text: word,
            style: TextStyle(color: typeColor, fontWeight: FontWeight.w500),
          ));
        } else {
          spans.add(TextSpan(
            text: word,
            style: TextStyle(color: plainColor),
          ));
        }
        i = end;
        continue;
      }

      // 5. Annotations / Decorators (@annotation)
      if (char == '@' && i + 1 < len && _isIdentStart(line[i + 1])) {
        int end = i + 1;
        while (end < len && _isIdentChar(line[end])) {
          end++;
        }
        spans.add(TextSpan(
          text: line.substring(i, end),
          style: TextStyle(color: isDark ? const Color(0xFFF687B3) : const Color(0xFF9F580A)),
        ));
        i = end;
        continue;
      }

      // 6. Operators, whitespace, punctuation
      spans.add(TextSpan(
        text: char,
        style: TextStyle(color: plainColor),
      ));
      i++;
    }

    return TextSpan(children: spans);
  }

  static bool _isDigit(String c) {
    if (c.isEmpty) return false;
    final code = c.codeUnitAt(0);
    return code >= 48 && code <= 57;
  }

  static bool _isHexDigit(String c) {
    if (c.isEmpty) return false;
    final code = c.codeUnitAt(0);
    return (code >= 48 && code <= 57) || (code >= 65 && code <= 70) || (code >= 97 && code <= 102);
  }

  static bool _isIdentStart(String c) {
    if (c.isEmpty) return false;
    final code = c.codeUnitAt(0);
    return (code >= 65 && code <= 90) || (code >= 97 && code <= 122) || code == 95 || code == 36; // A-Z, a-z, _, $
  }

  static bool _isIdentChar(String c) {
    if (c.isEmpty) return false;
    final code = c.codeUnitAt(0);
    return (code >= 65 && code <= 90) || (code >= 97 && code <= 122) || (code >= 48 && code <= 57) || code == 95 || code == 36;
  }

  static bool _isType(String word) {
    if (word.isEmpty) return false;
    final first = word[0];
    return first == first.toUpperCase() && first != first.toLowerCase() && word.length > 1;
  }
}
