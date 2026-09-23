"""tools.shell — Shell Execution Tool."""
from __future__ import annotations
from typing import Any
from tools.base import BaseTool
from tools.types import ToolResult


class ShellExecTool(BaseTool):
    name = "shell_exec"
    description = "Execute a shell command and return stdout/stderr. Use sparingly and safely."
    parameters = {
        "type": "object",
        "properties": {
            "command": {"type": "string", "description": "Shell command to execute"},
            "cwd": {"type": "string", "description": "Working directory (optional)"},
            "timeout_seconds": {"type": "integer", "default": 30},
        },
        "required": ["command"],
    }
    required_permissions = ["shell_exec"]

    async def execute(self, params: dict[str, Any] | None = None, **kwargs: Any) -> ToolResult:
        raise NotImplementedError  # TODO: implement in feature phase
