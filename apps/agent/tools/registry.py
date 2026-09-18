"""
tools.registry — Tool Registry

Central registry for all Kora tools.
Tools register themselves at startup; the ToolRouter looks them up by name.
"""

from __future__ import annotations

from tools.base import BaseTool


class ToolRegistry:
    """
    Holds all registered BaseTool instances.
    Populated at application startup via register().
    """

    def __init__(self) -> None:
        self._tools: dict[str, BaseTool] = {}

    def register(self, tool: BaseTool) -> None:
        """Register a tool. Raises if a tool with the same name already exists."""
        if tool.name in self._tools:
            raise ValueError(f"Tool already registered: {tool.name!r}")
        self._tools[tool.name] = tool

    def get(self, name: str) -> BaseTool:
        """Get a tool by name. Raises ToolNotFoundError if not registered."""
        if name not in self._tools:
            raise ToolNotFoundError(f"Tool not found: {name!r}")
        return self._tools[name]

    def all(self) -> list[BaseTool]:
        """Return all registered tools (for LLM tool schema generation)."""
        return list(self._tools.values())

    def to_schema(self) -> list[dict]:
        """Return a list of tool schemas compatible with OpenAI function-calling format."""
        return [
            {
                "name": tool.name,
                "description": tool.description,
                "parameters": tool.parameters,
            }
            for tool in self._tools.values()
        ]


class ToolNotFoundError(Exception):
    """Raised when a tool name is not in the registry."""


def build_default_registry() -> ToolRegistry:
    """
    Create and populate the default ToolRegistry with all built-in tools.
    Called once at application startup.
    """
    from tools.fs import FileReadTool, FileWriteTool
    from tools.shell import ShellExecTool
    from tools.browser import BrowserNavigateTool, BrowserClickTool, BrowserExtractTool
    from tools.scheduler import ScheduleTaskTool, CancelTaskTool
    from tools.rag_tool import RAGQueryTool
    from tools.web_tool import WebSearchTool

    registry = ToolRegistry()
    registry.register(FileReadTool())
    registry.register(FileWriteTool())
    registry.register(ShellExecTool())
    registry.register(BrowserNavigateTool())
    registry.register(BrowserClickTool())
    registry.register(BrowserExtractTool())
    registry.register(ScheduleTaskTool())
    registry.register(CancelTaskTool())
    registry.register(RAGQueryTool())
    registry.register(WebSearchTool())
    return registry
