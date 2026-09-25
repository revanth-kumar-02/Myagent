"""
observability.system_monitor — Real-Time Host System Telemetry & Monitor.

Collects actual, un-faked host machine resource metrics via psutil:
  - CPU usage % (logical & physical cores, clock frequency, core temperature)
  - RAM usage % (used, available, total, percentage)
  - Disk usage % (used, available, total, percentage, mount path)
  - Network I/O rate (realtime bytes/sec, formatted upload/download rate)
  - Process count
  - GPU telemetry (via nvidia-smi if available, gracefully optional)
  - Heavy load detection (for resource-aware agent decisions)
  - Threshold alert manager (SYSTEM_WARNING, SYSTEM_RECOVERED with debounce)

Streams telemetry over WebSocket every 1.5–2.0 seconds to connected desktop clients.
Runs completely offline without external APIs or cloud dependencies.
"""

from __future__ import annotations

import asyncio
import os
import platform
import shutil
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Callable

import psutil
import structlog

logger = structlog.get_logger(__name__)


def _format_rate(bytes_per_sec: float) -> str:
    """Format network bandwidth rate into human-readable MB/s or KB/s."""
    if bytes_per_sec >= 1024 * 1024:
        return f"{bytes_per_sec / (1024 * 1024):.1f} MB/s"
    elif bytes_per_sec >= 1024:
        return f"{bytes_per_sec / 1024:.1f} KB/s"
    else:
        return f"{bytes_per_sec:.0f} B/s"


def _format_bytes(num_bytes: int | float) -> str:
    """Format byte quantity into GB or MB."""
    gb = num_bytes / (1024 ** 3)
    if gb >= 1.0:
        return f"{gb:.1f} GB"
    mb = num_bytes / (1024 ** 2)
    return f"{mb:.1f} MB"


