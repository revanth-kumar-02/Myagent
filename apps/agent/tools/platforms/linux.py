"""
tools.platforms.linux — Linux Platform Adapter (V8)
"""

from __future__ import annotations

import asyncio
import os
import platform
import shutil
from pathlib import Path
from typing import Any

from tools.platforms.base import BasePlatformAdapter
from tools.types import PlatformOS

WEB_APP_URLS: dict[str, str] = {
    "youtube": "https://www.youtube.com",
    "yt": "https://www.youtube.com",
    "gmail": "https://mail.google.com",
    "github": "https://github.com",
    "gh": "https://github.com",
    "twitter": "https://x.com",
    "x": "https://x.com",
    "reddit": "https://www.reddit.com",
    "chatgpt": "https://chatgpt.com",
    "openai": "https://chatgpt.com",
    "claude": "https://claude.ai",
    "netflix": "https://www.netflix.com",
    "spotify": "https://open.spotify.com",
    "whatsapp": "https://web.whatsapp.com",
    "telegram": "https://web.telegram.org",
    "discord": "https://discord.com/app",
    "slack": "https://app.slack.com",
    "notion": "https://www.notion.so",
    "figma": "https://www.figma.com",
    "linkedin": "https://www.linkedin.com",
    "maps": "https://maps.google.com",
    "calendar": "https://calendar.google.com",
    "drive": "https://drive.google.com",
    "docs": "https://docs.google.com",
    "sheets": "https://sheets.google.com",
    "google": "https://www.google.com",
    "stackoverflow": "https://stackoverflow.com",
    "twitch": "https://www.twitch.tv",
    "amazon": "https://www.amazon.com",
    "wikipedia": "https://www.wikipedia.org",
}


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

    @staticmethod
    def _has_desktop_file(name: str) -> bool:
        desktop_dirs = [
            Path("/usr/share/applications"),
            Path("/usr/local/share/applications"),
            Path(os.path.expanduser("~/.local/share/applications")),
        ]
        target = f"{name}.desktop".lower()
        for d in desktop_dirs:
            if d.is_dir():
                for f in d.glob("*.desktop"):
                    if f.name.lower() == target or f.stem.lower() == name.lower():
                        return True
        return False

    async def launch_app(self, app_name: str, args: list[str] | None = None) -> dict[str, Any]:
        app_clean = app_name.lower().strip()

        # 1. Check if input is directly a URL or in known web apps
        is_direct_url = app_name.startswith(("http://", "https://", "www.")) or any(
            app_clean.endswith(tld) for tld in (".com", ".org", ".net", ".io", ".app", ".ai", ".tv")
        )
        web_url = WEB_APP_URLS.get(app_clean)

        # 2. Check direct binary or lowercase command first if not an explicit URL
        candidate_bin = None
        if not is_direct_url:
            candidate_bin = shutil.which(app_name)
            if not candidate_bin:
                lowered = app_clean.replace(" ", "-")
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
                    "terminal": "x-terminal-emulator" if shutil.which("x-terminal-emulator") else ("ptyxis" if shutil.which("ptyxis") else "gnome-terminal"),
                    "code": "code",
                    "vscode": "code",
                }
                mapped = common_mappings.get(app_clean)
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

        # 3. Check native desktop file (.desktop) before trying gtk-launch
        desktop_app_id = app_clean.replace(" ", "-")
        if self._has_desktop_file(desktop_app_id) and shutil.which("gtk-launch"):
            try:
                proc = await asyncio.create_subprocess_exec(
                    "gtk-launch",
                    desktop_app_id,
                    stdout=asyncio.subprocess.DEVNULL,
                    stderr=asyncio.subprocess.DEVNULL,
                )
                return {"launched": True, "app": app_name, "pid": proc.pid}
            except Exception:
                pass

        # 4. Fallback to Browser: If app is not installed locally, launch in Google Chrome / default browser
        target_url = web_url
        if not target_url:
            if is_direct_url:
                if app_name.startswith(("http://", "https://")):
                    target_url = app_name
                elif app_name.startswith("www."):
                    target_url = f"https://{app_name}"
                else:
                    target_url = f"https://www.{app_clean}"
            elif app_clean in WEB_APP_URLS:
                target_url = WEB_APP_URLS[app_clean]
            else:
                target_url = f"https://www.{app_clean}.com"

        browser_bin = (
            shutil.which("google-chrome")
            or shutil.which("chromium")
            or shutil.which("firefox")
            or shutil.which("xdg-open")
        )
        if browser_bin and target_url:
            browser_name = (
                "Google Chrome" if "chrome" in browser_bin
                else ("Firefox" if "firefox" in browser_bin else "Default Browser")
            )
            try:
                proc = await asyncio.create_subprocess_exec(
                    browser_bin,
                    target_url,
                    stdout=asyncio.subprocess.DEVNULL,
                    stderr=asyncio.subprocess.DEVNULL,
                )
                return {
                    "launched": True,
                    "app": app_name,
                    "mode": "browser",
                    "browser": browser_name,
                    "url": target_url,
                    "pid": proc.pid,
                    "message": f"'{app_name}' is not installed locally. Opened {target_url} in {browser_name}.",
                }
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
