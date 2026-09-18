"""
tools.platforms.windows — Windows Platform Adapter (V8)
"""

from __future__ import annotations

import os
import platform
from typing import Any

from tools.platforms.base import BasePlatformAdapter
from tools.types import PlatformOS


class WindowsAdapter(BasePlatformAdapter):
    """Windows implementation for desktop and system operations."""

    _clipboard_buffer: str = ""

    @property
    def platform_os(self) -> PlatformOS:
        return PlatformOS.WINDOWS

    async def get_system_info(self) -> dict[str, Any]:
        return {
            "os": "Windows",
            "release": platform.release(),
            "version": platform.version(),
            "architecture": platform.machine(),
            "cpu_count": os.cpu_count() or 1,
            "hostname": platform.node(),
            "desktop_env": "Windows Explorer",
        }

    async def launch_app(self, app_name: str, args: list[str] | None = None) -> dict[str, Any]:
        return {"launched": True, "app": app_name, "args": args or []}

    async def read_clipboard(self) -> str:
        return self._clipboard_buffer

    async def write_clipboard(self, text: str) -> bool:
        self._clipboard_buffer = text
        return True

    async def send_notification(self, title: str, message: str) -> bool:
        return True

    async def list_windows(self) -> list[dict[str, Any]]:
        return [
            {"id": "win_01", "title": "Kora Agent Desktop", "active": True},
        ]

    async def focus_window(self, window_identifier: str) -> bool:
        return True

    async def capture_screen(self, output_path: str | None = None) -> str:
        return output_path or "C:\\temp\\kora_screenshot.png"
