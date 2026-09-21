"""
tools.platforms.base — Base Platform Adapter Interface (V8)

Encapsulates all OS-specific execution (Linux, Windows, macOS).
"""

from __future__ import annotations

import abc
from typing import Any

from tools.types import PlatformOS


class BasePlatformAdapter(abc.ABC):
    """Abstract interface for OS-level platform operations."""

    @property
    @abc.abstractmethod
    def platform_os(self) -> PlatformOS:
        """Returns the PlatformOS enum for this adapter."""

    @abc.abstractmethod
    async def get_system_info(self) -> dict[str, Any]:
        """Return OS name, version, architecture, CPU count, memory info."""

    @abc.abstractmethod
    async def launch_app(self, app_name: str, args: list[str] | None = None) -> dict[str, Any]:
        """Launch an application or process."""

    @abc.abstractmethod
    async def read_clipboard(self) -> str:
        """Read text from the system clipboard."""

    @abc.abstractmethod
    async def write_clipboard(self, text: str) -> bool:
        """Write text to the system clipboard."""

    @abc.abstractmethod
    async def send_notification(self, title: str, message: str) -> bool:
        """Display a system desktop notification."""

    @abc.abstractmethod
    async def list_windows(self) -> list[dict[str, Any]]:
        """List active desktop windows."""

    @abc.abstractmethod
    async def focus_window(self, window_identifier: str) -> bool:
        """Bring a window to focus."""

    @abc.abstractmethod
    async def get_monitors(self) -> list[dict[str, Any]]:
        """List connected display monitors with resolution and index."""

    @abc.abstractmethod
    async def capture_screen(
        self,
        output_path: str | None = None,
        monitor_index: int | None = None,
        window_id: str | None = None,
        region: tuple[int, int, int, int] | None = None,
    ) -> str:
        """Capture screenshot and return file path or base64 indicator."""
