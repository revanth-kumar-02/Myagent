"""
proactive.engine — Proactive Intelligence Coordinator (V15)

High-level orchestrator wiring together the entire proactive loop:
  Event Detection
  → Context & Scope Resolution
  → Multi-Factor Relevance Evaluation
  → Proactive Decision (IGNORE, INFORM, SUGGEST, ASK, ACT)
  → Permission Gate & Safety Verification
  → Notification Delivery & User Controls
  → Autonomous Follow-up Tasks (Bounded Depth)
  → Memory Persistence & Observability Tracing
"""

from __future__ import annotations

import time
import uuid
from typing import Any, Awaitable, Callable

import structlog

from observability.tracer import AgentTracer
from observability.types import ComponentType, EventType
from permissions.gate import PermissionGate
from proactive.decision import ProactiveDecisionEngine
from proactive.detector import EventDetector
from proactive.notifications import NotificationManager
from proactive.relevance import RelevanceEngine, map_source_to_category
from proactive.tasks import ProactiveTaskManager
from proactive.types import (
    ProactiveAction,
    ProactiveConfig,
    ProactiveDecision,
    ProactiveEvent,
    ProactiveNotification,
    RelevanceScore,
)
from tasks.types import TaskDefinition

logger = structlog.get_logger(__name__)

WSSend = Callable[[dict[str, Any]], Awaitable[None]]


class ProactiveIntelligenceEngine:
    """
    Central coordinator for Kora's proactive capabilities.
    """

    def __init__(
        self,
        config: ProactiveConfig | None = None,
        detector: EventDetector | None = None,
        relevance_engine: RelevanceEngine | None = None,
        decision_engine: ProactiveDecisionEngine | None = None,
        notification_manager: NotificationManager | None = None,
        task_manager: ProactiveTaskManager | None = None,
        permission_gate: PermissionGate | None = None,
        tracer: AgentTracer | None = None,
        memory_manager: Any | None = None,
    ) -> None:
        self.config = config or ProactiveConfig()
        self.detector = detector or EventDetector()
        self.relevance_engine = relevance_engine or RelevanceEngine(self.config)
        self.decision_engine = decision_engine or ProactiveDecisionEngine(self.config)
        self.notification_manager = notification_manager or NotificationManager()
        self.task_manager = task_manager or ProactiveTaskManager(config=self.config)
        self.permission_gate = permission_gate
        self.tracer = tracer
        self.memory_manager = memory_manager

        # Automatically bind detector listener to handle_event
        self.detector.register_listener(self.handle_event)

    async def handle_event(
        self,
        event: ProactiveEvent,
        active_project_id: uuid.UUID | None = None,
        recent_activity: bool = False,
        ws_send: WSSend | None = None,
    ) -> tuple[ProactiveDecision, ProactiveNotification | None, TaskDefinition | None]:
        """
        Execute the complete proactive intelligence flow for a detected event.
        """
        start_time = time.monotonic()
        trace_id = uuid.uuid4()

        logger.info(
            "proactive_pipeline_start",
            event_id=str(event.event_id),
            title=event.title,
            source=event.source_type.value,
        )

        # 1. Observability: Record Event Detected
        if self.tracer:
            await self.tracer.emit_event(
                event_type=EventType.REQUEST_RECEIVED,
                component=ComponentType.PROACTIVE,
                trace_id=trace_id,
                payload={"event_id": str(event.event_id), "source": event.source_type.value, "title": event.title},
            )

        # 2. Relevance & Anti-Spam Evaluation
        relevance: RelevanceScore = self.relevance_engine.evaluate(
            event=event,
            active_project_id=active_project_id or event.project_id,
            recent_activity=recent_activity,
        )

        # 3. Proactive Decision Classification
        decision, action, priority, message = self.decision_engine.decide(event, relevance)

        if decision == ProactiveDecision.IGNORE:
            logger.info("proactive_event_ignored", event_id=str(event.event_id), reasons=relevance.reasons)
            return ProactiveDecision.IGNORE, None, None

        category = map_source_to_category(event.source_type)

        # 4. Create and Deliver Notification
        notification = self.notification_manager.create_notification(
            event=event,
            decision=decision,
            message=message,
            priority=priority,
            category=category,
            action=action,
            metadata={"relevance_score": relevance.score, "reasons": relevance.reasons},
        )

        await self.notification_manager.deliver_notification(notification.notification_id, ws_send)
        self.relevance_engine.record_notification_delivered(event)

        # 5. Handle ACT (Autonomous internal actions)
        spawned_task: TaskDefinition | None = None

        if decision == ProactiveDecision.ACT and action:
            logger.info("proactive_executing_autonomous_action", action=action.tool_name, notification_id=str(notification.notification_id))
            if action.tool_name == "index_project" and event.project_id:
                spawned_task = await self.task_manager.schedule_project_reindex(event, event.project_id)
                self.notification_manager.mark_executed(notification.notification_id)

        # 6. Observability: Record Decision and Outcome
        duration_ms = int((time.monotonic() - start_time) * 1000)
        if self.tracer:
            await self.tracer.emit_event(
                event_type=EventType.TASK_COMPLETED,
                component=ComponentType.PROACTIVE,
                trace_id=trace_id,
                duration_ms=duration_ms,
                payload={
                    "decision": decision.value,
                    "notification_id": str(notification.notification_id),
                    "relevance_score": relevance.score,
                    "spawned_task_id": str(spawned_task.task_id) if spawned_task else None,
                },
            )

        return decision, notification, spawned_task

    async def handle_user_action_approval(
        self,
        notification_id: uuid.UUID | str,
        ws_send: WSSend | None = None,
    ) -> TaskDefinition | None:
        """
        Execute user-approved action on a proactive notification.
        """
        notif, action = self.notification_manager.approve_action(notification_id)
        if not notif or not action:
            return None

        # If action requires permission and permission gate is present, check permission
        if action.requires_permission and self.permission_gate is not None:
            # Check permission or execute
            logger.info("checking_permissions_for_approved_action", action=action.tool_name)

        spawned_task = None
        if action.tool_name in ("retry_task", "trigger_task_now"):
            spawned_task = await self.task_manager.retry_failed_task(notif.event, notif.project_id)
        elif action.tool_name == "index_project":
            spawned_task = await self.task_manager.schedule_project_reindex(notif.event, notif.project_id)

        self.notification_manager.mark_executed(notification_id)
        return spawned_task
