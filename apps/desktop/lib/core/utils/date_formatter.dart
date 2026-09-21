import 'package:intl/intl.dart';

/// Formatter utilities for dates and timestamps
class DateFormatter {
  static final DateFormat _timeFormat = DateFormat('HH:mm:ss');
  static final DateFormat _shortTimeFormat = DateFormat('HH:mm');
  static final DateFormat _dateTimeFormat = DateFormat('MMM dd, yyyy HH:mm');

  static String formatTime(DateTime dateTime) {
    return _timeFormat.format(dateTime.toLocal());
  }

  static String formatShortTime(DateTime dateTime) {
    return _shortTimeFormat.format(dateTime.toLocal());
  }

  static String formatDateTime(DateTime dateTime) {
    return _dateTimeFormat.format(dateTime.toLocal());
  }

  static String formatIso(String isoString) {
    try {
      final dt = DateTime.parse(isoString);
      return formatDateTime(dt);
    } catch (_) {
      return isoString;
    }
  }
}
