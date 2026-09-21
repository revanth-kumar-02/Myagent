"""
vision.capture — Screen Capture Engine (V19)

Provides multi-monitor, window, full-screen, and region capture with
ephemeral storage lifecycle management and platform abstraction.
"""

from __future__ import annotations

import os
import pathlib
import tempfile
import uuid
from typing import Any

import structlog

from tools.platforms.base import BasePlatformAdapter
from tools.platforms.factory import get_platform_adapter
from vision.types import CaptureOptions, CaptureTarget, ScreenCaptureResult

logger = structlog.get_logger(__name__)


class ScreenCaptureEngine:
    """
    Coordinates desktop screen captures across monitors, windows, and regions.
    """

    def __init__(self, adapter: BasePlatformAdapter | None = None, base_temp_dir: str | None = None) -> None:
        self._adapter = adapter or get_platform_adapter()
        self._temp_dir = pathlib.Path(base_temp_dir or tempfile.gettempdir()) / "kora_vision"
        self._temp_dir.mkdir(parents=True, exist_ok=True)
        self._active_captures: dict[str, pathlib.Path] = {}

    async def get_monitors(self) -> list[dict[str, Any]]:
        """Return connected displays."""
        return await self._adapter.get_monitors()

    async def list_windows(self) -> list[dict[str, Any]]:
        """Return active desktop windows."""
        return await self._adapter.list_windows()

    async def capture(self, options: CaptureOptions | None = None) -> ScreenCaptureResult:
        """
        Execute screen capture according to options.
        """
        opts = options or CaptureOptions()
        capture_id = f"cap_{uuid.uuid4().hex[:8]}"

        if opts.output_path:
            dest_path = pathlib.Path(opts.output_path)
            is_ephemeral = opts.ephemeral
        else:
            dest_path = self._temp_dir / f"{capture_id}.png"
            is_ephemeral = opts.ephemeral

        # Call platform adapter
        res_path_str = await self._adapter.capture_screen(
            output_path=str(dest_path),
            monitor_index=opts.monitor_index,
            window_id=opts.window_id,
            region=opts.region,
        )

        saved_path = pathlib.Path(res_path_str)
        if is_ephemeral:
            self._active_captures[capture_id] = saved_path

        # Determine dimensions (default to standard HD or region bounds if mocked)
        width = 1920
        height = 1080
        if opts.region:
            width = opts.region[2]
            height = opts.region[3]

        logger.info(
            "screen_captured",
            capture_id=capture_id,
            target=opts.target.value,
            path=str(saved_path),
            is_ephemeral=is_ephemeral,
        )

        return ScreenCaptureResult(
            capture_id=capture_id,
            image_path=str(saved_path),
            width=width,
            height=height,
            target=opts.target,
            monitor_index=opts.monitor_index,
            window_id=opts.window_id,
            region=opts.region,
            is_ephemeral=is_ephemeral,
            metadata={
                "os": self._adapter.platform_os.value,
            },
        )

    def cleanup(self, capture_id: str) -> bool:
        """Remove an ephemeral screenshot from disk."""
        path = self._active_captures.pop(capture_id, None)
        if path and path.exists():
            try:
                path.unlink(missing_ok=True)
                return True
            except OSError as e:
                logger.warning("failed_to_delete_ephemeral_capture", path=str(path), error=str(e))
        return False

    def cleanup_all(self) -> int:
        """Remove all tracked ephemeral screenshots."""
        count = 0
        for cap_id in list(self._active_captures.keys()):
            if self.cleanup(cap_id):
                count += 1
        return count
