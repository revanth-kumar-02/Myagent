"""
personal.manager — Goal & Milestone Manager (V17)

Coordinates personal and project goals:
  - Full goal lifecycle (create, update, pause, resume, complete, cancel, archive, delete)
  - Milestone tracking and task-to-goal linking
  - Strict mathematical progress calculation: (completed milestones + completed tasks) / total
  - Deadline and stalled goal monitoring
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

import structlog

from personal.types import Goal, GoalPriority, GoalState, Milestone

logger = structlog.get_logger(__name__)


class GoalNotFoundError(Exception):
    """Raised when a goal ID cannot be found."""


class GoalActionError(Exception):
    """Raised when an invalid action is attempted on a goal."""


class GoalManager:
    """
    Manages goal records, milestones, progress calculation, and status transitions.
    """

    def __init__(self) -> None:
        self._goals: dict[uuid.UUID, Goal] = {}

    def create_goal(
        self,
        title: str,
        description: str = "",
        priority: GoalPriority = GoalPriority.NORMAL,
        project_id: uuid.UUID | None = None,
        target_date: datetime | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> Goal:
        """Create and store a new goal."""
        if not title or not title.strip():
            raise GoalActionError("Goal title cannot be empty")

        goal = Goal(
            title=title.strip(),
            description=description.strip(),
            priority=priority,
            project_id=project_id,
            target_date=target_date,
            metadata=metadata or {},
        )
        self._goals[goal.goal_id] = goal
        logger.info("goal_created", goal_id=str(goal.goal_id), title=goal.title, priority=goal.priority.value)
        return goal

    def get_goal(self, goal_id: uuid.UUID | str) -> Goal | None:
        """Retrieve goal by ID."""
        key = uuid.UUID(str(goal_id))
        return self._goals.get(key)

    def list_goals(
        self,
        project_id: uuid.UUID | None = None,
        state: GoalState | None = None,
        priority: GoalPriority | None = None,
    ) -> list[Goal]:
        """List stored goals with optional filtering."""
        results: list[Goal] = []
        for g in self._goals.values():
            if project_id is not None and g.project_id != project_id:
                continue
            if state is not None and g.state != state:
                continue
            if priority is not None and g.priority != priority:
                continue
            results.append(g)
        return sorted(results, key=lambda x: x.created_at, reverse=True)

    def update_goal(
        self,
        goal_id: uuid.UUID | str,
        title: str | None = None,
        description: str | None = None,
        priority: GoalPriority | None = None,
        target_date: datetime | None = None,
    ) -> Goal:
        """Update goal fields."""
        goal = self.get_goal(goal_id)
        if not goal:
            raise GoalNotFoundError(f"Goal {goal_id} not found")

        if title is not None:
            goal.title = title.strip()
        if description is not None:
            goal.description = description.strip()
        if priority is not None:
            goal.priority = priority
        if target_date is not None:
            goal.target_date = target_date

        goal.updated_at = datetime.now(timezone.utc)
        return goal

    def add_milestone(
        self,
        goal_id: uuid.UUID | str,
        title: str,
        description: str = "",
        deadline: datetime | None = None,
        order_index: int = 0,
    ) -> Milestone:
        """Add a milestone to a goal."""
        goal = self.get_goal(goal_id)
        if not goal:
            raise GoalNotFoundError(f"Goal {goal_id} not found")

        milestone = Milestone(
            goal_id=goal.goal_id,
            title=title.strip(),
            description=description.strip(),
            deadline=deadline,
            order_index=order_index,
        )
        goal.milestones.append(milestone)
        goal.updated_at = datetime.now(timezone.utc)
        self.calculate_progress(goal.goal_id)
        return milestone

    def complete_milestone(
        self,
        goal_id: uuid.UUID | str,
        milestone_id: uuid.UUID | str,
    ) -> Goal:
        """Mark a milestone as completed and recalculate goal progress."""
        goal = self.get_goal(goal_id)
        if not goal:
            raise GoalNotFoundError(f"Goal {goal_id} not found")

        ms_key = uuid.UUID(str(milestone_id))
        found = False
        for ms in goal.milestones:
            if ms.milestone_id == ms_key:
                ms.completed = True
                ms.completed_at = datetime.now(timezone.utc)
                found = True
                break

        if not found:
            raise GoalActionError(f"Milestone {milestone_id} not found on goal {goal_id}")

        self.calculate_progress(goal.goal_id)
        goal.updated_at = datetime.now(timezone.utc)
        return goal

    def calculate_progress(
        self,
        goal_id: uuid.UUID | str,
        completed_task_ids: set[uuid.UUID] | None = None,
    ) -> float:
        """
        Strictly calculate progress from actual completed milestones and tasks:
          progress = (completed_milestones + completed_tasks) / total_items
        """
        goal = self.get_goal(goal_id)
        if not goal:
            raise GoalNotFoundError(f"Goal {goal_id} not found")

        if goal.state == GoalState.COMPLETED:
            goal.progress = 1.0
            return 1.0

        total_milestones = len(goal.milestones)
        completed_milestones = sum(1 for m in goal.milestones if m.completed)

        total_tasks = len(goal.associated_task_ids)
        c_tasks = completed_task_ids or set()
        completed_tasks = sum(1 for t in goal.associated_task_ids if t in c_tasks)

        total_items = total_milestones + total_tasks
        if total_items == 0:
            goal.progress = 0.0
            return 0.0

        computed = round((completed_milestones + completed_tasks) / total_items, 2)
        goal.progress = max(0.0, min(1.0, computed))

        # Auto-complete if all items done
        if goal.progress >= 1.0 and goal.state == GoalState.ACTIVE:
            goal.state = GoalState.COMPLETED
            goal.completed_at = datetime.now(timezone.utc)

        return goal.progress

    def link_task(self, goal_id: uuid.UUID | str, task_id: uuid.UUID | str) -> Goal:
        """Link an autonomous task to a goal."""
        goal = self.get_goal(goal_id)
        if not goal:
            raise GoalNotFoundError(f"Goal {goal_id} not found")

        t_key = uuid.UUID(str(task_id))
        if t_key not in goal.associated_task_ids:
            goal.associated_task_ids.append(t_key)
            goal.updated_at = datetime.now(timezone.utc)
            self.calculate_progress(goal.goal_id)
        return goal

    def link_decision(self, goal_id: uuid.UUID | str, decision_id: uuid.UUID | str) -> Goal:
        """Link a decision journal record to a goal."""
        goal = self.get_goal(goal_id)
        if not goal:
            raise GoalNotFoundError(f"Goal {goal_id} not found")

        d_key = uuid.UUID(str(decision_id))
        if d_key not in goal.associated_decision_ids:
            goal.associated_decision_ids.append(d_key)
            goal.updated_at = datetime.now(timezone.utc)
        return goal

    # ── State Transitions ──────────────────────────────────────────────────────

    def pause_goal(self, goal_id: uuid.UUID | str) -> Goal:
        """Pause an active goal."""
        goal = self.get_goal(goal_id)
        if not goal:
            raise GoalNotFoundError(f"Goal {goal_id} not found")
        goal.state = GoalState.PAUSED
        goal.updated_at = datetime.now(timezone.utc)
        return goal

    def resume_goal(self, goal_id: uuid.UUID | str) -> Goal:
        """Resume a paused goal."""
        goal = self.get_goal(goal_id)
        if not goal:
            raise GoalNotFoundError(f"Goal {goal_id} not found")
        goal.state = GoalState.ACTIVE
        goal.updated_at = datetime.now(timezone.utc)
        return goal

    def complete_goal(self, goal_id: uuid.UUID | str) -> Goal:
        """Explicitly mark a goal as completed."""
        goal = self.get_goal(goal_id)
        if not goal:
            raise GoalNotFoundError(f"Goal {goal_id} not found")
        goal.state = GoalState.COMPLETED
        goal.progress = 1.0
        goal.completed_at = datetime.now(timezone.utc)
        goal.updated_at = datetime.now(timezone.utc)
        return goal

    def cancel_goal(self, goal_id: uuid.UUID | str, reason: str = "") -> Goal:
        """Cancel a goal."""
        goal = self.get_goal(goal_id)
        if not goal:
            raise GoalNotFoundError(f"Goal {goal_id} not found")
        goal.state = GoalState.CANCELLED
        if reason:
            goal.metadata["cancellation_reason"] = reason
        goal.updated_at = datetime.now(timezone.utc)
        return goal

    def archive_goal(self, goal_id: uuid.UUID | str) -> Goal:
        """Archive a goal."""
        goal = self.get_goal(goal_id)
        if not goal:
            raise GoalNotFoundError(f"Goal {goal_id} not found")
        goal.state = GoalState.ARCHIVED
        goal.updated_at = datetime.now(timezone.utc)
        return goal

    def delete_goal(self, goal_id: uuid.UUID | str, confirm: bool = False) -> bool:
        """Delete a goal. Requires explicit confirmation."""
        if not confirm:
            raise GoalActionError("Goal deletion requires explicit confirm=True")

        key = uuid.UUID(str(goal_id))
        if key in self._goals:
            del self._goals[key]
            logger.info("goal_deleted", goal_id=str(key))
            return True
        return False

    def get_stalled_or_due_goals(self, days_ahead: int = 3) -> list[tuple[Goal, str]]:
        """
        Identify goals with approaching deadlines (within days_ahead) or stalled active goals.
        """
        now = datetime.now(timezone.utc)
        target_cutoff = now + timedelta(days=days_ahead)
        stalled_threshold = now - timedelta(days=7)

        flagged: list[tuple[Goal, str]] = []
        for goal in self._goals.values():
            if goal.state != GoalState.ACTIVE:
                continue

            # Check approaching deadline
            if goal.target_date and goal.target_date <= target_cutoff:
                flagged.append((goal, f"Approaching target date on {goal.target_date.strftime('%Y-%m-%d')}"))
            elif goal.updated_at <= stalled_threshold and goal.progress < 0.5:
                flagged.append((goal, "Stalled goal: No progress updates for over 7 days"))

        return flagged
