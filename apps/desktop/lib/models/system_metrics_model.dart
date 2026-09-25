/// System metrics telemetry model for Kora host machine monitoring.

class CpuMetrics {
  final double percent;
  final int coresLogical;
  final int coresPhysical;
  final double? frequencyMhz;
  final double? temperatureC;

  const CpuMetrics({
    required this.percent,
    required this.coresLogical,
    required this.coresPhysical,
    this.frequencyMhz,
    this.temperatureC,
  });

  factory CpuMetrics.fromJson(Map<String, dynamic> json) {
    return CpuMetrics(
      percent: (json['percent'] as num?)?.toDouble() ?? 0.0,
      coresLogical: (json['cores_logical'] as num?)?.toInt() ?? 1,
      coresPhysical: (json['cores_physical'] as num?)?.toInt() ?? 1,
      frequencyMhz: (json['frequency_mhz'] as num?)?.toDouble(),
      temperatureC: (json['temperature_c'] as num?)?.toDouble(),
    );
  }

  double get normalizedRatio => (percent / 100.0).clamp(0.0, 1.0);
}

class MemoryMetrics {
  final double percent;
  final int usedBytes;
  final int availableBytes;
  final int totalBytes;
  final double usedGb;
  final double totalGb;
  final double availableGb;

  const MemoryMetrics({
    required this.percent,
    required this.usedBytes,
    required this.availableBytes,
    required this.totalBytes,
    required this.usedGb,
    required this.totalGb,
    required this.availableGb,
  });

  factory MemoryMetrics.fromJson(Map<String, dynamic> json) {
    return MemoryMetrics(
      percent: (json['percent'] as num?)?.toDouble() ?? 0.0,
      usedBytes: (json['used_bytes'] as num?)?.toInt() ?? 0,
      availableBytes: (json['available_bytes'] as num?)?.toInt() ?? 0,
      totalBytes: (json['total_bytes'] as num?)?.toInt() ?? 0,
      usedGb: (json['used_gb'] as num?)?.toDouble() ?? 0.0,
      totalGb: (json['total_gb'] as num?)?.toDouble() ?? 0.0,
      availableGb: (json['available_gb'] as num?)?.toDouble() ?? 0.0,
    );
  }

  double get normalizedRatio => (percent / 100.0).clamp(0.0, 1.0);
}

class DiskMetrics {
  final double percent;
  final int usedBytes;
  final int availableBytes;
  final int totalBytes;
  final double usedGb;
  final double totalGb;
  final double availableGb;
  final String mountPoint;

  const DiskMetrics({
    required this.percent,
    required this.usedBytes,
    required this.availableBytes,
    required this.totalBytes,
    required this.usedGb,
    required this.totalGb,
    required this.availableGb,
    required this.mountPoint,
  });

  factory DiskMetrics.fromJson(Map<String, dynamic> json) {
    return DiskMetrics(
      percent: (json['percent'] as num?)?.toDouble() ?? 0.0,
      usedBytes: (json['used_bytes'] as num?)?.toInt() ?? 0,
      availableBytes: (json['available_bytes'] as num?)?.toInt() ?? 0,
      totalBytes: (json['total_bytes'] as num?)?.toInt() ?? 0,
      usedGb: (json['used_gb'] as num?)?.toDouble() ?? 0.0,
      totalGb: (json['total_gb'] as num?)?.toDouble() ?? 0.0,
      availableGb: (json['available_gb'] as num?)?.toDouble() ?? 0.0,
      mountPoint: json['mount_point'] as String? ?? '/',
    );
  }

  double get normalizedRatio => (percent / 100.0).clamp(0.0, 1.0);
}

class NetworkMetrics {
  final double downloadRateBps;
  final double uploadRateBps;
  final String downloadRateFormatted;
  final String uploadRateFormatted;
  final int totalBytesRecv;
  final int totalBytesSent;

  const NetworkMetrics({
    required this.downloadRateBps,
    required this.uploadRateBps,
    required this.downloadRateFormatted,
    required this.uploadRateFormatted,
    required this.totalBytesRecv,
    required this.totalBytesSent,
  });

