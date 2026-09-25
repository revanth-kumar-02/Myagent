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
    DRAFT = "draft"
    PENDING = "pending"
    PLANNED = "planned"
    RUNNING = "running"
    WAITING = "waiting"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    PAUSED = "paused"
    ACTIVE = "active"


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
    # For EVENT triggers (e.g. "file_modified", "build_failed", "project_changed")
    event_name: str | None = None
    # For TASK_COMPLETION triggers (parent task_id to await)
    parent_task_id: UUID | str | None = None
    # For CONDITION triggers (e.g. predicate dict: {"key": "git_changes", "op": "==", "value": True})
    condition_expr: str | dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "trigger_type": self.trigger_type.value if isinstance(self.trigger_type, TriggerType) else str(self.trigger_type),
            "run_date": self.run_date.isoformat() if isinstance(self.run_date, datetime) else self.run_date,
            "interval_seconds": self.interval_seconds,
            "cron_expr": self.cron_expr,
            "event_name": self.event_name,
            "parent_task_id": str(self.parent_task_id) if self.parent_task_id else None,
            "condition_expr": self.condition_expr,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "TriggerConfig":
        if not data:
            return cls()
        tt_raw = data.get("trigger_type", "manual")
        try:
            tt = TriggerType(tt_raw.lower())
        except ValueError:
            tt = TriggerType.MANUAL
        return cls(
            trigger_type=tt,
            run_date=data.get("run_date"),
            interval_seconds=data.get("interval_seconds"),
            cron_expr=data.get("cron_expr"),
            event_name=data.get("event_name"),
            parent_task_id=data.get("parent_task_id"),
            condition_expr=data.get("condition_expr"),
        )


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

    def to_dict(self) -> dict[str, Any]:
        return {
            "step_id": str(self.step_id),
            "task_id": str(self.task_id),
            "step_index": self.step_index,
            "goal": self.goal,
            "tool_name": self.tool_name,
            "tool_params": self.tool_params,
            "status": self.status,
            "output": self.output,
            "error": self.error,
            "duration_ms": self.duration_ms,
            "verified": self.verified,
            "verification_feedback": self.verification_feedback,
            "created_at": self.created_at.isoformat() if isinstance(self.created_at, datetime) else str(self.created_at),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TaskStepRecord":
        sid = UUID(data["step_id"]) if "step_id" in data and data["step_id"] else uuid4()
        tid = UUID(data["task_id"]) if "task_id" in data and data["task_id"] else uuid4()
        created = data.get("created_at")
        created_dt = datetime.fromisoformat(created) if isinstance(created, str) else datetime.now(timezone.utc)
        return cls(
            step_id=sid,
            task_id=tid,
            step_index=data.get("step_index", 0),
            goal=data.get("goal", ""),
            tool_name=data.get("tool_name"),
            tool_params=data.get("tool_params") or {},
            status=data.get("status", "pending"),
            output=data.get("output"),
            error=data.get("error"),
            duration_ms=data.get("duration_ms", 0),
            verified=data.get("verified", False),
            verification_feedback=data.get("verification_feedback"),
            created_at=created_dt,
        )


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
    trigger_source: str = "manual"
    model_used: str = "qwen3:1.7b"
    plan: list[dict[str, Any]] = field(default_factory=list)
    result: Any = None
    steps: list[TaskStepRecord] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": str(self.run_id),
            "task_id": str(self.task_id),
            "run_number": self.run_number,
            "status": self.status.value if isinstance(self.status, TaskState) else str(self.status),
            "started_at": self.started_at.isoformat() if isinstance(self.started_at, datetime) else str(self.started_at),
            "completed_at": self.completed_at.isoformat() if isinstance(self.completed_at, datetime) else None,
            "duration_ms": self.duration_ms,
            "steps_completed": self.steps_completed,
            "retries_count": self.retries_count,
            "replan_count": self.replan_count,
            "error": self.error,
            "trigger_source": self.trigger_source,
            "model_used": self.model_used,
            "plan": self.plan,
            "result": self.result,
            "steps": [s.to_dict() for s in self.steps],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TaskExecutionHistory":
        rid = UUID(data["run_id"]) if "run_id" in data and data["run_id"] else uuid4()
        tid = UUID(data["task_id"]) if "task_id" in data and data["task_id"] else uuid4()
        status_raw = data.get("status", "pending")
        try:
            st = TaskState(status_raw)
        except ValueError:
            st = TaskState.PENDING
        started = data.get("started_at")
        started_dt = datetime.fromisoformat(started) if isinstance(started, str) else datetime.now(timezone.utc)
        completed = data.get("completed_at")
        completed_dt = datetime.fromisoformat(completed) if isinstance(completed, str) else None
        steps = [TaskStepRecord.from_dict(s) for s in data.get("steps", []) if isinstance(s, dict)]
        return cls(
            run_id=rid,
            task_id=tid,
            run_number=data.get("run_number", 1),
            status=st,
            started_at=started_dt,
            completed_at=completed_dt,
            duration_ms=data.get("duration_ms", 0),
            steps_completed=data.get("steps_completed", len(steps)),
            retries_count=data.get("retries_count", 0),
            replan_count=data.get("replan_count", 0),
            error=data.get("error"),
            trigger_source=data.get("trigger_source", "manual"),
            model_used=data.get("model_used", "qwen3:1.7b"),
            plan=data.get("plan", []),
            result=data.get("result"),
            steps=steps,
        )


@dataclass
class TaskDefinition:
    """Core autonomous task definition."""
    task_id: UUID = field(default_factory=uuid4)
    name: str = ""
    description: str = ""
    goal: str = ""
    status: TaskState = TaskState.PENDING
    priority: TaskPriority = TaskPriority.NORMAL
    trigger: TriggerConfig = field(default_factory=TriggerConfig)
    dependencies: list[UUID | str] = field(default_factory=list)
    max_retries: int = 3
    timeout_seconds: int = 300
    require_approval_for_tools: bool = False
    allowed_tools: list[str] = field(default_factory=list)
    permission_scope: dict[str, Any] = field(default_factory=dict)
    next_run_at: datetime | None = None
    last_run_at: datetime | None = None
    last_result: str | None = None
    last_error: str | None = None
    condition_logic: dict[str, Any] | None = None
    project_id: UUID | None = None
    session_id: UUID | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict[str, Any] = field(default_factory=dict)
    execution_history: list[TaskExecutionHistory] = field(default_factory=list)

    @property
    def display_name(self) -> str:
        return self.name or (self.goal[:40] + "..." if len(self.goal) > 40 else self.goal) or "Autonomous Task"

    @property
    def is_terminal(self) -> bool:
        """Whether the task is in a final, non-resumable state."""
        return self.status in {TaskState.COMPLETED, TaskState.FAILED, TaskState.CANCELLED}

    @property
    def is_active(self) -> bool:
        """Whether the task is currently scheduled or running."""
        return self.status in {TaskState.PENDING, TaskState.PLANNED, TaskState.RUNNING, TaskState.WAITING, TaskState.ACTIVE}

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": str(self.task_id),
            "id": str(self.task_id),
            "name": self.name or self.display_name,
            "title": self.name or self.display_name,
            "description": self.description,
            "goal": self.goal,
            "status": self.status.value if isinstance(self.status, TaskState) else str(self.status),
            "priority": self.priority.value if isinstance(self.priority, TaskPriority) else str(self.priority),
            "trigger": self.trigger.to_dict(),
            "trigger_type": self.trigger.trigger_type.value if isinstance(self.trigger.trigger_type, TriggerType) else str(self.trigger.trigger_type),
            "dependencies": [str(d) for d in self.dependencies],
            "max_retries": self.max_retries,
            "timeout_seconds": self.timeout_seconds,
            "require_approval_for_tools": self.require_approval_for_tools,
            "allowed_tools": self.allowed_tools,
            "permission_scope": self.permission_scope,
            "next_run_at": self.next_run_at.isoformat() if isinstance(self.next_run_at, datetime) else None,
            "last_run_at": self.last_run_at.isoformat() if isinstance(self.last_run_at, datetime) else None,
            "last_result": self.last_result,
            "last_error": self.last_error,
            "condition_logic": self.condition_logic,
            "project_id": str(self.project_id) if self.project_id else None,
            "session_id": str(self.session_id) if self.session_id else None,
            "created_at": self.created_at.isoformat() if isinstance(self.created_at, datetime) else str(self.created_at),
            "updated_at": self.updated_at.isoformat() if isinstance(self.updated_at, datetime) else str(self.updated_at),
            "metadata": self.metadata,
            "execution_count": len(self.execution_history),
            "execution_history": [h.to_dict() for h in self.execution_history[-10:]],  # Most recent 10 in summary
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TaskDefinition":
        tid_raw = data.get("task_id") or data.get("id") or str(uuid4())
        tid = UUID(tid_raw) if isinstance(tid_raw, str) else tid_raw
        st_raw = data.get("status", "pending")
        try:
            st = TaskState(st_raw)
        except ValueError:
            st = TaskState.PENDING
        pr_raw = data.get("priority", "normal")
        try:
            pr = TaskPriority(pr_raw)
        except ValueError:
            pr = TaskPriority.NORMAL

        created = data.get("created_at")
        created_dt = datetime.fromisoformat(created) if isinstance(created, str) else datetime.now(timezone.utc)
        updated = data.get("updated_at")
        updated_dt = datetime.fromisoformat(updated) if isinstance(updated, str) else datetime.now(timezone.utc)
        next_run = data.get("next_run_at")
        next_run_dt = datetime.fromisoformat(next_run) if isinstance(next_run, str) else None
        last_run = data.get("last_run_at")
        last_run_dt = datetime.fromisoformat(last_run) if isinstance(last_run, str) else None

        pid_raw = data.get("project_id")
        pid = UUID(pid_raw) if pid_raw and isinstance(pid_raw, str) else None
        sid_raw = data.get("session_id")
        sid = UUID(sid_raw) if sid_raw and isinstance(sid_raw, str) else None

        trigger_data = data.get("trigger")
        trigger = TriggerConfig.from_dict(trigger_data) if isinstance(trigger_data, dict) else TriggerConfig()
        if not trigger_data and "trigger_type" in data:
            trigger = TriggerConfig.from_dict(data)

        history = [
            TaskExecutionHistory.from_dict(h)
            for h in data.get("execution_history", [])
            if isinstance(h, dict)
        ]

        return cls(
            task_id=tid,
            name=data.get("name") or data.get("title") or "",
            description=data.get("description", ""),
            goal=data.get("goal", ""),
            status=st,
            priority=pr,
            trigger=trigger,
            dependencies=[UUID(d) if isinstance(d, str) else d for d in data.get("dependencies", [])],
            max_retries=data.get("max_retries", 3),
            timeout_seconds=data.get("timeout_seconds", 300),
            require_approval_for_tools=data.get("require_approval_for_tools", False),
            allowed_tools=data.get("allowed_tools", []),
            permission_scope=data.get("permission_scope", {}),
            next_run_at=next_run_dt,
            last_run_at=last_run_dt,
            last_result=data.get("last_result"),
            last_error=data.get("last_error"),
            condition_logic=data.get("condition_logic"),
            project_id=pid,
            session_id=sid,
            created_at=created_dt,
            updated_at=updated_dt,
            metadata=data.get("metadata", {}),
            execution_history=history,
        )
