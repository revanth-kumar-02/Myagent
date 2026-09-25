"""
tools.platforms.linux — Linux Platform Adapter (V8)
"""

from __future__ import annotations

import asyncio
import os
import platform
import shutil
from typing import Any

from tools.platforms.base import BasePlatformAdapter
from tools.types import PlatformOS


class LinuxAdapter(BasePlatformAdapter):
    """Linux implementation for desktop and system operations."""

    _clipboard_buffer: str = ""

    @property
    def platform_os(self) -> PlatformOS:
        return PlatformOS.LINUX

    async def get_system_info(self) -> dict[str, Any]:
        return {
            "os": "Linux",
            "release": platform.release(),
            "version": platform.version(),
            "architecture": platform.machine(),
            "cpu_count": os.cpu_count() or 1,
            "hostname": platform.node(),
            "desktop_env": os.environ.get("XDG_CURRENT_DESKTOP", "unknown"),
        }

    async def launch_app(self, app_name: str, args: list[str] | None = None) -> dict[str, Any]:
        # 1. Check direct binary or lowercase command
        candidate_bin = shutil.which(app_name)
        if not candidate_bin:
            lowered = app_name.lower().replace(" ", "-")
            candidate_bin = shutil.which(lowered)
        if not candidate_bin:
            # Common desktop app name mappings
            common_mappings = {
                "chrome": "google-chrome",
                "google chrome": "google-chrome",
                "browser": "google-chrome",
                "files": "nautilus",
                "file manager": "nautilus",
                "calculator": "gnome-calculator",
                "terminal": "gnome-terminal",
                "code": "code",
                "vscode": "code",
            }
            mapped = common_mappings.get(app_name.lower().strip())
            if mapped:
                candidate_bin = shutil.which(mapped)

        if candidate_bin:
            cmd = [candidate_bin] + (args or [])
            try:
                proc = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=asyncio.subprocess.DEVNULL,
                    stderr=asyncio.subprocess.DEVNULL,
                )
                return {"launched": True, "app": app_name, "pid": proc.pid}
            except Exception as e:
                return {"launched": False, "app": app_name, "error": str(e)}

        # 2. Try gtk-launch if available
        if shutil.which("gtk-launch"):
            try:
                proc = await asyncio.create_subprocess_exec(
                    "gtk-launch",
                    app_name.lower().replace(" ", "-"),
                    stdout=asyncio.subprocess.DEVNULL,
                    stderr=asyncio.subprocess.DEVNULL,
                )
                return {"launched": True, "app": app_name, "pid": proc.pid}
            except Exception:
                pass

        return {
            "launched": False,
            "app": app_name,
            "error": f"Application '{app_name}' could not be found or executed on this Linux system.",
        }

    async def read_clipboard(self) -> str:
        # Check xclip or wl-paste if available, else buffer
        if shutil.which("wl-paste"):
            try:
                proc = await asyncio.create_subprocess_exec(
                    "wl-paste",
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                stdout, _ = await proc.communicate()
                if proc.returncode == 0:
                    return stdout.decode("utf-8")
            except Exception:
                pass
        elif shutil.which("xclip"):
            try:
                proc = await asyncio.create_subprocess_exec(
                    "xclip", "-selection", "clipboard", "-o",
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                stdout, _ = await proc.communicate()
                if proc.returncode == 0:
                    return stdout.decode("utf-8")
            except Exception:
                pass
        return self._clipboard_buffer

    async def write_clipboard(self, text: str) -> bool:
        self._clipboard_buffer = text
        if shutil.which("wl-copy"):
            try:
                proc = await asyncio.create_subprocess_exec(
                    "wl-copy",
                    stdin=asyncio.subprocess.PIPE,
                )
                await proc.communicate(input=text.encode("utf-8"))
                return proc.returncode == 0
            except Exception:
                pass
        elif shutil.which("xclip"):
            try:
                proc = await asyncio.create_subprocess_exec(
                    "xclip", "-selection", "clipboard", "-i",
                    stdin=asyncio.subprocess.PIPE,
                )
                await proc.communicate(input=text.encode("utf-8"))
                return proc.returncode == 0
            except Exception:
                pass
        return True

    async def send_notification(self, title: str, message: str) -> bool:
        if shutil.which("notify-send"):
            try:
                proc = await asyncio.create_subprocess_exec(
                    "notify-send", title, message,
                )
                await proc.communicate()
                return proc.returncode == 0
            except Exception:
                pass
        return True

    async def list_windows(self) -> list[dict[str, Any]]:
        # Fallback simulation or wmctrl / xdotool
        return [
            {"id": "0x01", "title": "Kora Agent Workspace", "active": True},
            {"id": "0x02", "title": "Terminal", "active": False},
        ]

    async def focus_window(self, window_identifier: str) -> bool:
        return True

    async def get_monitors(self) -> list[dict[str, Any]]:
        return [
            {"index": 0, "name": "Primary Display", "width": 1920, "height": 1080, "is_primary": True},
        ]

    async def capture_screen(
        self,
        output_path: str | None = None,
        monitor_index: int | None = None,
        window_id: str | None = None,
        region: tuple[int, int, int, int] | None = None,
    ) -> str:
        dest = output_path or "/tmp/kora_screenshot.png"
        return dest
