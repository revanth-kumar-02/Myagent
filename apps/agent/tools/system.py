"""
tools.system — System Management Tools (V8)

Tools:
  - AppLauncherTool: Launch desktop applications
  - ClipboardTool: Read and write system clipboard
  - NotificationTool: Dispatch OS desktop notifications
  - SystemInfoTool: Query hardware and OS information
"""

from __future__ import annotations

from typing import Any

from tools.base import BaseTool
from tools.platforms.factory import get_platform_adapter
from tools.types import PermissionLevel, PlatformOS, ToolCategory, ToolResult


class AppLauncherTool(BaseTool):
    """Launch a desktop application or process."""

    @property
    def tool_id(self) -> str:
        return "app_launcher"

    @property
    def category(self) -> ToolCategory:
        return ToolCategory.SYSTEM

    @property
    def description(self) -> str:
        return "Launch an installed desktop application or executable."

    @property
    def permission_level(self) -> PermissionLevel:
        return PermissionLevel.HIGH_IMPACT_ACTION

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "app_name": {"type": "string", "description": "Name or executable of the application"},
                "args": {"type": "array", "items": {"type": "string"}, "description": "Command line arguments"},
            },
            "required": ["app_name"],
        }

    async def execute(self, params: dict[str, Any] | None = None, **kwargs: Any) -> ToolResult:
        p = self.sanitize_params(params, **kwargs)
        adapter = get_platform_adapter()
        app_name = p.get("app_name", "")
        args = p.get("args", [])
        res = await adapter.launch_app(app_name, args)
        if res.get("launched"):
            return self._make_result(output=res)
        return self._make_result(output=res, error=res.get("error", "Failed to launch app"))


class ClipboardTool(BaseTool):
    """Read or write text to the system clipboard."""

    @property
    def tool_id(self) -> str:
        return "clipboard"

    @property
    def category(self) -> ToolCategory:
        return ToolCategory.SYSTEM

    @property
    def description(self) -> str:
        return "Read from or write text to the system clipboard."

    @property
    def permission_level(self) -> PermissionLevel:
        return PermissionLevel.LOW_RISK_WRITE

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "action": {"type": "string", "enum": ["read", "write"], "description": "Clipboard action"},
                "text": {"type": "string", "description": "Text to write (required if action is write)"},
            },
            "required": ["action"],
        }

    async def execute(self, params: dict[str, Any] | None = None, **kwargs: Any) -> ToolResult:
        p = self.sanitize_params(params, **kwargs)
        adapter = get_platform_adapter()
        action = p.get("action", "read")
        if action == "write":
            text = p.get("text", "")
            ok = await adapter.write_clipboard(text)
            return self._make_result(output={"written": ok, "length": len(text)})
        else:
            content = await adapter.read_clipboard()
            return self._make_result(output={"content": content, "length": len(content)})


class NotificationTool(BaseTool):
    """Display a system desktop notification."""

    @property
    def tool_id(self) -> str:
        return "notification"

    @property
    def category(self) -> ToolCategory:
        return ToolCategory.SYSTEM

    @property
    def description(self) -> str:
        return "Display a system desktop notification to the user."

    @property
    def permission_level(self) -> PermissionLevel:
        return PermissionLevel.LOW_RISK_WRITE

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "Notification title"},
                "message": {"type": "string", "description": "Notification body message"},
            },
            "required": ["title", "message"],
        }

    async def execute(self, params: dict[str, Any] | None = None, **kwargs: Any) -> ToolResult:
        p = self.sanitize_params(params, **kwargs)
        adapter = get_platform_adapter()
        title = p.get("title", "")
        message = p.get("message", "")
        ok = await adapter.send_notification(title, message)
        return self._make_result(output={"displayed": ok, "title": title})


class SystemInfoTool(BaseTool):
    """Retrieve host system, hardware, and OS specifications."""

    @property
    def tool_id(self) -> str:
        return "system_info"

    @property
    def category(self) -> ToolCategory:
        return ToolCategory.SYSTEM

    @property
    def description(self) -> str:
        return "Retrieve host hardware, operating system, and architecture details."

    @property
    def permission_level(self) -> PermissionLevel:
        return PermissionLevel.READ

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {},
        }

    async def execute(self, params: dict[str, Any] | None = None, **kwargs: Any) -> ToolResult:
        adapter = get_platform_adapter()
        info = await adapter.get_system_info()
        return self._make_result(output=info)