  factory NetworkMetrics.fromJson(Map<String, dynamic> json) {
    return NetworkMetrics(
      downloadRateBps: (json['download_rate_bps'] as num?)?.toDouble() ?? 0.0,
      uploadRateBps: (json['upload_rate_bps'] as num?)?.toDouble() ?? 0.0,
      downloadRateFormatted: json['download_rate_formatted'] as String? ?? '0 B/s',
      uploadRateFormatted: json['upload_rate_formatted'] as String? ?? '0 B/s',
      totalBytesRecv: (json['total_bytes_recv'] as num?)?.toInt() ?? 0,
      totalBytesSent: (json['total_bytes_sent'] as num?)?.toInt() ?? 0,
    );
  }
}

class GpuMetrics {
  final bool available;
  final String? name;
  final double? utilizationPercent;
  final double? vramUsedMb;
  final double? vramTotalMb;

  const GpuMetrics({
    required this.available,
    this.name,
    this.utilizationPercent,
    this.vramUsedMb,
    this.vramTotalMb,
  });

  factory GpuMetrics.fromJson(Map<String, dynamic> json) {
    return GpuMetrics(
      available: json['available'] as bool? ?? false,
      name: json['name'] as String?,
      utilizationPercent: (json['utilization_percent'] as num?)?.toDouble(),
      vramUsedMb: (json['vram_used_mb'] as num?)?.toDouble(),
      vramTotalMb: (json['vram_total_mb'] as num?)?.toDouble(),
    );
  }
}

class SystemMetrics {
  final String timestamp;
  final String os;
  final String osRelease;
  final CpuMetrics cpu;
  final MemoryMetrics memory;
  final DiskMetrics disk;
  final NetworkMetrics network;
  final int processesCount;
  final GpuMetrics gpu;
  final bool isHeavyLoad;
  final String loadSummary;

  const SystemMetrics({
    required this.timestamp,
    required this.os,
    required this.osRelease,
    required this.cpu,
    required this.memory,
    required this.disk,
    required this.network,
    required this.processesCount,
    required this.gpu,
    required this.isHeavyLoad,
    required this.loadSummary,
  });

  factory SystemMetrics.fromJson(Map<String, dynamic> json) {
    final cpuMap = json['cpu'] as Map<String, dynamic>? ?? {};
    final memMap = json['memory'] as Map<String, dynamic>? ?? {};
    final diskMap = json['disk'] as Map<String, dynamic>? ?? {};
    final netMap = json['network'] as Map<String, dynamic>? ?? {};
    final procMap = json['processes'] as Map<String, dynamic>? ?? {};
    final gpuMap = json['gpu'] as Map<String, dynamic>? ?? {};
    final loadMap = json['load'] as Map<String, dynamic>? ?? {};

    return SystemMetrics(
      timestamp: json['timestamp'] as String? ?? '',
      os: json['os'] as String? ?? 'Host',
      osRelease: json['os_release'] as String? ?? '',
      cpu: CpuMetrics.fromJson(cpuMap),
      memory: MemoryMetrics.fromJson(memMap),
      disk: DiskMetrics.fromJson(diskMap),
      network: NetworkMetrics.fromJson(netMap),
      processesCount: (procMap['count'] as num?)?.toInt() ?? 0,
      gpu: GpuMetrics.fromJson(gpuMap),
      isHeavyLoad: loadMap['is_heavy_load'] as bool? ?? false,
      loadSummary: loadMap['summary'] as String? ?? 'Normal',
    );
  }

  /// Empty fallback state for initial UI before first tick
  static SystemMetrics empty() {
    return const SystemMetrics(
      timestamp: '',
      os: 'Host OS',
      osRelease: '',
      cpu: CpuMetrics(percent: 0, coresLogical: 1, coresPhysical: 1),
      memory: MemoryMetrics(percent: 0, usedBytes: 0, availableBytes: 0, totalBytes: 0, usedGb: 0, totalGb: 0, availableGb: 0),
      disk: DiskMetrics(percent: 0, usedBytes: 0, availableBytes: 0, totalBytes: 0, usedGb: 0, totalGb: 0, availableGb: 0, mountPoint: '/'),
      network: NetworkMetrics(downloadRateBps: 0, uploadRateBps: 0, downloadRateFormatted: '0 B/s', uploadRateFormatted: '0 B/s', totalBytesRecv: 0, totalBytesSent: 0),
      processesCount: 0,
      gpu: GpuMetrics(available: false),
      isHeavyLoad: false,
      loadSummary: 'Normal',
    );
  }
}
