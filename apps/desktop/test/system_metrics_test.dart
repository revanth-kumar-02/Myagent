import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:kora_desktop/models/system_metrics_model.dart';
import 'package:kora_desktop/services/kora_api_service.dart';
import 'package:kora_desktop/services/kora_socket_service.dart';
import 'package:kora_desktop/state/connection_state.dart';
import 'package:kora_desktop/state/system_metrics_state.dart';
import 'package:kora_desktop/widgets/header_system_indicator.dart';
import 'package:kora_desktop/widgets/system_details_modal.dart';
import 'package:kora_desktop/widgets/system_status_card.dart';

void main() {
  group('SystemMetrics Model Tests', () {
    test('SystemMetrics fromJson parses complete telemetry payload', () {
      final json = {
        'timestamp': '2026-09-25T07:08:17Z',
        'os': 'Linux',
        'os_release': '7.0.0-30-generic',
        'cpu': {
          'percent': 34.5,
          'cores_logical': 8,
          'cores_physical': 4,
          'frequency_mhz': 2400.0,
          'temperature_c': 52.0,
        },
        'memory': {
          'percent': 58.2,
          'used_bytes': 9800000000,
          'available_bytes': 6200000000,
          'total_bytes': 16000000000,
          'used_gb': 9.8,
          'total_gb': 16.0,
          'available_gb': 6.2,
        },
        'disk': {
          'percent': 72.0,
          'used_bytes': 362000000000,
          'available_bytes': 150000000000,
          'total_bytes': 512000000000,
          'used_gb': 362.0,
          'total_gb': 512.0,
          'available_gb': 150.0,
          'mount_point': '/',
        },
        'network': {
          'download_rate_bps': 2516582.4,
          'upload_rate_bps': 348160.0,
          'download_rate_formatted': '2.4 MB/s',
          'upload_rate_formatted': '340 KB/s',
          'total_bytes_recv': 2000000000,
          'total_bytes_sent': 500000000,
        },
        'processes': {'count': 285},
        'gpu': {
          'available': true,
          'name': 'NVIDIA RTX 3080',
          'utilization_percent': 18.0,
          'vram_used_mb': 2100.0,
          'vram_total_mb': 10240.0,
        },
        'load': {
          'is_heavy_load': false,
          'summary': 'Normal',
        },
      };

      final metrics = SystemMetrics.fromJson(json);

      expect(metrics.os, equals('Linux'));
      expect(metrics.cpu.percent, equals(34.5));
      expect(metrics.cpu.coresLogical, equals(8));
      expect(metrics.cpu.normalizedRatio, closeTo(0.345, 0.001));

      expect(metrics.memory.percent, equals(58.2));
      expect(metrics.memory.usedGb, equals(9.8));
      expect(metrics.memory.totalGb, equals(16.0));
      expect(metrics.memory.normalizedRatio, closeTo(0.582, 0.001));

      expect(metrics.disk.percent, equals(72.0));
      expect(metrics.disk.usedGb, equals(362.0));
      expect(metrics.disk.mountPoint, equals('/'));

      expect(metrics.network.downloadRateFormatted, equals('2.4 MB/s'));
      expect(metrics.network.uploadRateFormatted, equals('340 KB/s'));

      expect(metrics.gpu.available, isTrue);
      expect(metrics.gpu.name, equals('NVIDIA RTX 3080'));
      expect(metrics.isHeavyLoad, isFalse);
    });
  });

  group('System Telemetry UI Widget Tests', () {
    testWidgets('HeaderSystemIndicator displays CPU and RAM percentages', (tester) async {
      final sampleMetrics = SystemMetrics(
        timestamp: '2026-09-25T07:08:17Z',
        os: 'Linux',
        osRelease: '7.0',
        cpu: const CpuMetrics(percent: 34.0, coresLogical: 8, coresPhysical: 4),
        memory: const MemoryMetrics(percent: 58.0, usedBytes: 0, availableBytes: 0, totalBytes: 0, usedGb: 9.8, totalGb: 16.0, availableGb: 6.2),
        disk: const DiskMetrics(percent: 72.0, usedBytes: 0, availableBytes: 0, totalBytes: 0, usedGb: 362.0, totalGb: 512.0, availableGb: 150.0, mountPoint: '/'),
        network: const NetworkMetrics(downloadRateBps: 0, uploadRateBps: 0, downloadRateFormatted: '2.4 MB/s', uploadRateFormatted: '340 KB/s', totalBytesRecv: 0, totalBytesSent: 0),
        processesCount: 300,
        gpu: const GpuMetrics(available: false),
        isHeavyLoad: false,
        loadSummary: 'Normal',
      );

      await tester.pumpWidget(
        ProviderScope(
          overrides: [
            systemMetricsProvider.overrideWith((ref) => _MockSystemMetricsNotifier(sampleMetrics)),
          ],
          child: const MaterialApp(
            home: Scaffold(
              body: HeaderSystemIndicator(),
            ),
          ),
        ),
      );

      await tester.pumpAndSettle();

      expect(find.text('CPU '), findsOneWidget);
      expect(find.text('34%'), findsOneWidget);
      expect(find.text('RAM '), findsOneWidget);
      expect(find.text('58%'), findsOneWidget);

      // Tapping it opens SystemDetailsModal
      await tester.tap(find.byType(HeaderSystemIndicator));
      await tester.pumpAndSettle();

      expect(find.byType(SystemDetailsModal), findsOneWidget);
      expect(find.text('Host System Telemetry'), findsOneWidget);
      expect(find.text('2.4 MB/s'), findsOneWidget);
      expect(find.text('340 KB/s'), findsOneWidget);
    });

    testWidgets('SystemStatusCard renders compact live telemetry card', (tester) async {
      final sampleMetrics = SystemMetrics(
        timestamp: '2026-09-25T07:08:17Z',
        os: 'Linux',
        osRelease: '7.0',
        cpu: const CpuMetrics(percent: 78.0, coresLogical: 8, coresPhysical: 4),
        memory: const MemoryMetrics(percent: 61.0, usedBytes: 0, availableBytes: 0, totalBytes: 0, usedGb: 9.8, totalGb: 16.0, availableGb: 6.2),
        disk: const DiskMetrics(percent: 72.0, usedBytes: 0, availableBytes: 0, totalBytes: 0, usedGb: 362.0, totalGb: 512.0, availableGb: 150.0, mountPoint: '/'),
        network: const NetworkMetrics(downloadRateBps: 0, uploadRateBps: 0, downloadRateFormatted: '2.4 MB/s', uploadRateFormatted: '340 KB/s', totalBytesRecv: 0, totalBytesSent: 0),
        processesCount: 300,
        gpu: const GpuMetrics(available: false),
        isHeavyLoad: false,
        loadSummary: 'Normal',
      );

      await tester.pumpWidget(
        ProviderScope(
          overrides: [
            systemMetricsProvider.overrideWith((ref) => _MockSystemMetricsNotifier(sampleMetrics)),
          ],
          child: const MaterialApp(
            home: Scaffold(
              body: SystemStatusCard(),
            ),
          ),
        ),
      );

      await tester.pumpAndSettle();

      expect(find.text('SYSTEM / HOST MACHINE'), findsOneWidget);
      expect(find.text('CPU'), findsOneWidget);
      expect(find.text('78%'), findsOneWidget);
      expect(find.text('8 cores'), findsOneWidget);

      expect(find.text('MEMORY'), findsOneWidget);
      expect(find.text('61%'), findsOneWidget);
      expect(find.text('9.8 / 16.0 GB'), findsOneWidget);

      expect(find.text('DISK'), findsOneWidget);
      expect(find.text('72%'), findsOneWidget);
      expect(find.text('362.0 / 512.0 GB'), findsOneWidget);

      expect(find.text('NETWORK'), findsOneWidget);
      expect(find.text('2.4 MB/s'), findsOneWidget);
      expect(find.text('340 KB/s'), findsOneWidget);
    });
  });
}

class _MockSystemMetricsNotifier extends StateNotifier<SystemMetricsState>
    implements SystemMetricsNotifier {
  _MockSystemMetricsNotifier(SystemMetrics initialMetrics)
      : super(SystemMetricsState(metrics: initialMetrics, isLiveStreaming: true));

  @override
  Future<void> refresh() async {}
}
