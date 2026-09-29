"""
integrations.google.tasks — Google Tasks Service Integration (V8)

Provides direct async integration with Google Tasks API v1:
- List task lists
- List tasks in a task list
- Create task (with title, notes, due date)
- Update task
- Complete task
- Reopen task
- Delete task (destructive)
"""

from __future__ import annotations

from typing import Any

import structlog

from integrations.google.client import GoogleWorkspaceClient
from integrations.google.errors import GoogleInvalidArgumentError

logger = structlog.get_logger(__name__)

TASKS_BASE_URL = "https://tasks.googleapis.com/tasks/v1"


class TasksService:
    """Service wrapper for Google Tasks API v1."""

    def __init__(self, client: GoogleWorkspaceClient | None = None) -> None:
        self.client = client or GoogleWorkspaceClient()

    async def list_task_lists(self, max_results: int = 50) -> list[dict[str, Any]]:
        """List all task lists for the authenticated user."""
        url = f"{TASKS_BASE_URL}/users/@me/lists"
        data = await self.client.request("GET", url, params={"maxResults": max_results})
        items = data.get("items", [])
        return [
            {
                "id": lst.get("id"),
                "title": lst.get("title"),
                "updated": lst.get("updated"),
            }
            for lst in items
        ]

    async def list_tasks(
        self,
        task_list_id: str = "@default",
        show_completed: bool = False,
        show_hidden: bool = False,
        due_min: str | None = None,
        due_max: str | None = None,
        max_results: int = 100,
    ) -> list[dict[str, Any]]:
        """List tasks within a task list."""
        url = f"{TASKS_BASE_URL}/lists/{task_list_id}/tasks"
        params: dict[str, Any] = {
            "maxResults": max_results,
            "showCompleted": str(show_completed).lower(),
            "showHidden": str(show_hidden).lower(),
        }
        if due_min:
            params["dueMin"] = due_min
        if due_max:
            params["dueMax"] = due_max

        data = await self.client.request("GET", url, params=params)
        items = data.get("items", [])
        return [self._format_task(t) for t in items]

    async def create_task(
        self,
        title: str,
        task_list_id: str = "@default",
        notes: str | None = None,
        due: str | None = None,
    ) -> dict[str, Any]:
        """
        Create a new task.
        due: RFC 3339 timestamp (e.g. 2026-09-27T00:00:00Z).
        """
        if not title or not title.strip():
            raise GoogleInvalidArgumentError("Task title is required.")

        body: dict[str, Any] = {"title": title.strip()}
        if notes:
            body["notes"] = notes
        if due:
            # Ensure due timestamp has RFC 3339 format
            if len(due) == 10 and due.count("-") == 2:
                body["due"] = f"{due}T00:00:00.000Z"
            else:
                body["due"] = due

        url = f"{TASKS_BASE_URL}/lists/{task_list_id}/tasks"
        data = await self.client.request("POST", url, json_data=body)
        logger.info("google_task_created", task_id=data.get("id"), title=title)
        return self._format_task(data)

    async def update_task(
        self,
        task_id: str,
        task_list_id: str = "@default",
        title: str | None = None,
        notes: str | None = None,
        due: str | None = None,
        status: str | None = None,
    ) -> dict[str, Any]:
        """Update fields of an existing task."""
        if not task_id:
            raise GoogleInvalidArgumentError("task_id is required.")

        body: dict[str, Any] = {}
        if title is not None:
            body["title"] = title
        if notes is not None:
            body["notes"] = notes
        if due is not None:
            if len(due) == 10 and due.count("-") == 2:
                body["due"] = f"{due}T00:00:00.000Z"
            else:
                body["due"] = due
        if status is not None:
            body["status"] = status

        url = f"{TASKS_BASE_URL}/lists/{task_list_id}/tasks/{task_id}"
        data = await self.client.request("PATCH", url, json_data=body)
        logger.info("google_task_updated", task_id=task_id)
        return self._format_task(data)

    async def complete_task(
        self, task_id: str, task_list_id: str = "@default"
    ) -> dict[str, Any]:
        """Mark a task as completed."""
        return await self.update_task(
            task_id=task_id,
            task_list_id=task_list_id,
            status="completed",
        )

    async def reopen_task(
        self, task_id: str, task_list_id: str = "@default"
    ) -> dict[str, Any]:
        """Reopen a completed task."""
        return await self.update_task(
            task_id=task_id,
            task_list_id=task_list_id,
            status="needsAction",
        )

    async def delete_task(
        self, task_id: str, task_list_id: str = "@default"
    ) -> dict[str, Any]:
        """Delete a task."""
        if not task_id:
            raise GoogleInvalidArgumentError("task_id is required.")
        url = f"{TASKS_BASE_URL}/lists/{task_list_id}/tasks/{task_id}"
        await self.client.request("DELETE", url)
        logger.info("google_task_deleted", task_id=task_id)
        return {"status": "deleted", "task_id": task_id, "task_list_id": task_list_id}

    def _format_task(self, data: dict[str, Any]) -> dict[str, Any]:
        """Format raw Google Tasks JSON item."""
        return {
            "id": data.get("id"),
            "title": data.get("title", "(No Title)"),
            "status": data.get("status"),
            "due": data.get("due"),
            "completed": data.get("completed"),
            "notes": data.get("notes"),
            "updated": data.get("updated"),
            "parent": data.get("parent"),
            "position": data.get("position"),
        }
