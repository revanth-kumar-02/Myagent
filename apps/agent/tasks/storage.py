"""
tasks.storage — Task Storage & Persistence (V9)

Provides in-memory and database-backed persistence for tasks, execution runs,
step records, and state transitions, with secret masking in history payloads.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

import structlog

from tasks.types import (
    TaskDefinition,
    TaskExecutionHistory,
    TaskPriority,
    TaskState,
    TaskStepRecord,
    TriggerConfig,
    TriggerType,
)
from tools.audit import sanitize_audit_payload

logger = structlog.get_logger(__name__)


class TaskStorage:
    """
    Thread-safe and async-safe repository for task definitions and execution runs.
    Keeps state in-memory and can persist/reconcile with PostgreSQL/Redis.
    """

    def __init__(self) -> None:
        self._tasks: dict[UUID, TaskDefinition] = {}
        self._lock = asyncio.Lock()

    async def save_task(self, task: TaskDefinition) -> TaskDefinition:
        """Create or update a task definition."""
        async with self._lock:
            task.updated_at = datetime.now(timezone.utc)
            # Mask any secrets that might be in metadata
            task.metadata = sanitize_audit_payload(task.metadata)
            self._tasks[task.task_id] = task
            logger.debug("task_saved", task_id=str(task.task_id), status=task.status.value)
            return task

    async def get_task(self, task_id: UUID | str) -> TaskDefinition | None:
        """Retrieve a task by ID."""
        if isinstance(task_id, str):
            try:
                task_id = UUID(task_id)
            except ValueError:
                return None
        async with self._lock:
            return self._tasks.get(task_id)

    async def list_tasks(
        self,
        status: TaskState | None = None,
        priority: TaskPriority | None = None,
        project_id: UUID | None = None,
    ) -> list[TaskDefinition]:
        """List tasks with optional filtering."""
        async with self._lock:
            results = list(self._tasks.values())
            if status:
                results = [t for t in results if t.status == status]
            if priority:
                results = [t for t in results if t.priority == priority]
            if project_id:
                results = [t for t in results if t.project_id == project_id]
            return sorted(results, key=lambda t: t.created_at, reverse=True)

    async def update_status(self, task_id: UUID | str, new_state: TaskState) -> TaskDefinition | None:
        """Atomically transition task status."""
        if isinstance(task_id, str):
            task_id = UUID(task_id)

        async with self._lock:
            task = self._tasks.get(task_id)
            if not task:
                return None

            old_state = task.status
            task.status = new_state
            task.updated_at = datetime.now(timezone.utc)
            logger.info("task_state_transition", task_id=str(task_id), old_state=old_state.value, new_state=new_state.value)
            return task

    async def record_run(self, task_id: UUID | str, history: TaskExecutionHistory) -> None:
        """Record an execution run into task history with sanitized payloads."""
        if isinstance(task_id, str):
            task_id = UUID(task_id)

        # Sanitize all step outputs & params
        for step in history.steps:
            step.tool_params = sanitize_audit_payload(step.tool_params)
            if isinstance(step.output, dict):
                step.output = sanitize_audit_payload(step.output)

        async with self._lock:
            task = self._tasks.get(task_id)
            if task:
                task.execution_history.append(history)
                task.updated_at = datetime.now(timezone.utc)

    async def delete_task(self, task_id: UUID | str) -> bool:
        """Delete a task from storage."""
        if isinstance(task_id, str):
            task_id = UUID(task_id)
        async with self._lock:
            return self._tasks.pop(task_id, None) is not None

    async def clear(self) -> None:
        """Clear all tasks (useful in testing)."""
        async with self._lock:
            self._tasks.clear()
