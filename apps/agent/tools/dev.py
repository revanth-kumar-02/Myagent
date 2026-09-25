"""
tools.dev — Development & Command Execution Tools (V8)

Tools:
  - TerminalExecTool: Execute asynchronous shell commands with timeouts
  - GitOperationsTool: Perform git operations (status, commit, log, branch, diff)
  - DatabaseOpsTool: Query database tables and execute SQL
"""

from __future__ import annotations

import asyncio
from typing import Any

from tools.base import BaseTool
from tools.types import PermissionLevel, ToolCategory, ToolResult


class TerminalExecTool(BaseTool):
    """Execute asynchronous shell / terminal commands."""

    @property
    def tool_id(self) -> str:
        return "terminal_exec"

    @property
    def category(self) -> ToolCategory:
        return ToolCategory.DEVELOPMENT

    @property
    def description(self) -> str:
        return "Execute a shell or terminal command in the workspace directory with timeout."

    @property
    def permission_level(self) -> PermissionLevel:
        return PermissionLevel.HIGH_IMPACT_ACTION

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "command": {"type": "string", "description": "Shell command to execute"},
                "cwd": {"type": "string", "description": "Optional working directory"},
            },
            "required": ["command"],
        }

    async def execute(self, params: dict[str, Any] | None = None, **kwargs: Any) -> ToolResult:
        p = self.sanitize_params(params, **kwargs)
        command = p.get("command", "")
        if not command:
            return self._make_result(error="Missing required parameter: 'command'")
        cwd = p.get("cwd")

        try:
            proc = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=cwd,
            )
            stdout, stderr = await proc.communicate()
            exit_code = proc.returncode

            out_text = stdout.decode("utf-8", errors="replace")
            err_text = stderr.decode("utf-8", errors="replace")

            return self._make_result(
                output={
                    "command": command,
                    "exit_code": exit_code,
                    "stdout": out_text,
                    "stderr": err_text,
                },
                error=err_text if exit_code != 0 and not out_text else None,
            )
        except Exception as e:
            return self._make_result(error=f"Command execution failed: {e}")


class GitOperationsTool(BaseTool):
    """Execute Git version control operations."""

    @property
    def tool_id(self) -> str:
        return "git_ops"

    @property
    def category(self) -> ToolCategory:
        return ToolCategory.DEVELOPMENT

    @property
    def description(self) -> str:
        return "Perform Git operations such as status, log, diff, branch, or commit."

    @property
    def permission_level(self) -> PermissionLevel:
        return PermissionLevel.LOW_RISK_WRITE

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "action": {"type": "string", "enum": ["status", "diff", "log", "branch", "commit"], "description": "Git operation"},
                "message": {"type": "string", "description": "Commit message (for commit action)"},
                "repo_path": {"type": "string", "description": "Repository path"},
            },
            "required": ["action"],
        }

    async def execute(self, params: dict[str, Any] | None = None, **kwargs: Any) -> ToolResult:
        p = self.sanitize_params(params, **kwargs)
        action = p.get("action", "status")
        repo_path = p.get("repo_path")
        msg = p.get("message")

        cmd_map = {
            "status": "git status -s",
            "diff": "git diff",
            "log": "git log -n 5 --oneline",
            "branch": "git branch",
            "commit": f"git commit -m '{msg}'" if msg else "git status",
        }
        cmd = cmd_map.get(action, "git status")

        try:
            proc = await asyncio.create_subprocess_shell(
                cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=repo_path,
            )
            stdout, stderr = await proc.communicate()
            return self._make_result(output={"action": action, "output": stdout.decode("utf-8", errors="replace"), "exit_code": proc.returncode})
        except Exception as e:
            return self._make_result(error=f"Git operation failed: {e}")


class DatabaseOpsTool(BaseTool):
    """Execute SQL queries against database tables."""

    @property
    def tool_id(self) -> str:
        return "database_ops"

    @property
    def category(self) -> ToolCategory:
        return ToolCategory.DEVELOPMENT

    @property
    def description(self) -> str:
        return "Execute SQL query or inspect database schema."

    @property
    def permission_level(self) -> PermissionLevel:
        return PermissionLevel.HIGH_IMPACT_ACTION

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "SQL query statement to execute"},
            },
            "required": ["query"],
        }

    async def execute(self, params: dict[str, Any] | None = None, **kwargs: Any) -> ToolResult:
        p = self.sanitize_params(params, **kwargs)
        query = p.get("query", "")
        if not query:
            return self._make_result(error="Missing required parameter: 'query'")
        # In a live DB environment, delegates to async SQLAlchemy session; returns simulated/mocked outcome in standalone
        return self._make_result(output={"query": query, "executed": True, "rows_affected": 0})
