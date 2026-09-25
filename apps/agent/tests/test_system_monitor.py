"""
tests.test_system_monitor — Tests for Real-Time System Resource Monitoring (Reqs 14–22)
"""

import asyncio
import os
import platform
import pytest
from httpx import AsyncClient, ASGITransport

from main import app
from observability.system_monitor import SystemMonitor, get_system_monitor


def test_system_monitor_collects_actual_host_metrics():
    """Verify monitor queries host OS psutil without hardcoding."""
    monitor = SystemMonitor(interval_seconds=1.0)
    metrics = monitor.get_latest_metrics()

    # Core required keys (Req 14)
    assert "cpu" in metrics
    assert "memory" in metrics
    assert "disk" in metrics
    assert "network" in metrics
    assert "processes" in metrics
    assert "gpu" in metrics
    assert "load" in metrics

    # CPU metrics
    cpu = metrics["cpu"]
    assert isinstance(cpu["percent"], (int, float))
    assert 0.0 <= cpu["percent"] <= 100.0
    assert cpu["cores_logical"] >= 1
    assert cpu["cores_physical"] >= 1

    # RAM metrics (used, available, total, percent)
    mem = metrics["memory"]
    assert 0.0 <= mem["percent"] <= 100.0
    assert mem["total_bytes"] > 0
    assert mem["used_bytes"] > 0
    assert mem["available_bytes"] > 0
    assert mem["total_gb"] > 0.0

    # Disk metrics (used, available, total, percent, mount)
    disk = metrics["disk"]
    assert 0.0 <= disk["percent"] <= 100.0
    assert disk["total_bytes"] > 0
    assert disk["mount_point"] in ["/", "C:\\", os.path.abspath(os.sep)]

    # Network metrics
    net = metrics["network"]
    assert "download_rate_formatted" in net
    assert "upload_rate_formatted" in net
    assert net["total_bytes_recv"] >= 0
    assert net["total_bytes_sent"] >= 0

    # OS detection
    assert metrics["os"] == platform.system()


def test_heavy_load_detection_and_agent_awareness():
    """Verify resource-aware agent detection (Req 21)."""
    monitor = SystemMonitor(interval_seconds=1.0)
    # Default state
    is_heavy = monitor.is_system_under_heavy_load()
    assert isinstance(is_heavy, bool)


def test_threshold_alerts_and_activity_integration():
    """Verify activity warnings trigger only on genuine threshold transitions (Req 18)."""
    recorded_events: list[tuple[str, str]] = []

    def mock_record_warning(event_type: str, details: str):
        recorded_events.append((event_type, details))

    monitor = SystemMonitor(
        interval_seconds=0.1,
        activity_recorder=mock_record_warning,
    )

    # 1. Normal state -> no warnings
    normal_metrics = {
        "cpu": {"percent": 25.0},
        "memory": {"percent": 45.0, "used_gb": 4.0, "total_gb": 16.0},
        "disk": {"percent": 50.0, "available_gb": 200.0},
    }
    monitor._check_thresholds(normal_metrics)
    assert len(recorded_events) == 0

    # 2. Memory threshold crossed (> 90%)
    high_mem_metrics = {
        "cpu": {"percent": 25.0},
        "memory": {"percent": 93.5, "used_gb": 15.0, "total_gb": 16.0},
        "disk": {"percent": 50.0, "available_gb": 200.0},
    }
    monitor._check_thresholds(high_mem_metrics)
    assert len(recorded_events) == 1
    assert recorded_events[0][0] == "SYSTEM_WARNING"
    assert "Memory usage exceeded 90%" in recorded_events[0][1]

    # Repeated high memory tick must NOT duplicate the warning (debounced)
    monitor._check_thresholds(high_mem_metrics)
    assert len(recorded_events) == 1

    # 3. Memory recovery below 80%
    recovered_mem_metrics = {
        "cpu": {"percent": 25.0},
        "memory": {"percent": 75.0, "used_gb": 12.0, "total_gb": 16.0},
        "disk": {"percent": 50.0, "available_gb": 200.0},
    }
    monitor._check_thresholds(recovered_mem_metrics)
    assert len(recorded_events) == 2
    assert recorded_events[1][0] == "SYSTEM_RECOVERED"
    assert "Memory usage returned below threshold" in recorded_events[1][1]


@pytest.mark.asyncio
async def test_system_metrics_api_endpoints():
    """Verify GET /api/system/metrics and /api/system/load REST endpoints."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/system/metrics")
        assert resp.status_code == 200
        data = resp.json()
        assert "cpu" in data
        assert "memory" in data
        assert "disk" in data
        assert "network" in data

        load_resp = await client.get("/api/system/load")
        assert load_resp.status_code == 200
        load_data = load_resp.json()
        assert "is_heavy_load" in load_data
        assert "cpu_percent" in load_data
        assert "ram_percent" in load_data
        assert "load_summary" in load_data
