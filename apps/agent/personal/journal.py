"""
personal.journal — Decision Journal (V17)

Captures and retrieves structured decision records:
  - Decision statement and context
  - Alternatives considered
  - Trade-off reasoning and evidence
  - Associated project and goal references
  - Known outcomes and retrospective reflections
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

import structlog

from personal.types import DecisionRecord

logger = structlog.get_logger(__name__)


class DecisionNotFoundError(Exception):
    """Raised when a decision record cannot be found."""


class DecisionJournal:
    """
    Stores and manages historical decision logs with explicit reasoning and trade-offs.
    """

    def __init__(self) -> None:
        self._decisions: dict[uuid.UUID, DecisionRecord] = {}

    def record_decision(
        self,
        decision_text: str,
        context: str = "",
        alternatives_considered: list[str] | None = None,
        reasoning: str = "",
        project_id: uuid.UUID | None = None,
        goal_id: uuid.UUID | None = None,
        outcome: str | None = None,
        tags: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> DecisionRecord:
        """Record an explicit user decision."""
        if not decision_text or not decision_text.strip():
            raise ValueError("Decision text cannot be empty")

        rec = DecisionRecord(
            decision_text=decision_text.strip(),
            context=context.strip(),
            alternatives_considered=alternatives_considered or [],
            reasoning=reasoning.strip(),
            project_id=project_id,
            goal_id=goal_id,
            outcome=outcome,
            tags=tags or [],
            metadata=metadata or {},
        )

        self._decisions[rec.decision_id] = rec
        logger.info("decision_recorded", decision_id=str(rec.decision_id), text=rec.decision_text[:60])
        return rec

    def get_decision(self, decision_id: uuid.UUID | str) -> DecisionRecord | None:
        """Retrieve a decision record by ID."""
        key = uuid.UUID(str(decision_id))
        return self._decisions.get(key)

    def list_decisions(
        self,
        project_id: uuid.UUID | None = None,
        goal_id: uuid.UUID | None = None,
        tag: str | None = None,
        limit: int = 50,
    ) -> list[DecisionRecord]:
        """Query stored decisions with optional filters."""
        results: list[DecisionRecord] = []
        for d in self._decisions.values():
            if project_id is not None and d.project_id != project_id:
                continue
            if goal_id is not None and d.goal_id != goal_id:
                continue
            if tag is not None and tag not in d.tags:
                continue
            results.append(d)

        sorted_res = sorted(results, key=lambda x: x.created_at, reverse=True)
        return sorted_res[:limit]

    def update_outcome(
        self,
        decision_id: uuid.UUID | str,
        outcome: str,
    ) -> DecisionRecord:
        """Update the known outcome of a prior decision."""
        rec = self.get_decision(decision_id)
        if not rec:
            raise DecisionNotFoundError(f"Decision {decision_id} not found")

        rec.outcome = outcome.strip()
        rec.updated_at = datetime.now(timezone.utc)
        logger.info("decision_outcome_updated", decision_id=str(rec.decision_id))
        return rec
