"""
proactive.detector — Event Detection Subsystem (V15)

Monitors, captures, and normalizes events originating from:
  - Scheduled tasks and autonomous task lifecycles (completion, failure, timeout)
  - Project file changes and workspace modifications
  - Automation schedule triggers and event rules
  - System diagnostics and component health degradations
  - Long-term memory modifications and detected contradictions
  - Configurable external checks
"""

from __future__ import annotations

import uuid
from typing import Any, Awaitable, Callable

import structlog

from proactive.types import (
    EventSourceType,
    EventUrgency,
    ProactiveEvent,
)

logger = structlog.get_logger(__name__)

EventListener = Callable[[ProactiveEvent], Awaitable[None]]


class EventDetector:
    """
    Central event ingestion and detection engine.
    Normalizes raw environmental events into typed ProactiveEvent records.
    """

    def __init__(self) -> None:
        self._listeners: list[EventListener] = []

    def register_listener(self, listener: EventListener) -> None:
        """Register an async callback invoked whenever an event is emitted."""
        if listener not in self._listeners:
            self._listeners.append(listener)

    def unregister_listener(self, listener: EventListener) -> None:
        """Remove a previously registered listener."""
        if listener in self._listeners:
            self._listeners.remove(listener)

    async def emit(self, event: ProactiveEvent) -> ProactiveEvent:
        """Emit a normalized proactive event to all registered listeners."""
        logger.info(
            "proactive_event_detected",
            event_id=str(event.event_id),
            source=event.source_type.value,
            title=event.title,
            urgency=event.urgency.value,
            project_id=str(event.project_id) if event.project_id else None,
        )

        for listener in list(self._listeners):
            try:
                await listener(event)
            except Exception as e:
                logger.error("event_listener_failed", error=str(e), event_id=str(event.event_id))

        return event

    # ── Task Lifecycle Event Detectors ─────────────────────────────────────────

    async def on_task_completed(
        self,
        task_id: uuid.UUID | str,
        goal: str,
        project_id: uuid.UUID | None = None,
        duration_ms: int = 0,
        result_summary: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> ProactiveEvent:
        """Detect and emit a task completion event."""
        task_uuid = uuid.UUID(str(task_id)) if task_id else None
        event = ProactiveEvent(
            source_type=EventSourceType.TASK_LIFECYCLE,
            title=f"Task Completed: {goal[:60]}",
            description=result_summary or f"Task '{goal}' finished successfully in {duration_ms}ms.",
            project_id=project_id,
            task_id=task_uuid,
            urgency=EventUrgency.LOW,
            importance=0.4,
            data={
                "event_subtype": "task_completed",
                "goal": goal,
                "duration_ms": duration_ms,
                "result_summary": result_summary,
                "metadata": metadata or {},
            },
        )
        return await self.emit(event)

    async def on_task_failed(
        self,
        task_id: uuid.UUID | str,
        goal: str,
        error_message: str,
        project_id: uuid.UUID | None = None,
        replan_count: int = 0,
        metadata: dict[str, Any] | None = None,
    ) -> ProactiveEvent:
        """Detect and emit a task failure event."""
        task_uuid = uuid.UUID(str(task_id)) if task_id else None
        event = ProactiveEvent(
            source_type=EventSourceType.TASK_LIFECYCLE,
            title=f"Task Failed: {goal[:60]}",
            description=f"Task '{goal}' failed with error: {error_message}",
            project_id=project_id,
            task_id=task_uuid,
            urgency=EventUrgency.HIGH,
            importance=0.85,
            data={
                "event_subtype": "task_failed",
                "goal": goal,
                "error_message": error_message,
                "replan_count": replan_count,
                "metadata": metadata or {},
            },
        )
        return await self.emit(event)

    async def on_task_overdue(
        self,
        task_id: uuid.UUID | str,
        goal: str,
        scheduled_for: str,
        project_id: uuid.UUID | None = None,
    ) -> ProactiveEvent:
        """Detect and emit an overdue scheduled task event."""
        task_uuid = uuid.UUID(str(task_id)) if task_id else None
        event = ProactiveEvent(
            source_type=EventSourceType.SCHEDULED_TASK,
            title=f"Scheduled Task Overdue: {goal[:60]}",
            description=f"Task was scheduled for {scheduled_for} but has not executed.",
            project_id=project_id,
            task_id=task_uuid,
            urgency=EventUrgency.HIGH,
            importance=0.75,
            data={
                "event_subtype": "task_overdue",
                "goal": goal,
                "scheduled_for": scheduled_for,
            },
        )
        return await self.emit(event)

    # ── Project & Workspace Event Detectors ────────────────────────────────────

    async def on_files_changed(
        self,
        project_id: uuid.UUID | None,
        files_added: list[str] | None = None,
        files_modified: list[str] | None = None,
        files_deleted: list[str] | None = None,
    ) -> ProactiveEvent:
        """Detect significant file additions, modifications, or deletions."""
        added = files_added or []
        mod = files_modified or []
        deleted = files_deleted or []
        total_changes = len(added) + len(mod) + len(deleted)

        urgency = EventUrgency.NORMAL
        importance = 0.5
        if total_changes > 10:
            urgency = EventUrgency.NORMAL
            importance = 0.7

        event = ProactiveEvent(
            source_type=EventSourceType.PROJECT_FILE_CHANGE,
            title=f"Project Workspace Updated ({total_changes} files)",
            description=f"{len(added)} added, {len(mod)} modified, {len(deleted)} deleted.",
            project_id=project_id,
            urgency=urgency,
            importance=importance,
            data={
                "files_added": added,
                "files_modified": mod,
                "files_deleted": deleted,
                "total_changes": total_changes,
            },
        )
        return await self.emit(event)

    # ── Memory & Context Event Detectors ───────────────────────────────────────

    async def on_memory_contradiction(
        self,
        old_memory_id: uuid.UUID | str,
        old_content: str,
        new_content: str,
        project_id: uuid.UUID | None = None,
    ) -> ProactiveEvent:
        """Detect when a new fact or user instruction contradicts earlier stored memory."""
        event = ProactiveEvent(
            source_type=EventSourceType.MEMORY_CHANGE,
            title="Memory Contradiction Resolved",
            description=f"Updated older memory '{old_content[:40]}...' with newer insight '{new_content[:40]}...'",
            project_id=project_id,
            urgency=EventUrgency.LOW,
            importance=0.6,
            data={
                "event_subtype": "memory_contradiction",
                "old_memory_id": str(old_memory_id),
                "old_content": old_content,
                "new_content": new_content,
            },
        )
        return await self.emit(event)

    async def on_user_preference_updated(
        self,
        preference_key: str,
        value: Any,
        project_id: uuid.UUID | None = None,
    ) -> ProactiveEvent:
        """Detect when a user preference is updated or learned."""
        event = ProactiveEvent(
            source_type=EventSourceType.MEMORY_CHANGE,
            title=f"User Preference Learned: {preference_key}",
            description=f"Adjusted preference '{preference_key}' to '{value}' based on recent interactions.",
            project_id=project_id,
            urgency=EventUrgency.LOW,
            importance=0.5,
            data={
                "event_subtype": "preference_updated",
                "preference_key": preference_key,
                "value": value,
            },
        )
        return await self.emit(event)

    # ── System Diagnostics Event Detectors ─────────────────────────────────────

    async def on_system_health_degraded(
        self,
        component_name: str,
        error_rate: float,
        status_message: str,
    ) -> ProactiveEvent:
        """Detect component health degradation or elevated failure rates."""
        event = ProactiveEvent(
            source_type=EventSourceType.SYSTEM_EVENT,
            title=f"System Health Degraded: {component_name}",
            description=f"Component '{component_name}' reported degraded state: {status_message} (Error rate: {error_rate:.1%})",
            urgency=EventUrgency.HIGH,
            importance=0.9,
            data={
                "event_subtype": "system_degraded",
                "component": component_name,
                "error_rate": error_rate,
                "status_message": status_message,
            },
        )
        return await self.emit(event)

    # ── Automation & External Check Detectors ──────────────────────────────────

    async def on_automation_triggered(
        self,
        trigger_name: str,
        action_summary: str,
        project_id: uuid.UUID | None = None,
        details: dict[str, Any] | None = None,
    ) -> ProactiveEvent:
        """Detect an automation rule or scheduled cron trigger firing."""
        event = ProactiveEvent(
            source_type=EventSourceType.AUTOMATION,
            title=f"Automation Triggered: {trigger_name}",
            description=action_summary,
            project_id=project_id,
            urgency=EventUrgency.NORMAL,
            importance=0.6,
            data={
                "trigger_name": trigger_name,
                "action_summary": action_summary,
                "details": details or {},
            },
        )
        return await self.emit(event)

    async def on_external_check(
        self,
        check_name: str,
        status: str,
        message: str,
        urgency: EventUrgency = EventUrgency.NORMAL,
        project_id: uuid.UUID | None = None,
        data: dict[str, Any] | None = None,
    ) -> ProactiveEvent:
        """Detect results from configurable external checks (git status, API health, etc.)."""
        event = ProactiveEvent(
            source_type=EventSourceType.EXTERNAL_CHECK,
            title=f"External Check: {check_name} ({status})",
            description=message,
            project_id=project_id,
            urgency=urgency,
            importance=0.65 if urgency != EventUrgency.LOW else 0.4,
            data={"check_name": check_name, "status": status, **(data or {})},
        )
        return await self.emit(event)