class SystemMonitor:
    """
    Lightweight background monitor for host hardware telemetry.
    Collects real CPU, RAM, Disk, Network, and GPU metrics every ~1.5s.
    """

    def __init__(
        self,
        interval_seconds: float = 1.5,
        broadcast_func: Callable[[dict[str, Any]], Any] | None = None,
        activity_recorder: Callable[[str, str], Any] | None = None,
    ) -> None:
        self.interval_seconds = interval_seconds
        self._broadcast_func = broadcast_func
        self._activity_recorder = activity_recorder
        self._task: asyncio.Task[None] | None = None
        self._running = False

        # Previous network snapshot for rate diffing
        self._last_net_time: float = time.monotonic()
        self._last_net_bytes_recv: int = 0
        self._last_net_bytes_sent: int = 0

        # Prime network counters
        try:
            net_io = psutil.net_io_counters()
            self._last_net_bytes_recv = net_io.bytes_recv
            self._last_net_bytes_sent = net_io.bytes_sent
        except Exception:
            pass

        # Prime CPU calculation (interval=None enables non-blocking delta calls)
        try:
            psutil.cpu_percent(interval=None)
        except Exception:
            pass

        # Threshold tracking state for Activity Events
        self._cpu_high_ticks: int = 0
        self._cpu_warning_active: bool = False
        self._ram_warning_active: bool = False
        self._disk_warning_active: bool = False

        # Cached latest metrics snapshot
        self._latest_metrics: dict[str, Any] = self._sample_metrics(delta_time=1.0)

    @property
    def is_running(self) -> bool:
        return self._running

    def set_broadcaster(self, broadcast_func: Callable[[dict[str, Any]], Any]) -> None:
        self._broadcast_func = broadcast_func

    def set_activity_recorder(self, activity_recorder: Callable[[str, str], Any]) -> None:
        self._activity_recorder = activity_recorder

    def get_latest_metrics(self) -> dict[str, Any]:
        """Return the most recently collected metrics snapshot."""
        return self._latest_metrics

    def is_system_under_heavy_load(self) -> bool:
        """
        Resource-aware check: returns True if the host is experiencing high CPU or RAM pressure.
        Can be queried by Agent Planner or Executor before launching compute-heavy jobs.
        """
        cpu_pct = self._latest_metrics.get("cpu", {}).get("percent", 0.0)
        ram_pct = self._latest_metrics.get("memory", {}).get("percent", 0.0)
        return cpu_pct >= 85.0 or ram_pct >= 90.0

    def start(self) -> None:
        """Start the background monitoring loop."""
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._run_loop(), name="kora-system-monitor")
        logger.info("system_monitor_started", interval=self.interval_seconds)

    def stop(self) -> None:
        """Stop the background monitoring loop."""
        self._running = False
        if self._task and not self._task.done():
            self._task.cancel()
        self._task = None
        logger.info("system_monitor_stopped")

    async def _run_loop(self) -> None:
        """Main loop: periodically sample metrics, verify thresholds, and broadcast."""
        while self._running:
            try:
                await asyncio.sleep(self.interval_seconds)
                now = time.monotonic()
                dt = max(now - self._last_net_time, 0.001)

                # Sample metrics
                metrics = self._sample_metrics(delta_time=dt)
                self._latest_metrics = metrics
                self._last_net_time = now

                # Check thresholds and trigger activity warnings if needed
                self._check_thresholds(metrics)

                # Stream to WebSocket clients
                if self._broadcast_func:
                    payload = {
                        "type": "SYSTEM_METRICS",
                        "payload": metrics,
                    }
                    if asyncio.iscoroutinefunction(self._broadcast_func):
                        await self._broadcast_func(payload)
                    else:
                        self._broadcast_func(payload)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.debug("system_monitor_tick_error", error=str(e))
                await asyncio.sleep(1.0)

    def _sample_metrics(self, delta_time: float) -> dict[str, Any]:
        """Collect real-time hardware telemetry."""
        # 1. CPU
        cpu_percent = psutil.cpu_percent(interval=None)
        logical_cores = psutil.cpu_count(logical=True) or 1
        physical_cores = psutil.cpu_count(logical=False) or 1

        freq_mhz = None
        try:
            freq = psutil.cpu_freq()
            if freq:
                freq_mhz = round(freq.current, 1)
        except Exception:
            pass

        cpu_temp_c = None
        try:
            temps = psutil.sensors_temperatures()
            if temps:
                if "coretemp" in temps and temps["coretemp"]:
                    cpu_temp_c = round(temps["coretemp"][0].current, 1)
                elif "cpu_thermal" in temps and temps["cpu_thermal"]:
                    cpu_temp_c = round(temps["cpu_thermal"][0].current, 1)
                else:
                    first_sensor = next(iter(temps.values()))
                    if first_sensor:
                        cpu_temp_c = round(first_sensor[0].current, 1)
        except Exception:
            pass

        # 2. Memory (RAM)
        vmem = psutil.virtual_memory()
        ram_percent = vmem.percent
        ram_total = vmem.total
        ram_used = vmem.used
        ram_available = vmem.available
        ram_used_gb = round(ram_used / (1024 ** 3), 2)
        ram_total_gb = round(ram_total / (1024 ** 3), 2)
        ram_available_gb = round(ram_available / (1024 ** 3), 2)

        # 3. Disk
        root_path = os.path.abspath(os.sep)
        disk_usage = psutil.disk_usage(root_path)
        disk_percent = disk_usage.percent
        disk_total = disk_usage.total
        disk_used = disk_usage.used
        disk_free = disk_usage.free
        disk_total_gb = round(disk_total / (1024 ** 3), 1)
        disk_used_gb = round(disk_used / (1024 ** 3), 1)
        disk_free_gb = round(disk_free / (1024 ** 3), 1)

        # 4. Network I/O
        down_rate_bps = 0.0
        up_rate_bps = 0.0
        total_recv = 0
        total_sent = 0
        try:
            net_io = psutil.net_io_counters()
            total_recv = net_io.bytes_recv
            total_sent = net_io.bytes_sent
            if self._last_net_bytes_recv > 0 and delta_time > 0:
                down_rate_bps = max(0.0, (total_recv - self._last_net_bytes_recv) / delta_time)
                up_rate_bps = max(0.0, (total_sent - self._last_net_bytes_sent) / delta_time)
            self._last_net_bytes_recv = total_recv
            self._last_net_bytes_sent = total_sent
        except Exception:
            pass

        # 5. Processes
        process_count = 0
        try:
            process_count = len(psutil.pids())
        except Exception:
            pass

        # 6. GPU (Optional & Non-blocking detection)
        gpu_info = self._detect_gpu()

        # 7. Overall System Status
        is_heavy = cpu_percent >= 85.0 or ram_percent >= 90.0
        if cpu_percent >= 90.0 or ram_percent >= 92.0:
            load_status = "Critical Load"
        elif is_heavy:
            load_status = "Heavy Load"
        elif cpu_percent >= 60.0 or ram_percent >= 75.0:
            load_status = "Elevated"
        else:
            load_status = "Normal"

        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "os": platform.system(),
            "os_release": platform.release(),
            "cpu": {
                "percent": round(cpu_percent, 1),
                "cores_logical": logical_cores,
                "cores_physical": physical_cores,
                "frequency_mhz": freq_mhz,
                "temperature_c": cpu_temp_c,
            },
            "memory": {
                "percent": round(ram_percent, 1),
                "used_bytes": ram_used,
                "available_bytes": ram_available,
                "total_bytes": ram_total,
                "used_gb": ram_used_gb,
                "total_gb": ram_total_gb,
                "available_gb": ram_available_gb,
            },
            "disk": {
                "percent": round(disk_percent, 1),
                "used_bytes": disk_used,
                "available_bytes": disk_free,
                "total_bytes": disk_total,
                "used_gb": disk_used_gb,
                "total_gb": disk_total_gb,
                "available_gb": disk_free_gb,
                "mount_point": root_path,
            },
            "network": {
                "download_rate_bps": round(down_rate_bps, 1),
                "upload_rate_bps": round(up_rate_bps, 1),
                "download_rate_formatted": _format_rate(down_rate_bps),
                "upload_rate_formatted": _format_rate(up_rate_bps),
                "total_bytes_recv": total_recv,
                "total_bytes_sent": total_sent,
            },
            "processes": {
                "count": process_count,
            },
            "gpu": gpu_info,
            "load": {
                "is_heavy_load": is_heavy,
                "summary": load_status,
            },
        }

    def _detect_gpu(self) -> dict[str, Any]:
        """Check for local GPU metrics (e.g. nvidia-smi), fallback gracefully."""
        nvidia_path = shutil.which("nvidia-smi")
        if not nvidia_path:
            return {
                "available": False,
                "name": None,
                "utilization_percent": None,
                "vram_used_mb": None,
                "vram_total_mb": None,
            }

        try:
            import subprocess
            out = subprocess.check_output(
                [
                    nvidia_path,
                    "--query-gpu=name,utilization.gpu,memory.used,memory.total",
                    "--format=csv,noheader,nounits",
                ],
                stderr=subprocess.DEVNULL,
                timeout=0.6,
                text=True,
            ).strip()
            if out:
                lines = out.split("\n")
                first = lines[0].split(",")
                if len(first) >= 4:
                    return {
                        "available": True,
                        "name": first[0].strip(),
                        "utilization_percent": float(first[1].strip()),
                        "vram_used_mb": float(first[2].strip()),
                        "vram_total_mb": float(first[3].strip()),
                    }
        except Exception:
            pass

        return {
            "available": False,
            "name": None,
            "utilization_percent": None,
            "vram_used_mb": None,
            "vram_total_mb": None,
        }

    def _check_thresholds(self, metrics: dict[str, Any]) -> None:
        """
        Threshold detection with hysteresis and debounce.
        Only generates Activity events on state transitions (never every tick).
        """
        cpu_pct = metrics["cpu"]["percent"]
        ram_pct = metrics["memory"]["percent"]
        disk_pct = metrics["disk"]["percent"]
        disk_free_gb = metrics["disk"]["available_gb"]

        # CPU Threshold: sustained > 90% for ~15 ticks (~22s)
        if cpu_pct >= 90.0:
            self._cpu_high_ticks += 1
            if self._cpu_high_ticks >= 15 and not self._cpu_warning_active:
                self._cpu_warning_active = True
                self._record_warning(
                    "SYSTEM_WARNING",
                    f"CPU usage exceeded 90% for 30 seconds ({cpu_pct}%)",
                )
        else:
            if cpu_pct < 80.0 and self._cpu_warning_active:
                self._cpu_warning_active = False
                self._cpu_high_ticks = 0
                self._record_warning(
                    "SYSTEM_RECOVERED",
                    f"CPU usage normalized below threshold ({cpu_pct}%)",
                )
            elif not self._cpu_warning_active:
                self._cpu_high_ticks = max(0, self._cpu_high_ticks - 1)

        # RAM Threshold: > 90%
        if ram_pct >= 90.0 and not self._ram_warning_active:
            self._ram_warning_active = True
            used_gb = metrics["memory"]["used_gb"]
            total_gb = metrics["memory"]["total_gb"]
            self._record_warning(
                "SYSTEM_WARNING",
                f"Memory usage exceeded 90% ({ram_pct}%, {used_gb} GB / {total_gb} GB)",
            )
        elif ram_pct < 80.0 and self._ram_warning_active:
            self._ram_warning_active = False
            self._record_warning(
                "SYSTEM_RECOVERED",
                f"Memory usage returned below threshold ({ram_pct}%)",
            )

        # Disk Threshold: > 90% used
        if disk_pct >= 90.0 and not self._disk_warning_active:
            self._disk_warning_active = True
            self._record_warning(
                "SYSTEM_WARNING",
                f"Disk space below threshold ({disk_free_gb} GB free, {disk_pct}% used)",
            )
        elif disk_pct < 85.0 and self._disk_warning_active:
            self._disk_warning_active = False
            self._record_warning(
                "SYSTEM_RECOVERED",
                f"Disk space returned above threshold ({disk_free_gb} GB free)",
            )

    def _record_warning(self, event_type: str, details: str) -> None:
        """Dispatch warning to activity recorder."""
        logger.warn("system_threshold_alert", event_type=event_type, details=details)
        if self._activity_recorder:
            try:
                self._activity_recorder(event_type, details)
            except Exception as e:
                logger.debug("failed_to_record_system_warning", error=str(e))


# Global singleton instance
_system_monitor: SystemMonitor | None = None


def get_system_monitor() -> SystemMonitor:
    """Retrieve or initialize the global SystemMonitor singleton."""
    global _system_monitor
    if _system_monitor is None:
        from api.ws import broadcast_ws
        _system_monitor = SystemMonitor(
            interval_seconds=1.5,
            broadcast_func=broadcast_ws,
        )
    return _system_monitor
