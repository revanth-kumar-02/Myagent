"""
tools.google.tasks_tools — Google Tasks Agent Tools (V8)

Provides granular tools (google_tasks_list, google_tasks_create, google_tasks_complete)
and unified tool (google_tasks).
"""

from __future__ import annotations

from typing import Any

from integrations.google.errors import GoogleWorkspaceError
from integrations.google.tasks import TasksService
from tools.base import BaseTool
from tools.types import PermissionLevel, ToolCategory, ToolResult, ToolStatus


def _format_google_error(tool_name: str, err: Exception) -> ToolResult:
    """Format exceptions into clean, structured ToolResult."""
    if isinstance(err, GoogleWorkspaceError):
        return ToolResult(
            tool_name=tool_name,
            status=ToolStatus.ERROR,
            error=err.message,
            output={"error_code": err.error_code, "details": err.details},
        )
    return ToolResult(
        tool_name=tool_name,
        status=ToolStatus.ERROR,
        error=f"Tasks operation failed: {err}",
        output={"error_code": "GOOGLE_API_ERROR"},
    )


class TasksListTool(BaseTool):
    """List tasks in a user's task list."""

    def __init__(self, service: TasksService | None = None) -> None:
        self.service = service or TasksService()

    @property
    def tool_id(self) -> str:
        return "google_tasks_list"

    @property
    def category(self) -> ToolCategory:
        return ToolCategory.WORKSPACE

    @property
    def description(self) -> str:
        return "List tasks from the user's Google Tasks with optional completed/due filters."

    @property
    def permission_level(self) -> PermissionLevel:
        return PermissionLevel.READ

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "task_list_id": {"type": "string", "description": "Task list ID (defaults to '@default')", "default": "@default"},
                "show_completed": {"type": "boolean", "description": "Include completed tasks", "default": False},
                "due_min": {"type": "string", "description": "RFC 3339 earliest due date"},
                "due_max": {"type": "string", "description": "RFC 3339 latest due date"},
            },
        }

    async def execute(self, params: dict[str, Any] | None = None, **kwargs: Any) -> ToolResult:
        p = self.sanitize_params(params, **kwargs)
        try:
            tasks = await self.service.list_tasks(
                task_list_id=p.get("task_list_id", "@default"),
                show_completed=p.get("show_completed", False),
                due_min=p.get("due_min"),
                due_max=p.get("due_max"),
            )
            return ToolResult(tool_name=self.name, status=ToolStatus.SUCCESS, output={"tasks": tasks, "count": len(tasks)})
        except Exception as e:
            return _format_google_error(self.name, e)


class TasksCreateTool(BaseTool):
    """Create a task in Google Tasks."""

    def __init__(self, service: TasksService | None = None) -> None:
        self.service = service or TasksService()

    @property
    def tool_id(self) -> str:
        return "google_tasks_create"

    @property
    def category(self) -> ToolCategory:
        return ToolCategory.WORKSPACE

    @property
    def description(self) -> str:
        return "Create a new task in Google Tasks with optional notes and due date."

    @property
    def permission_level(self) -> PermissionLevel:
        return PermissionLevel.LOW_RISK_WRITE

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "Task title"},
                "task_list_id": {"type": "string", "default": "@default"},
                "notes": {"type": "string", "description": "Additional notes/description"},
                "due": {"type": "string", "description": "Due date in YYYY-MM-DD or RFC 3339 format"},
            },
            "required": ["title"],
        }

    async def execute(self, params: dict[str, Any] | None = None, **kwargs: Any) -> ToolResult:
        p = self.sanitize_params(params, **kwargs)
        try:
            task = await self.service.create_task(
                title=p.get("title", ""),
                task_list_id=p.get("task_list_id", "@default"),
                notes=p.get("notes"),
                due=p.get("due"),
            )
            return ToolResult(tool_name=self.name, status=ToolStatus.SUCCESS, output=task)
        except Exception as e:
            return _format_google_error(self.name, e)


