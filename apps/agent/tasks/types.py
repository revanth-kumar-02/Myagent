"""
tasks.types — Task & Automation Engine Data Types (V9)

Defines task states, priorities, trigger types, definitions, step records,
and execution history models.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4


class TaskState(str, enum.Enum):
    """Deterministic states for autonomous tasks."""
    PENDING = "pending"
    PLANNED = "planned"
    RUNNING = "running"
    WAITING = "waiting"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    PAUSED = "paused"


class TaskPriority(str, enum.Enum):
    """Execution priority levels for tasks."""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"


class TriggerType(str, enum.Enum):
    """Supported trigger types for the automation engine."""
    MANUAL = "manual"
    DATE = "date"
    INTERVAL = "interval"
    CRON = "cron"
    EVENT = "event"
    TASK_COMPLETION = "task_completion"
    CONDITION = "condition"


@dataclass
class TriggerConfig:
    """Configuration for automation triggers."""
    trigger_type: TriggerType = TriggerType.MANUAL
    # For DATE triggers (e.g. ISO string or run_date)
    run_date: str | datetime | None = None
    # For INTERVAL triggers (e.g. seconds=30, minutes=5, hours=1)
    interval_seconds: int | None = None
    # For CRON triggers (e.g. "0 9 * * 1-5" or {"minute": "*/15"})
    cron_expr: str | dict[str, Any] | None = None
    # For EVENT triggers (e.g. "file_modified", "build_failed")
    event_name: str | None = None
    # For TASK_COMPLETION triggers (parent task_id to await)
    parent_task_id: UUID | str | None = None
    # For CONDITION triggers (e.g. lambda/expression name or predicate dict)
    condition_expr: str | dict[str, Any] | None = None


@dataclass
class TaskStepRecord:
    """Detailed record of an executed step within a task."""
    step_id: UUID = field(default_factory=uuid4)
    task_id: UUID = field(default_factory=uuid4)
    step_index: int = 0
    goal: str = ""
    tool_name: str | None = None
    tool_params: dict[str, Any] = field(default_factory=dict)
    status: str = "pending"
    output: Any = None
    error: str | None = None
    duration_ms: int = 0
    verified: bool = False
    verification_feedback: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class TaskExecutionHistory:
    """Audit record for a complete task execution run."""
    run_id: UUID = field(default_factory=uuid4)
    task_id: UUID = field(default_factory=uuid4)
    run_number: int = 1
    status: TaskState = TaskState.PENDING
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: datetime | None = None
    duration_ms: int = 0
    steps_completed: int = 0
    retries_count: int = 0
    replan_count: int = 0
    error: str | None = None
    steps: list[TaskStepRecord] = field(default_factory=list)


@dataclass
class TaskDefinition:
    """Core autonomous task definition."""
    task_id: UUID = field(default_factory=uuid4)
    goal: str = ""
    status: TaskState = TaskState.PENDING
    priority: TaskPriority = TaskPriority.NORMAL
    trigger: TriggerConfig = field(default_factory=TriggerConfig)
    dependencies: list[UUID | str] = field(default_factory=list)
    max_retries: int = 3
    timeout_seconds: int = 300
    require_approval_for_tools: bool = True
    project_id: UUID | None = None
    session_id: UUID | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict[str, Any] = field(default_factory=dict)
    execution_history: list[TaskExecutionHistory] = field(default_factory=list)

    @property
    def is_terminal(self) -> bool:
        """Whether the task is in a final, non-resumable state."""
        return self.status in {TaskState.COMPLETED, TaskState.FAILED, TaskState.CANCELLED}

    @property
    def is_active(self) -> bool:
        """Whether the task is currently scheduled or running."""
        return self.status in {TaskState.PENDING, TaskState.PLANNED, TaskState.RUNNING, TaskState.WAITING}
