"""
personal.types — Data Types and Schemas for Kora Personal Knowledge & Goals (V17).

Defines:
  - Goal states and priority enumerations
  - Goal and Milestone data models with fact-based mathematical progress
  - Decision Journal records capturing context, alternatives, and outcomes
  - Personal Context Packages with strict privacy boundaries
"""

from __future__ import annotations

import enum
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


class GoalState(str, enum.Enum):
    """Lifecycle states of a personal goal."""
    ACTIVE    = "active"
    PAUSED    = "paused"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    ARCHIVED  = "archived"


class GoalPriority(str, enum.Enum):
    """Priority level for goals and milestone scheduling."""
    LOW      = "low"
    NORMAL   = "normal"
    HIGH     = "high"
    CRITICAL = "critical"


@dataclass
class Milestone:
    """Individual milestone step contributing toward a goal."""
    title: str
    goal_id: uuid.UUID
    description: str = ""
    deadline: datetime | None = None
    completed: bool = False
    order_index: int = 0
    milestone_id: uuid.UUID = field(default_factory=uuid.uuid4)
    completed_at: datetime | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class Goal:
    """Structured personal or project goal."""
    title: str
    goal_id: uuid.UUID = field(default_factory=uuid.uuid4)
    description: str = ""
    state: GoalState = GoalState.ACTIVE
    priority: GoalPriority = GoalPriority.NORMAL
    project_id: uuid.UUID | None = None
    target_date: datetime | None = None
    progress: float = 0.0  # 0.0 to 1.0 (strictly calculated)
    milestones: list[Milestone] = field(default_factory=list)
    associated_task_ids: list[uuid.UUID] = field(default_factory=list)
    associated_decision_ids: list[uuid.UUID] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: datetime | None = None

    def __post_init__(self) -> None:
        if isinstance(self.state, str):
            self.state = GoalState(self.state)
        if isinstance(self.priority, str):
            self.priority = GoalPriority(self.priority)


@dataclass
class DecisionRecord:
    """Structured record in the Decision Journal."""
    decision_text: str
    context: str = ""
    alternatives_considered: list[str] = field(default_factory=list)
    reasoning: str = ""
    project_id: uuid.UUID | None = None
    goal_id: uuid.UUID | None = None
    outcome: str | None = None
    tags: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    decision_id: uuid.UUID = field(default_factory=uuid.uuid4)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class PersonalContextPackage:
    """Bounded, privacy-scoped personal context slice for agent planning."""
    goals: list[Goal] = field(default_factory=list)
    decisions: list[DecisionRecord] = field(default_factory=list)
    active_milestones: list[Milestone] = field(default_factory=list)
    summary_text: str = ""
    token_count: int = 0