class TasksCompleteTool(BaseTool):
    """Mark a task as completed in Google Tasks."""

    def __init__(self, service: TasksService | None = None) -> None:
        self.service = service or TasksService()

    @property
    def tool_id(self) -> str:
        return "google_tasks_complete"

    @property
    def category(self) -> ToolCategory:
        return ToolCategory.WORKSPACE

    @property
    def description(self) -> str:
        return "Mark an existing Google Task as completed."

    @property
    def permission_level(self) -> PermissionLevel:
        return PermissionLevel.LOW_RISK_WRITE

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "task_id": {"type": "string", "description": "Task ID to complete"},
                "task_list_id": {"type": "string", "default": "@default"},
            },
            "required": ["task_id"],
        }

    async def execute(self, params: dict[str, Any] | None = None, **kwargs: Any) -> ToolResult:
        p = self.sanitize_params(params, **kwargs)
        try:
            task = await self.service.complete_task(
                task_id=p.get("task_id", ""),
                task_list_id=p.get("task_list_id", "@default"),
            )
            return ToolResult(tool_name=self.name, status=ToolStatus.SUCCESS, output=task)
        except Exception as e:
            return _format_google_error(self.name, e)


class GoogleTasksTool(BaseTool):
    """Unified Google Tasks multi-action tool."""

    def __init__(self, service: TasksService | None = None) -> None:
        self.service = service or TasksService()

    @property
    def tool_id(self) -> str:
        return "google_tasks"

    @property
    def category(self) -> ToolCategory:
        return ToolCategory.WORKSPACE

    @property
    def description(self) -> str:
        return "Manage Google Tasks: list tasks, create tasks, update details, mark complete, reopen, or delete."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["list", "create", "update", "complete", "reopen", "delete", "list_lists"],
                    "description": "Tasks action to perform",
                },
                "task_list_id": {"type": "string", "default": "@default"},
                "task_id": {"type": "string", "description": "Task ID for update/complete/delete"},
                "title": {"type": "string", "description": "Title for task creation or rename"},
                "notes": {"type": "string", "description": "Task description notes"},
                "due": {"type": "string", "description": "Due date in YYYY-MM-DD or RFC 3339 format"},
                "show_completed": {"type": "boolean", "default": False},
            },
            "required": ["action"],
        }

    async def execute(self, params: dict[str, Any] | None = None, **kwargs: Any) -> ToolResult:
        p = self.sanitize_params(params, **kwargs)
        action = p.get("action", "list")
        task_list_id = p.get("task_list_id", "@default")

        try:
            if action == "list":
                tasks = await self.service.list_tasks(
                    task_list_id=task_list_id,
                    show_completed=p.get("show_completed", False),
                    due_min=p.get("due_min"),
                    due_max=p.get("due_max"),
                )
                return ToolResult(tool_name=self.name, status=ToolStatus.SUCCESS, output={"tasks": tasks})

            elif action == "list_lists":
                lists = await self.service.list_task_lists()
                return ToolResult(tool_name=self.name, status=ToolStatus.SUCCESS, output={"lists": lists})

            elif action == "create":
                task = await self.service.create_task(
                    title=p.get("title", ""),
                    task_list_id=task_list_id,
                    notes=p.get("notes"),
                    due=p.get("due"),
                )
                return ToolResult(tool_name=self.name, status=ToolStatus.SUCCESS, output=task)

            elif action == "update":
                task = await self.service.update_task(
                    task_id=p.get("task_id", ""),
                    task_list_id=task_list_id,
                    title=p.get("title"),
                    notes=p.get("notes"),
                    due=p.get("due"),
                )
                return ToolResult(tool_name=self.name, status=ToolStatus.SUCCESS, output=task)

            elif action == "complete":
                task = await self.service.complete_task(
                    task_id=p.get("task_id", ""),
                    task_list_id=task_list_id,
                )
                return ToolResult(tool_name=self.name, status=ToolStatus.SUCCESS, output=task)

            elif action == "reopen":
                task = await self.service.reopen_task(
                    task_id=p.get("task_id", ""),
                    task_list_id=task_list_id,
                )
                return ToolResult(tool_name=self.name, status=ToolStatus.SUCCESS, output=task)

            elif action == "delete":
                res = await self.service.delete_task(
                    task_id=p.get("task_id", ""),
                    task_list_id=task_list_id,
                )
                return ToolResult(tool_name=self.name, status=ToolStatus.SUCCESS, output=res)

            else:
                return ToolResult(
                    tool_name=self.name,
                    status=ToolStatus.ERROR,
                    error=f"Unknown action: {action}",
                    output={"error_code": "GOOGLE_INVALID_ARGUMENT"},
                )
        except Exception as e:
            return _format_google_error(self.name, e)
