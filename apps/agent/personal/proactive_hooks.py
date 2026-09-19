"""
personal.proactive_hooks — Proactive Goal & Deadline Detection (V17)

Monitors active goals, milestones, and deadlines to generate proactive suggestions
via Kora's Proactive Intelligence Engine without silently modifying goal states.
"""

from __future__ import annotations

from personal.manager import GoalManager
from proactive.detector import EventDetector
from proactive.types import EventSourceType, EventUrgency, ProactiveEvent


class PersonalProactiveDetector:
    """
    Scans goals and triggers proactive alerts for upcoming deadlines and stalled progress.
    """

    def __init__(
        self,
        goal_manager: GoalManager | None = None,
        detector: EventDetector | None = None,
    ) -> None:
        self.goal_manager = goal_manager or GoalManager()
        self.detector = detector or EventDetector()

    async def check_goals_and_deadlines(self, days_ahead: int = 3) -> list[ProactiveEvent]:
        """
        Scan goals and emit proactive events for deadlines or stalled items.
        """
        flagged = self.goal_manager.get_stalled_or_due_goals(days_ahead=days_ahead)
        emitted_events: list[ProactiveEvent] = []

        for goal, reason in flagged:
            is_deadline = "Approaching target date" in reason
            urgency = EventUrgency.HIGH if is_deadline else EventUrgency.NORMAL
            importance = 0.8 if is_deadline else 0.6

            event = ProactiveEvent(
                source_type=EventSourceType.TASK_LIFECYCLE,
                title=f"Goal Alert: {goal.title[:50]}",
                description=f"{reason}. Current progress: {int(goal.progress * 100)}%.",
                project_id=goal.project_id,
                urgency=urgency,
                importance=importance,
                data={
                    "event_subtype": "goal_deadline" if is_deadline else "goal_stalled",
                    "goal_id": str(goal.goal_id),
                    "goal_title": goal.title,
                    "progress": goal.progress,
                    "reason": reason,
                },
            )
            emitted = await self.detector.emit(event)
            emitted_events.append(emitted)

        return emitted_events
