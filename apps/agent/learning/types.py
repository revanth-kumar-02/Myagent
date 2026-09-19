"""
learning.types — Data models and enumerations for Kora's Adaptive Learning & Reflection Subsystem (V12).

Defines:
  - Learning categories and user feedback types
  - Execution traces and step outcomes
  - Reflection analysis reports
  - Persistent learning records and evidence structures
"""

from __future__ import annotations

import enum
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


class LearningCategory(str, enum.Enum):
    """Classifies the domain and application of the learned insight."""
    SUCCESSFUL_WORKFLOW    = "successful_workflow"     # Effective sequence of steps for a goal
    FAILED_WORKFLOW        = "failed_workflow"         # Anti-pattern or failure mode to avoid
    TOOL_SELECTION_PATTERN = "tool_selection_pattern"  # Preferred tool under specific input criteria
    RECOVERY_STRATEGY      = "recovery_strategy"       # How to recover when a specific error occurs
    PLANNING_IMPROVEMENT   = "planning_improvement"    # Plan simplification or dependency optimization
    EXECUTION_CONSTRAINT   = "execution_constraint"    # Environmental or platform limitation


class LearningStatus(str, enum.Enum):
    """Lifecycle status of a learned pattern."""
    ACTIVE      = "active"       # Ready for retrieval and planner guidance
    REINFORCED  = "reinforced"   # Confirmed by repeated success or positive user feedback
    INVALIDATED = "invalidated"  # Rejected by user feedback or contradictory new evidence
    DEPRECATED  = "deprecated"   # Superseded by an updated learning


class FeedbackType(str, enum.Enum):
    """User feedback signals on agent learning and execution."""
    USEFUL             = "useful"              # Reinforces confidence
    NOT_USEFUL         = "not_useful"          # Decreases confidence or invalidates
    CORRECTION         = "correction"          # Modifies learning recommendation
    PREFERRED_APPROACH = "preferred_approach"  # Explicitly overrides with user pattern


@dataclass
class StepOutcome:
    """Record of an individual executed plan step."""
    step_index: int
    goal: str
    tool_name: str | None = None
    action_type: str = ""
    status: str = "done"               # 'done', 'failed', 'skipped'
    output: Any = None
    error: str | None = None
    duration_ms: int = 0
    verification_verdict: str = "pass" # 'pass', 'retry', 'escalate'
    retry_count: int = 0
    params: dict[str, Any] = field(default_factory=dict)


@dataclass
class ExecutionTrace:
    """Complete trace of a planned and executed task."""
    task_id: uuid.UUID = field(default_factory=uuid.uuid4)
    goal: str = ""
    planned_steps_count: int = 0
    actual_steps: list[StepOutcome] = field(default_factory=list)
    successful_actions: list[str] = field(default_factory=list)
    failed_actions: list[str] = field(default_factory=list)
    retries_used: int = 0
    total_duration_ms: int = 0
    final_outcome: str = "success"  # 'success', 'failed', 'partially_completed'
    error_summary: str | None = None
    project_id: uuid.UUID | None = None
    session_id: uuid.UUID | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class LearningRecord:
    """Validated, non-sensitive learning item for long-term retention."""
    learning_id: uuid.UUID = field(default_factory=uuid.uuid4)
    category: LearningCategory = LearningCategory.SUCCESSFUL_WORKFLOW
    title: str = ""
    description: str = ""
    condition: str = ""               # When this learning applies (trigger context)
    recommendation: str = ""          # What the agent/planner should do
    confidence: float = 1.0           # 0.0 to 1.0 certainty score
    importance: float = 0.5           # 0.0 to 1.0 prioritization score
    source_task_id: uuid.UUID | None = None
    project_id: uuid.UUID | None = None  # None = global agent learning
    evidence: dict[str, Any] = field(default_factory=dict)
    status: LearningStatus = LearningStatus.ACTIVE
    feedback_score: int = 0           # Net user feedback (+1 for useful, -1 for not useful)
    content_hash: str = ""
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self) -> None:
        if isinstance(self.category, str):
            self.category = LearningCategory(self.category)
        if isinstance(self.status, str):
            self.status = LearningStatus(self.status)


@dataclass
class ReflectionAnalysis:
    """Factual, evidence-based post-execution analysis."""
    task_id: uuid.UUID
    what_worked: list[str] = field(default_factory=list)
    what_failed: list[str] = field(default_factory=list)
    root_cause: str | None = None
    improvement_areas: list[str] = field(default_factory=list)
    is_plan_overly_complex: bool = False
    plan_complexity_notes: str = ""
    candidate_learnings: list[LearningRecord] = field(default_factory=list)


@dataclass
class UserFeedbackRecord:
    """Explicit user evaluation on a learning record."""
    feedback_id: uuid.UUID = field(default_factory=uuid.uuid4)
    learning_id: uuid.UUID = field(default_factory=uuid.uuid4)
    feedback_type: FeedbackType = FeedbackType.USEFUL
    comments: str = ""
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class ReflectionReport:
    """Comprehensive output of the Reflection Engine."""
    trace: ExecutionTrace
    analysis: ReflectionAnalysis
    stored_learnings: list[LearningRecord] = field(default_factory=list)
    rejected_learnings: list[tuple[LearningRecord, str]] = field(default_factory=list)
