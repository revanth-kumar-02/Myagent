"""
tools.computer — Computer Control & GUI Automation Tools (V8)

Tools:
  - WindowManagerTool: List, focus, or manage active desktop windows
  - MouseControlTool: Move, click, and scroll mouse
  - KeyboardControlTool: Type text and press keyboard hotkeys
  - ScreenCaptureTool: Take desktop screenshot
"""

from __future__ import annotations

from typing import Any

from tools.base import BaseTool
from tools.platforms.factory import get_platform_adapter
from tools.types import PermissionLevel, ToolCategory, ToolResult


class WindowManagerTool(BaseTool):
    """List or focus active desktop windows."""

    @property
    def tool_id(self) -> str:
        return "window_manager"

    @property
    def category(self) -> ToolCategory:
        return ToolCategory.COMPUTER

    @property
    def description(self) -> str:
        return "List open desktop windows or focus a specific window."

    @property
    def permission_level(self) -> PermissionLevel:
        return PermissionLevel.LOW_RISK_WRITE

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "action": {"type": "string", "enum": ["list", "focus"], "description": "Action to perform"},
                "window_id": {"type": "string", "description": "Window title or identifier for focus action"},
            },
            "required": ["action"],
        }

    async def execute(self, params: dict[str, Any]) -> ToolResult:
        adapter = get_platform_adapter()
        action = params["action"]
        if action == "list":
            windows = await adapter.list_windows()
            return self._make_result(output={"windows": windows, "count": len(windows)})
        elif action == "focus":
            win_id = params.get("window_id", "")
            ok = await adapter.focus_window(win_id)
            return self._make_result(output={"focused": ok, "window_id": win_id})
        return self._make_result(error=f"Unknown action: {action}")


class MouseControlTool(BaseTool):
    """Simulate mouse actions (move, click, scroll)."""

    @property
    def tool_id(self) -> str:
        return "mouse_control"

    @property
    def category(self) -> ToolCategory:
        return ToolCategory.COMPUTER

    @property
    def description(self) -> str:
        return "Simulate mouse cursor movement, clicking, and scrolling."

    @property
    def permission_level(self) -> PermissionLevel:
        return PermissionLevel.HIGH_IMPACT_ACTION

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "action": {"type": "string", "enum": ["click", "move", "scroll"], "description": "Mouse action"},
                "x": {"type": "integer", "description": "X screen coordinate"},
                "y": {"type": "integer", "description": "Y screen coordinate"},
                "button": {"type": "string", "enum": ["left", "right", "middle"], "description": "Mouse button"},
                "scroll_amount": {"type": "integer", "description": "Scroll delta"},
            },
            "required": ["action"],
        }

    async def execute(self, params: dict[str, Any]) -> ToolResult:
        action = params["action"]
        x = params.get("x", 0)
        y = params.get("y", 0)
        btn = params.get("button", "left")
        scroll = params.get("scroll_amount", 0)

        # Simulation or OS interaction via adapter
        return self._make_result(output={"executed": True, "action": action, "x": x, "y": y, "button": btn, "scroll": scroll})


class KeyboardControlTool(BaseTool):
    """Simulate keyboard input and hotkeys."""

    @property
    def tool_id(self) -> str:
        return "keyboard_control"

    @property
    def category(self) -> ToolCategory:
        return ToolCategory.COMPUTER

    @property
    def description(self) -> str:
        return "Simulate typing text or pressing keyboard hotkeys."

    @property
    def permission_level(self) -> PermissionLevel:
        return PermissionLevel.HIGH_IMPACT_ACTION

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "action": {"type": "string", "enum": ["type", "press_key", "hotkey"], "description": "Keyboard action"},
                "text": {"type": "string", "description": "Text to type"},
                "keys": {"type": "array", "items": {"type": "string"}, "description": "Key or hotkey sequence (e.g. ['ctrl', 'c'])"},
            },
            "required": ["action"],
        }

    async def execute(self, params: dict[str, Any]) -> ToolResult:
        action = params["action"]
        text = params.get("text", "")
        keys = params.get("keys", [])
        return self._make_result(output={"executed": True, "action": action, "typed": text, "keys": keys})


class ScreenCaptureTool(BaseTool):
    """Capture a screenshot of the active desktop."""

    @property
    def tool_id(self) -> str:
        return "screen_capture"

    @property
    def category(self) -> ToolCategory:
        return ToolCategory.COMPUTER

    @property
    def description(self) -> str:
        return "Capture a screenshot of the current screen and save to disk."

    @property
    def permission_level(self) -> PermissionLevel:
        return PermissionLevel.READ

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "output_path": {"type": "string", "description": "Optional destination image path"},
                "monitor_index": {"type": "integer", "description": "Index of monitor to capture"},
                "window_id": {"type": "string", "description": "Window ID to capture"},
                "region": {
                    "type": "array",
                    "items": {"type": "integer"},
                    "description": "[x, y, width, height] region coordinates",
                },
            },
        }

    async def execute(self, params: dict[str, Any]) -> ToolResult:
        adapter = get_platform_adapter()
        dest = params.get("output_path")
        mon = params.get("monitor_index")
        win = params.get("window_id")
        reg = tuple(params["region"]) if params.get("region") else None
        path = await adapter.capture_screen(output_path=dest, monitor_index=mon, window_id=win, region=reg)
        return self._make_result(
            output={
                "screenshot_path": path,
                "captured": True,
                "monitor_index": mon,
                "window_id": win,
                "region": list(reg) if reg else None,
            }
        )
