"""
tasks.manager — Central Task Manager (V9)

Manages the lifecycle of one-time, recurring, scheduled, multi-step, dependent,
and long-running tasks. Enforces duplicate prevention, dependency resolution,
and crash/restart recovery.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

import structlog

from tasks.storage import TaskStorage
from tasks.types import (
    TaskDefinition,
    TaskPriority,
    TaskState,
    TriggerConfig,
    TriggerType,
)

logger = structlog.get_logger(__name__)


class TaskManagerError(Exception):
    """Base exception for task manager errors."""


class DuplicateTaskError(TaskManagerError):
    """Raised when an identical active task already exists."""


class TaskNotFoundError(TaskManagerError):
    """Raised when a task is not found."""


class DependencyUnmetError(TaskManagerError):
    """Raised when task dependencies are not completed."""


class TaskManager:
    """
    Central Task Manager coordinating task lifecycle, dependencies,
    duplicate prevention, and crash recovery.
    """

    def __init__(self, storage: TaskStorage | None = None) -> None:
        self.storage = storage or TaskStorage()

    async def create_task(
        self,
        goal: str,
        priority: TaskPriority = TaskPriority.NORMAL,
        trigger: TriggerConfig | None = None,
        dependencies: list[UUID | str] | None = None,
        max_retries: int = 3,
        timeout_seconds: int = 300,
        project_id: UUID | None = None,
        session_id: UUID | None = None,
        metadata: dict[str, Any] | None = None,
        allow_duplicates: bool = False,
    ) -> TaskDefinition:
        """
        Create and persist a new autonomous task.
        Prevents duplicate active tasks with identical goal unless allow_duplicates is True.
        """
        if not goal or not goal.strip():
            raise TaskManagerError("Task goal cannot be empty")

        clean_goal = goal.strip()

        # Duplicate check: check if an identical goal is already PENDING/RUNNING/PLANNED
        if not allow_duplicates:
            active_tasks = await self.storage.list_tasks()
            for existing in active_tasks:
                if (
                    existing.is_active
                    and existing.goal.strip().lower() == clean_goal.lower()
                    and (existing.project_id == project_id)
                ):
                    logger.warning("duplicate_task_rejected", goal=clean_goal, existing_id=str(existing.task_id))
                    raise DuplicateTaskError(
                        f"An active task with goal '{clean_goal}' already exists (ID: {existing.task_id})"
                    )

        task = TaskDefinition(
            task_id=uuid4(),
            goal=clean_goal,
            status=TaskState.PENDING,
            priority=priority,
            trigger=trigger or TriggerConfig(),
            dependencies=dependencies or [],
            max_retries=max_retries,
            timeout_seconds=timeout_seconds,
            project_id=project_id,
            session_id=session_id,
            metadata=metadata or {},
        )

        await self.storage.save_task(task)
        logger.info("task_created", task_id=str(task.task_id), goal=clean_goal, trigger=task.trigger.trigger_type.value)
        return task

    async def get_task(self, task_id: UUID | str) -> TaskDefinition:
        """Get task definition or raise TaskNotFoundError."""
        task = await self.storage.get_task(task_id)
        if not task:
            raise TaskNotFoundError(f"Task {task_id} not found")
        return task

    async def list_tasks(
        self,
        status: TaskState | None = None,
        priority: TaskPriority | None = None,
        project_id: UUID | None = None,
    ) -> list[TaskDefinition]:
        """List stored tasks matching criteria."""
        return await self.storage.list_tasks(status=status, priority=priority, project_id=project_id)

    async def pause_task(self, task_id: UUID | str) -> TaskDefinition:
        """Pause a pending or scheduled task."""
        task = await self.get_task(task_id)
        if task.status in {TaskState.COMPLETED, TaskState.FAILED, TaskState.CANCELLED}:
            raise TaskManagerError(f"Cannot pause task in terminal state: {task.status.value}")

        updated = await self.storage.update_status(task.task_id, TaskState.PAUSED)
        logger.info("task_paused", task_id=str(task.task_id))
        return updated or task

    async def resume_task(self, task_id: UUID | str) -> TaskDefinition:
        """Resume a paused task."""
        task = await self.get_task(task_id)
        if task.status != TaskState.PAUSED:
            raise TaskManagerError(f"Task is not paused (current state: {task.status.value})")

        updated = await self.storage.update_status(task.task_id, TaskState.PENDING)
        logger.info("task_resumed", task_id=str(task.task_id))
        return updated or task

    async def cancel_task(self, task_id: UUID | str, reason: str = "Cancelled by user") -> TaskDefinition:
        """Cancel a task."""
        task = await self.get_task(task_id)
        if task.status == TaskState.COMPLETED:
            raise TaskManagerError("Cannot cancel an already completed task")

        task.metadata["cancellation_reason"] = reason
        await self.storage.save_task(task)
        updated = await self.storage.update_status(task.task_id, TaskState.CANCELLED)
        logger.info("task_cancelled", task_id=str(task.task_id), reason=reason)
        return updated or task

    async def check_dependencies_met(self, task_id: UUID | str) -> bool:
        """
        Verify whether all prerequisite tasks in `dependencies` are in COMPLETED state.
        """
        task = await self.get_task(task_id)
        if not task.dependencies:
            return True

        for dep_id in task.dependencies:
            dep_task = await self.storage.get_task(dep_id)
            if not dep_task or dep_task.status != TaskState.COMPLETED:
                return False

        return True

    async def recover_on_startup(self) -> int:
        """
        Crash & restart recovery:
        Finds any tasks left in RUNNING or PLANNED states upon restart and safely resets
        them to PENDING so they can be resumed cleanly.
        """
        all_tasks = await self.storage.list_tasks()
        recovered_count = 0
        for task in all_tasks:
            if task.status in {TaskState.RUNNING, TaskState.PLANNED}:
                logger.warning(
                    "recovering_abandoned_task",
                    task_id=str(task.task_id),
                    previous_state=task.status.value,
                )
                task.metadata["recovered_after_crash"] = True
                await self.storage.save_task(task)
                await self.storage.update_status(task.task_id, TaskState.PENDING)
                recovered_count += 1

        logger.info("startup_recovery_complete", recovered_count=recovered_count)
        return recovered_count
