"""tools.scheduler — APScheduler Task Tools."""
from __future__ import annotations
from typing import Any
from tools.base import BaseTool
from tools.types import ToolResult


class ScheduleTaskTool(BaseTool):
    name = "schedule_task"
    description = "Schedule a recurring or one-time task using a cron expression or delay."
    parameters = {
        "type": "object",
        "properties": {
            "task_id": {"type": "string", "description": "Unique identifier for the task"},
            "description": {"type": "string"},
            "trigger": {"type": "string", "enum": ["cron", "interval", "date"]},
            "trigger_params": {"type": "object"},
            "action": {"type": "string", "description": "Agent instruction to run when triggered"},
        },
        "required": ["task_id", "description", "trigger", "trigger_params", "action"],
    }

    async def execute(self, params: dict[str, Any]) -> ToolResult:
        raise NotImplementedError  # TODO: APScheduler implementation in feature phase


class CancelTaskTool(BaseTool):
    name = "cancel_task"
    description = "Cancel a previously scheduled task by its task_id."
    parameters = {
        "type": "object",
        "properties": {"task_id": {"type": "string"}},
        "required": ["task_id"],
    }

    async def execute(self, params: dict[str, Any]) -> ToolResult:
        raise NotImplementedError  # TODO: implement in feature phase
