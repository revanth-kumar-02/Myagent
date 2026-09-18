"""
tools.platforms.factory — Platform Adapter Factory (V8)
"""

from __future__ import annotations

import sys

from tools.platforms.base import BasePlatformAdapter
from tools.platforms.linux import LinuxAdapter
from tools.platforms.macos import MacOSAdapter
from tools.platforms.windows import WindowsAdapter

_ADAPTER_INSTANCE: BasePlatformAdapter | None = None


def get_platform_adapter(force_platform: str | None = None) -> BasePlatformAdapter:
    """
    Return the singleton platform adapter for the current OS.
    """
    global _ADAPTER_INSTANCE
    if force_platform:
        if force_platform.lower().startswith("win"):
            return WindowsAdapter()
        elif force_platform.lower().startswith("darwin") or force_platform.lower() == "macos":
            return MacOSAdapter()
        return LinuxAdapter()

    if _ADAPTER_INSTANCE is None:
        if sys.platform.startswith("win"):
            _ADAPTER_INSTANCE = WindowsAdapter()
        elif sys.platform.startswith("darwin"):
            _ADAPTER_INSTANCE = MacOSAdapter()
        else:
            _ADAPTER_INSTANCE = LinuxAdapter()

    return _ADAPTER_INSTANCE
