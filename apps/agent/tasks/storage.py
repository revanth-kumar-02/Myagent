"""
tasks.storage — Task Storage & Persistence (V9)

Provides in-memory and disk-backed persistence for tasks, execution runs,
step records, and state transitions, with secret masking in history payloads.
Guarantees persistent state across server restarts in ~/.kora/automations.json.
"""

from __future__ import annotations

import asyncio
import json
import os
from datetime import datetime, timezone
from pathlib import Path
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

STORAGE_PATH = Path.home() / ".kora" / "automations.json"


class TaskStorage:
    """
    Thread-safe and async-safe repository for task definitions and execution runs.
    Keeps state in-memory and persistently syncs to ~/.kora/automations.json.
    """

    def __init__(self, persistence_file: Path | str | None = None) -> None:
        self._tasks: dict[UUID, TaskDefinition] = {}
        self._lock = asyncio.Lock()
        self._file_path = Path(persistence_file) if persistence_file else STORAGE_PATH
        self._load_from_disk_sync()

    def _load_from_disk_sync(self) -> None:
        """Load tasks from disk synchronously on initialization."""
        try:
            if self._file_path.exists():
                with open(self._file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, list):
                        for item in data:
                            if isinstance(item, dict):
                                task = TaskDefinition.from_dict(item)
                                self._tasks[task.task_id] = task
                logger.info("automations_loaded_from_disk", count=len(self._tasks), path=str(self._file_path))
        except Exception as e:
            logger.error("failed_to_load_automations_from_disk", error=str(e), path=str(self._file_path))

    def _save_to_disk_sync(self) -> None:
        """Atomic write to disk."""
        try:
            self._file_path.parent.mkdir(parents=True, exist_ok=True)
            temp_path = self._file_path.with_suffix(".tmp")
            items = [t.to_dict() for t in self._tasks.values()]
            with open(temp_path, "w", encoding="utf-8") as f:
                json.dump(items, f, indent=2, ensure_ascii=False)
            temp_path.replace(self._file_path)
            logger.debug("automations_saved_to_disk", count=len(items))
        except Exception as e:
            logger.error("failed_to_save_automations_to_disk", error=str(e))

    async def save_task(self, task: TaskDefinition) -> TaskDefinition:
        """Create or update a task definition."""
        async with self._lock:
            task.updated_at = datetime.now(timezone.utc)
            # Mask any secrets that might be in metadata
            task.metadata = sanitize_audit_payload(task.metadata)
            self._tasks[task.task_id] = task
            self._save_to_disk_sync()
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
            self._save_to_disk_sync()
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
                task.last_run_at = history.started_at
                task.last_result = str(history.result)[:300] if history.result else (f"Completed with {len(history.steps)} steps" if history.status == TaskState.COMPLETED else None)
                task.last_error = history.error
                task.updated_at = datetime.now(timezone.utc)
                self._save_to_disk_sync()

    async def delete_task(self, task_id: UUID | str) -> bool:
        """Delete a task from storage."""
        if isinstance(task_id, str):
            task_id = UUID(task_id)
        async with self._lock:
            removed = self._tasks.pop(task_id, None) is not None
            if removed:
                self._save_to_disk_sync()
            return removed

    async def clear(self) -> None:
        """Clear all tasks (useful in testing)."""
        async with self._lock:
            self._tasks.clear()
            self._save_to_disk_sync()
