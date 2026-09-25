"""
tools.registry — Central Tool Registry (V8)

Features:
  - Central registration for all Kora tools across 5 categories
  - Lookup by tool_id or name
  - Category-based filtering and listing
  - Function-calling JSON schema export for LLM integration
  - Factory build_default_registry() registering all built-in tools
"""

from __future__ import annotations

from typing import Any, Iterator

from tools.base import BaseTool
from tools.types import ToolCategory


class ToolNotFoundError(Exception):
    """Raised when a requested tool is not found in the registry."""


class ToolRegistry:
    """
    Holds all registered BaseTool instances.
    """

    def __init__(self) -> None:
        self._tools: dict[str, BaseTool] = {}

    def register(self, tool: BaseTool) -> None:
        """Register a tool. Raises if a tool with the same id or name exists."""
        key = tool.tool_id
        if key in self._tools:
            raise ValueError(f"Tool already registered: {key!r}")
        self._tools[key] = tool
        # Also map by name if different
        if tool.name != key:
            self._tools[tool.name] = tool

    def get(self, name_or_id: str) -> BaseTool:
        """Get a tool by name or tool_id."""
        if name_or_id not in self._tools:
            raise ToolNotFoundError(f"Tool not found: {name_or_id!r}")
        return self._tools[name_or_id]

    def get_by_category(self, category: ToolCategory | str) -> list[BaseTool]:
        """Filter tools by category."""
        cat_val = category.value if isinstance(category, ToolCategory) else category
        return [t for t in self.all() if t.category.value == cat_val]

    def all(self) -> list[BaseTool]:
        """Return unique list of registered tools."""
        unique_tools: dict[str, BaseTool] = {}
        for t in self._tools.values():
            unique_tools[t.tool_id] = t
        return list(unique_tools.values())

    def to_schema(self) -> list[dict[str, Any]]:
        """Return a list of tool schemas compatible with OpenAI / Anthropic function-calling format."""
        return [
            {
                "name": tool.name,
                "description": tool.description,
                "parameters": tool.parameters,
            }
            for tool in self.all()
        ]


def build_default_registry() -> ToolRegistry:
    """
    Create and populate the default ToolRegistry with all 22 built-in tools.
    """
    from tools.computer import (
        KeyboardControlTool,
        MouseControlTool,
        ScreenCaptureTool,
        WindowManagerTool,
    )
    from tools.dev import (
        DatabaseOpsTool,
        GitOperationsTool,
        TerminalExecTool,
    )
    from tools.files import (
        DirectoryOpsTool,
        FileCreateTool,
        FileDeleteTool,
        FileMoveTool,
        FileReadTool,
        FileRenameTool,
        FileWriteTool,
    )
    from tools.scheduler import (
        CancelTaskTool,
        ListTasksTool,
        PauseTaskTool,
        ResumeTaskTool,
        ScheduleTaskTool,
    )
    from tools.system import (
        AppLauncherTool,
        ClipboardTool,
        NotificationTool,
        SystemInfoTool,
    )
    from tools.web import (
        BrowserControlTool,
        DownloadManagerTool,
        PageInteractionTool,
        PageNavigationTool,
    )

    registry = ToolRegistry()

    # System & Automation
    registry.register(AppLauncherTool())
    registry.register(ClipboardTool())
    registry.register(NotificationTool())
    registry.register(SystemInfoTool())
    registry.register(ScheduleTaskTool())
    registry.register(CancelTaskTool())
    registry.register(ListTasksTool())
    registry.register(PauseTaskTool())
    registry.register(ResumeTaskTool())

    # Files
    registry.register(FileReadTool())
    registry.register(FileWriteTool())
    registry.register(FileCreateTool())
    registry.register(FileMoveTool())
    registry.register(FileRenameTool())
    registry.register(FileDeleteTool())
    registry.register(DirectoryOpsTool())

    # Computer
    registry.register(WindowManagerTool())
    registry.register(MouseControlTool())
    registry.register(KeyboardControlTool())
    registry.register(ScreenCaptureTool())

    # Web
    registry.register(BrowserControlTool())
    registry.register(PageNavigationTool())
    registry.register(PageInteractionTool())
    registry.register(DownloadManagerTool())
    from tools.web_tool import WebSearchTool
    registry.register(WebSearchTool())

    # Dev
    registry.register(TerminalExecTool())
    registry.register(GitOperationsTool())
    registry.register(DatabaseOpsTool())

    return registry
