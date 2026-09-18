"""
tools.platforms package — Multi-OS Platform Abstraction (V8).
"""

from tools.platforms.base import BasePlatformAdapter
from tools.platforms.factory import get_platform_adapter
from tools.platforms.linux import LinuxAdapter
from tools.platforms.macos import MacOSAdapter
from tools.platforms.windows import WindowsAdapter

__all__ = [
    "BasePlatformAdapter",
    "LinuxAdapter",
    "WindowsAdapter",
    "MacOSAdapter",
    "get_platform_adapter",
]
