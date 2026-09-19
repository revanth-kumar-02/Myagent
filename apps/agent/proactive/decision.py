"""
proactive.decision — Proactive Decision Engine (V15)

Evaluates relevance scores, security boundaries, and suggested actions to decide:
  - IGNORE: Drop, suppress, or disregard event
  - INFORM: Notify user with an informational update (no action needed)
  - SUGGEST: Propose a recommended action with 1-click execution
  - ASK: Require explicit user confirmation or choice before taking action
  - ACT: Automatically execute pre-authorized, safe, internal actions

Enforces strict safety invariants:
  - Zero permission bypass (routes all tool invocations through PermissionGate)
  - Degrades ACT to ASK/SUGGEST when user has not enabled autonomous execution
  - Prohibits destructive or high-impact autonomous actions
"""

from __future__ import annotations

from typing import Any

import structlog

from proactive.types import (
    EventSourceType,
    EventUrgency,
    NotificationPriority,
    ProactiveAction,
    ProactiveConfig,
    ProactiveDecision,
    ProactiveEvent,
    RelevanceScore,
)

logger = structlog.get_logger(__name__)


class ProactiveDecisionEngine:
    """
    Decides the appropriate proactive response tier (IGNORE, INFORM, SUGGEST, ASK, ACT)
    based on event context, relevance scores, and permission boundaries.
    """

    def __init__(self, config: ProactiveConfig | None = None) -> None:
        self.config = config or ProactiveConfig()

    def decide(
        self,
        event: ProactiveEvent,
        relevance: RelevanceScore,
    ) -> tuple[ProactiveDecision, ProactiveAction | None, NotificationPriority, str]:
        """
        Make a deterministic decision on how to handle the proactive event.

        Returns:
            tuple of (decision, suggested_action, notification_priority, formatted_message)
        """
        # 1. Check if event should be IGNORED
        if not relevance.should_notify or relevance.score < self.config.min_relevance_score:
            logger.debug(
                "proactive_decision_ignore",
                event_id=str(event.event_id),
                relevance_score=relevance.score,
                reasons=relevance.reasons,
            )
            return ProactiveDecision.IGNORE, None, NotificationPriority.LOW, ""

        # Determine default notification priority from event urgency
        priority = self._map_urgency_to_priority(event.urgency)

        # 2. Decision Logic based on Event Source & Subtypes
        subtype = event.data.get("event_subtype", "")

        # A. Task Failures
        if event.source_type == EventSourceType.TASK_LIFECYCLE and subtype == "task_failed":
            error_msg = event.data.get("error_message", "Unknown error")
            goal = event.data.get("goal", "Task")
            action = ProactiveAction(
                tool_name="retry_task",
                params={"task_id": str(event.task_id), "with_replan": True},
                description=f"Retry task '{goal[:40]}' with dynamic replanning",
                requires_permission=True,
                permission_level="normal",
            )
            message = f"Task '{goal}' failed ({error_msg}). Would you like Kora to replan and retry?"
            return ProactiveDecision.ASK, action, NotificationPriority.HIGH, message

        # B. Task Completed
        if event.source_type == EventSourceType.TASK_LIFECYCLE and subtype == "task_completed":
            goal = event.data.get("goal", "Task")
            message = f"Task '{goal}' completed successfully."
            return ProactiveDecision.INFORM, None, NotificationPriority.LOW, message

        # C. Overdue Scheduled Tasks
        if event.source_type == EventSourceType.SCHEDULED_TASK and subtype == "task_overdue":
            goal = event.data.get("goal", "Task")
            action = ProactiveAction(
                tool_name="trigger_task_now",
                params={"task_id": str(event.task_id)},
                description=f"Execute overdue task '{goal[:40]}' immediately",
                requires_permission=True,
            )
            message = f"Scheduled task '{goal}' is overdue. Run it now?"
            return ProactiveDecision.ASK, action, NotificationPriority.HIGH, message

        # D. Project File Changes (Large Workspace Modifications)
        if event.source_type == EventSourceType.PROJECT_FILE_CHANGE:
            total_changes = event.data.get("total_changes", 0)
            action = ProactiveAction(
                tool_name="index_project",
                params={"project_id": str(event.project_id) if event.project_id else ""},
                description="Re-index workspace files for RAG search",
                requires_permission=False,
                permission_level="normal",
            )
            message = f"Detected {total_changes} file changes in workspace. Recommended: refresh search index."

            # If autonomous actions are enabled, safe read-only indexing can ACT; otherwise SUGGEST
            if self.config.allow_autonomous_actions and total_changes < 50:
                return ProactiveDecision.ACT, action, NotificationPriority.LOW, message
            return ProactiveDecision.SUGGEST, action, NotificationPriority.NORMAL, message

        # E. System Diagnostics & Degraded Health
        if event.source_type == EventSourceType.SYSTEM_EVENT and subtype == "system_degraded":
            comp = event.data.get("component", "system")
            msg = event.data.get("status_message", "Degraded")
            action = ProactiveAction(
                tool_name="run_diagnostics",
                params={"component": comp},
                description=f"Run comprehensive diagnostic check on {comp}",
                requires_permission=False,
            )
            message = f"System alert: {comp} is degraded ({msg}). Diagnostic inspection recommended."
            return ProactiveDecision.SUGGEST, action, NotificationPriority.URGENT, message

        # F. Memory Changes & Learned Preferences
        if event.source_type == EventSourceType.MEMORY_CHANGE:
            if subtype == "memory_contradiction":
                message = event.description or "Resolved conflicting memory record."
                return ProactiveDecision.INFORM, None, NotificationPriority.LOW, message
            if subtype == "preference_updated":
                pref = event.data.get("preference_key", "preference")
                val = event.data.get("value", "")
                message = f"Learned new user preference: {pref} = '{val}'."
                return ProactiveDecision.INFORM, None, NotificationPriority.LOW, message

        # G. Automation Rules
        if event.source_type == EventSourceType.AUTOMATION:
            trigger_name = event.data.get("trigger_name", "Automation")
            summary = event.data.get("action_summary", "")
            action = ProactiveAction(
                tool_name="confirm_automation_action",
                params={"trigger": trigger_name},
                description=f"Proceed with automation action for '{trigger_name}'",
                requires_permission=True,
            )
            message = f"Automation '{trigger_name}' triggered: {summary}"
            return ProactiveDecision.SUGGEST, action, NotificationPriority.NORMAL, message

        # H. External Checks
        if event.source_type == EventSourceType.EXTERNAL_CHECK:
            message = event.description or f"External check completed: {event.title}"
            return ProactiveDecision.INFORM, None, priority, message

        # Default fallback: INFORM if description present, else IGNORE
        if event.description:
            return ProactiveDecision.INFORM, None, priority, event.description

        return ProactiveDecision.IGNORE, None, NotificationPriority.LOW, ""

    def _map_urgency_to_priority(self, urgency: EventUrgency) -> NotificationPriority:
        """Map event urgency to notification priority."""
        mapping = {
            EventUrgency.CRITICAL: NotificationPriority.URGENT,
            EventUrgency.HIGH: NotificationPriority.HIGH,
            EventUrgency.NORMAL: NotificationPriority.NORMAL,
            EventUrgency.LOW: NotificationPriority.LOW,
        }
        return mapping.get(urgency, NotificationPriority.NORMAL)
