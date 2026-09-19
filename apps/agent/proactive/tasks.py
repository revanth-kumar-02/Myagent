"""
proactive.tasks — Proactive Task & Follow-up Manager (V15)

Safely creates and schedules autonomous follow-up tasks in response to proactive events:
  - Failed task recovery with dynamic replanning
  - Project re-indexing on significant workspace modifications
  - Strict anti-recursion depth tracking (max_proactive_depth = 2)
  - Duplicate task prevention
"""

from __future__ import annotations

import uuid
from typing import Any

import structlog

from proactive.types import ProactiveConfig, ProactiveEvent
from tasks.manager import DuplicateTaskError, TaskManager
from tasks.types import TaskDefinition, TaskPriority, TriggerConfig, TriggerType

logger = structlog.get_logger(__name__)


class RecursionLimitExceededError(Exception):
    """Raised when proactive follow-up task depth exceeds the configured threshold."""


class ProactiveTaskManager:
    """
    Coordinates follow-up task creation with strict loop and recursion prevention.
    """

    def __init__(
        self,
        task_manager: TaskManager | None = None,
        config: ProactiveConfig | None = None,
    ) -> None:
        self.task_manager = task_manager or TaskManager()
        self.config = config or ProactiveConfig()

    async def create_followup_task(
        self,
        goal: str,
        event: ProactiveEvent,
        priority: TaskPriority = TaskPriority.NORMAL,
        project_id: uuid.UUID | None = None,
        dependencies: list[uuid.UUID | str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> TaskDefinition | None:
        """
        Create a new proactive follow-up task with recursion depth checking.
        """
        # 1. Check parent depth from event metadata or data
        parent_depth = event.data.get("proactive_depth", 0)
        current_depth = parent_depth + 1

        if current_depth > self.config.max_proactive_depth:
            logger.warning(
                "proactive_task_recursion_limit_reached",
                current_depth=current_depth,
                max_depth=self.config.max_proactive_depth,
                goal=goal,
            )
            return None

        task_meta = {
            **(metadata or {}),
            "created_by_proactive_engine": True,
            "proactive_depth": current_depth,
            "origin_event_id": str(event.event_id),
            "origin_source_type": event.source_type.value,
        }

        try:
            task = await self.task_manager.create_task(
                goal=goal,
                priority=priority,
                project_id=project_id or event.project_id,
                dependencies=dependencies,
                metadata=task_meta,
                allow_duplicates=False,
            )
            logger.info(
                "proactive_followup_task_created",
                task_id=str(task.task_id),
                goal=goal,
                depth=current_depth,
            )
            return task
        except DuplicateTaskError as de:
            logger.warning("proactive_task_duplicate_skipped", goal=goal, error=str(de))
            return None
        except Exception as e:
            logger.error("proactive_task_creation_failed", goal=goal, error=str(e))
            return None

    async def retry_failed_task(
        self,
        event: ProactiveEvent,
        project_id: uuid.UUID | None = None,
    ) -> TaskDefinition | None:
        """Create a follow-up retry task for a failed autonomous task."""
        orig_goal = event.data.get("goal", "Task")
        err = event.data.get("error_message", "error")
        new_goal = f"Retry with replanning: {orig_goal}"

        return await self.create_followup_task(
            goal=new_goal,
            event=event,
            priority=TaskPriority.HIGH,
            project_id=project_id or event.project_id,
            metadata={"retry_of_task_id": str(event.task_id) if event.task_id else None, "original_error": err},
        )

    async def schedule_project_reindex(
        self,
        event: ProactiveEvent,
        project_id: uuid.UUID | None = None,
    ) -> TaskDefinition | None:
        """Create a background indexing task on significant workspace modifications."""
        proj = project_id or event.project_id
        if not proj:
            return None

        goal = f"Re-index project workspace {proj}"
        return await self.create_followup_task(
            goal=goal,
            event=event,
            priority=TaskPriority.LOW,
            project_id=proj,
            metadata={"source_event": "file_changes"},
        )
