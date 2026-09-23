"""
tools.scheduler — Task & Automation Tools (V9)

Tools:
  - ScheduleTaskTool: Create and schedule a one-time or recurring autonomous task
  - CancelTaskTool: Cancel an existing task
  - ListTasksTool: List currently managed tasks and states
  - PauseTaskTool: Pause a running or scheduled task
  - ResumeTaskTool: Resume a paused task
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from uuid import UUID

from tools.base import BaseTool
from tools.types import PermissionLevel, ToolCategory, ToolResult

if TYPE_CHECKING:
    from tasks.automation import AutomationEngine
    from tasks.manager import TaskManager


class ScheduleTaskTool(BaseTool):
    """Schedule a new one-time, interval, or cron autonomous task."""

    def __init__(self, task_manager: TaskManager | None = None, automation_engine: AutomationEngine | None = None) -> None:
        super().__init__()
        self._task_manager = task_manager
        self._automation_engine = automation_engine

    @property
    def task_manager(self) -> TaskManager:
        if self._task_manager is None:
            from tasks.manager import TaskManager
            self._task_manager = TaskManager()
        return self._task_manager

    @property
    def automation_engine(self) -> AutomationEngine | None:
        return self._automation_engine

    @property
    def tool_id(self) -> str:
        return "schedule_task"

    @property
    def category(self) -> ToolCategory:
        return ToolCategory.SYSTEM

    @property
    def description(self) -> str:
        return "Schedule a recurring or one-time autonomous task using cron, interval, or date."

    @property
    def permission_level(self) -> PermissionLevel:
        return PermissionLevel.EXTERNAL_ACTION

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "goal": {"type": "string", "description": "Goal or instruction for the autonomous task"},
                "trigger_type": {"type": "string", "enum": ["manual", "date", "interval", "cron", "event"], "default": "manual"},
                "trigger_params": {"type": "object", "description": "Optional parameters like interval_seconds, cron_expr, run_date, event_name"},
                "priority": {"type": "string", "enum": ["low", "normal", "high", "critical"], "default": "normal"},
            },
            "required": ["goal"],
        }

    async def execute(self, params: dict[str, Any] | None = None, **kwargs: Any) -> ToolResult:
        from tasks.types import TaskPriority, TriggerConfig, TriggerType

        p = {**(params or {}), **kwargs}
        goal = p["goal"]
        trig_type_str = p.get("trigger_type", "manual")
        trig_params = p.get("trigger_params", {})
        priority_str = p.get("priority", "normal")

        try:
            trig_type = TriggerType(trig_type_str)
            priority = TaskPriority(priority_str)
        except ValueError as e:
            return self._make_result(error=f"Invalid parameter value: {e}")

        trigger_cfg = TriggerConfig(
            trigger_type=trig_type,
            run_date=trig_params.get("run_date"),
            interval_seconds=trig_params.get("interval_seconds"),
            cron_expr=trig_params.get("cron_expr"),
            event_name=trig_params.get("event_name"),
            parent_task_id=trig_params.get("parent_task_id"),
        )

        try:
            task = await self.task_manager.create_task(
                goal=goal,
                priority=priority,
                trigger=trigger_cfg,
            )

            if self.automation_engine:
                await self.automation_engine.schedule_task(task)

            return self._make_result(
                output={
                    "task_id": str(task.task_id),
                    "goal": task.goal,
                    "status": task.status.value,
                    "priority": task.priority.value,
                    "trigger_type": task.trigger.trigger_type.value,
                    "scheduled": True,
                }
            )
        except Exception as e:
            return self._make_result(error=f"Failed to schedule task: {e}")


class CancelTaskTool(BaseTool):
    """Cancel an existing autonomous task."""

    def __init__(self, task_manager: TaskManager | None = None, automation_engine: AutomationEngine | None = None) -> None:
        super().__init__()
        self._task_manager = task_manager
        self._automation_engine = automation_engine

    @property
    def task_manager(self) -> TaskManager:
        if self._task_manager is None:
            from tasks.manager import TaskManager
            self._task_manager = TaskManager()
        return self._task_manager

    @property
    def automation_engine(self) -> AutomationEngine | None:
        return self._automation_engine

    @property
    def tool_id(self) -> str:
        return "cancel_task"

    @property
    def category(self) -> ToolCategory:
        return ToolCategory.SYSTEM

    @property
    def description(self) -> str:
        return "Cancel an existing task by its task_id."

    @property
    def permission_level(self) -> PermissionLevel:
        return PermissionLevel.EXTERNAL_ACTION

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "task_id": {"type": "string", "description": "Unique UUID of the task to cancel"},
                "reason": {"type": "string", "description": "Optional cancellation reason"},
            },
            "required": ["task_id"],
        }

    async def execute(self, params: dict[str, Any] | None = None, **kwargs: Any) -> ToolResult:
        p = {**(params or {}), **kwargs}
        task_id = p["task_id"]
        reason = p.get("reason", "Cancelled via tool")
        try:
            task = await self.task_manager.cancel_task(task_id, reason=reason)
            if self.automation_engine:
                await self.automation_engine.unschedule_task(task.task_id)

            return self._make_result(
                output={"task_id": str(task.task_id), "status": task.status.value, "cancelled": True}
            )
        except Exception as e:
            return self._make_result(error=f"Failed to cancel task: {e}")


class ListTasksTool(BaseTool):
    """List currently tracked tasks."""

    def __init__(self, task_manager: TaskManager | None = None) -> None:
        super().__init__()
        self._task_manager = task_manager

    @property
    def task_manager(self) -> TaskManager:
        if self._task_manager is None:
            from tasks.manager import TaskManager
            self._task_manager = TaskManager()
        return self._task_manager

    @property
    def tool_id(self) -> str:
        return "list_tasks"

    @property
    def category(self) -> ToolCategory:
        return ToolCategory.SYSTEM

    @property
    def description(self) -> str:
        return "List all current autonomous tasks and their execution states."

    @property
    def permission_level(self) -> PermissionLevel:
        return PermissionLevel.READ

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "status": {"type": "string", "description": "Optional status filter (e.g. pending, running, completed)"},
            },
        }

    async def execute(self, params: dict[str, Any] | None = None, **kwargs: Any) -> ToolResult:
        p = {**(params or {}), **kwargs}
        tasks = await self.task_manager.list_tasks()
        status_filter = p.get("status")
        if status_filter:
            tasks = [t for t in tasks if t.status.value == status_filter]

        return self._make_result(
            output={
                "count": len(tasks),
                "tasks": [
                    {
                        "task_id": str(t.task_id),
                        "goal": t.goal,
                        "status": t.status.value,
                        "priority": t.priority.value,
                        "trigger_type": t.trigger.trigger_type.value,
                    }
                    for t in tasks
                ],
            }
        )


class PauseTaskTool(BaseTool):
    """Pause a running or scheduled task."""

    def __init__(self, task_manager: TaskManager | None = None, automation_engine: AutomationEngine | None = None) -> None:
        super().__init__()
        self._task_manager = task_manager
        self._automation_engine = automation_engine

    @property
    def task_manager(self) -> TaskManager:
        if self._task_manager is None:
            from tasks.manager import TaskManager
            self._task_manager = TaskManager()
        return self._task_manager

    @property
    def automation_engine(self) -> AutomationEngine | None:
        return self._automation_engine

    @property
    def tool_id(self) -> str:
        return "pause_task"

    @property
    def category(self) -> ToolCategory:
        return ToolCategory.SYSTEM

    @property
    def description(self) -> str:
        return "Pause an active or scheduled task."

    @property
    def permission_level(self) -> PermissionLevel:
        return PermissionLevel.EXTERNAL_ACTION

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "task_id": {"type": "string", "description": "Task ID to pause"},
            },
            "required": ["task_id"],
        }

    async def execute(self, params: dict[str, Any] | None = None, **kwargs: Any) -> ToolResult:
        p = {**(params or {}), **kwargs}
        task_id = p["task_id"]
        try:
            task = await self.task_manager.pause_task(task_id)
            if self.automation_engine:
                await self.automation_engine.pause_schedule(task.task_id)
            return self._make_result(output={"task_id": str(task.task_id), "status": task.status.value, "paused": True})
        except Exception as e:
            return self._make_result(error=f"Failed to pause task: {e}")


class ResumeTaskTool(BaseTool):
    """Resume a paused task."""

    def __init__(self, task_manager: TaskManager | None = None, automation_engine: AutomationEngine | None = None) -> None:
        super().__init__()
        self._task_manager = task_manager
        self._automation_engine = automation_engine

    @property
    def task_manager(self) -> TaskManager:
        if self._task_manager is None:
            from tasks.manager import TaskManager
            self._task_manager = TaskManager()
        return self._task_manager

    @property
    def automation_engine(self) -> AutomationEngine | None:
        return self._automation_engine

    @property
    def tool_id(self) -> str:
        return "resume_task"

    @property
    def category(self) -> ToolCategory:
        return ToolCategory.SYSTEM

    @property
    def description(self) -> str:
        return "Resume a previously paused task."

    @property
    def permission_level(self) -> PermissionLevel:
        return PermissionLevel.EXTERNAL_ACTION

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "task_id": {"type": "string", "description": "Task ID to resume"},
            },
            "required": ["task_id"],
        }

    async def execute(self, params: dict[str, Any] | None = None, **kwargs: Any) -> ToolResult:
        p = {**(params or {}), **kwargs}
        task_id = p["task_id"]
        try:
            task = await self.task_manager.resume_task(task_id)
            if self.automation_engine:
                await self.automation_engine.resume_schedule(task.task_id)
            return self._make_result(output={"task_id": str(task.task_id), "status": task.status.value, "resumed": True})
        except Exception as e:
            return self._make_result(error=f"Failed to resume task: {e}")
