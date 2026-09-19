"""
learning.manager — Central Adaptive Learning & Self-Reflection Manager (V12).

Orchestrates:
  - Post-execution reflection & insight extraction
  - Safety & secret validation
  - Persistence into Long-Term Memory (AGENT_LEARNING)
  - Semantic linkage in Knowledge Graph
  - Relevance retrieval for task planning
  - User feedback processing & confidence adjustments
"""

from __future__ import annotations

import uuid
from typing import Any, Sequence

import structlog

from graph.service import KnowledgeGraphService
from learning.analyzer import ExecutionAnalyzer
from learning.reflector import ReflectionEngine
from learning.types import (
    ExecutionTrace,
    FeedbackType,
    LearningCategory,
    LearningRecord,
    LearningStatus,
    ReflectionAnalysis,
    ReflectionReport,
    UserFeedbackRecord,
)
from learning.validator import LearningValidator
from memory.manager import MemoryManager
from memory.types import MemorySource, MemoryType

logger = structlog.get_logger(__name__)


class AdaptiveLearningManager:
    """
    Coordinates self-reflection, learning validation, persistent storage, and planner retrieval.
    """

    def __init__(
        self,
        memory_manager: MemoryManager | None = None,
        graph_service: KnowledgeGraphService | None = None,
        analyzer: ExecutionAnalyzer | None = None,
        reflector: ReflectionEngine | None = None,
        validator: LearningValidator | None = None,
    ) -> None:
        self.memory_manager = memory_manager
        self.graph_service = graph_service
        self.analyzer = analyzer or ExecutionAnalyzer()
        self.reflector = reflector or ReflectionEngine()
        self.validator = validator or LearningValidator()

        # In-memory store for fast retrieval and isolated testing
        self._learnings: dict[uuid.UUID, LearningRecord] = {}
        self._feedback_records: list[UserFeedbackRecord] = []

    # ── Task Reflection & Ingestion ──────────────────────────────────────────

    async def process_task_execution(self, trace: ExecutionTrace) -> ReflectionReport:
        """
        Reflect on task execution, validate extracted insights, and store verified learnings.
        """
        # 1. Run Reflection
        analysis = self.reflector.reflect(trace)

        stored: list[LearningRecord] = []
        rejected: list[tuple[LearningRecord, str]] = []
        existing_list = list(self._learnings.values())

        # 2. Validate & Store Candidates
        for candidate in analysis.candidate_learnings:
            is_valid, reason, sanitized = self.validator.validate_candidate(candidate, existing_list)
            if is_valid:
                self._learnings[sanitized.learning_id] = sanitized
                stored.append(sanitized)
                existing_list.append(sanitized)

                # Persist to Long-Term Memory (RAG V5)
                if self.memory_manager is not None:
                    try:
                        mem_content = f"[{sanitized.category.value.upper()}] {sanitized.condition} -> {sanitized.recommendation}"
                        await self.memory_manager.create_memory(
                            content=mem_content,
                            type=MemoryType.AGENT_LEARNING,
                            project_id=sanitized.project_id,
                            confidence=sanitized.confidence,
                            importance=sanitized.importance,
                            source=MemorySource.TOOL_OUTPUT,
                            metadata={
                                "learning_id": str(sanitized.learning_id),
                                "category": sanitized.category.value,
                                "condition": sanitized.condition,
                                "recommendation": sanitized.recommendation,
                            },
                        )
                    except Exception as exc:
                        logger.warning("learning_memory_persistence_failed", error=str(exc))

                # Link into Knowledge Graph (V11)
                if self.graph_service is not None:
                    try:
                        await self.graph_service.index_memory(
                            content=f"Learned pattern: {sanitized.title} | {sanitized.recommendation}",
                            memory_type=MemoryType.AGENT_LEARNING.value,
                            memory_id=sanitized.learning_id,
                            project_id=sanitized.project_id,
                            source="agent_learning",
                        )
                    except Exception as exc:
                        logger.warning("learning_graph_link_failed", error=str(exc))
            else:
                rejected.append((candidate, reason))

        report = ReflectionReport(
            trace=trace,
            analysis=analysis,
            stored_learnings=stored,
            rejected_learnings=rejected,
        )

        logger.info(
            "adaptive_learning_processed",
            task_id=str(trace.task_id),
            stored_count=len(stored),
            rejected_count=len(rejected),
        )
        return report

    # ── Retrieval for Task Planner ───────────────────────────────────────────

    async def get_relevant_learnings(
        self,
        query: str,
        project_id: uuid.UUID | None = None,
        category: LearningCategory | None = None,
        min_confidence: float = 0.5,
    ) -> list[LearningRecord]:
        """
        Find active, high-confidence learnings applicable to the incoming query or project.
        """
        relevant: list[LearningRecord] = []
        lower_query = query.lower()
        query_words = set(lower_query.split())

        for learning in self._learnings.values():
            if learning.status not in (LearningStatus.ACTIVE, LearningStatus.REINFORCED):
                continue
            if learning.confidence < min_confidence:
                continue
            # Project isolation: match project_id or global learnings
            if project_id is not None and learning.project_id is not None and learning.project_id != project_id:
                continue
            if category is not None and learning.category != category:
                continue

            # Check keyword match in condition or recommendation
            text_to_match = (learning.title + " " + learning.condition + " " + learning.recommendation).lower()
            if any(w in text_to_match for w in query_words if len(w) > 3) or not query_words:
                relevant.append(learning)

        # Sort by importance and confidence descending
        relevant.sort(key=lambda r: (r.importance, r.confidence), reverse=True)
        return relevant

    # ── Explicit User Feedback ───────────────────────────────────────────────

    def apply_user_feedback(
        self,
        learning_id: uuid.UUID,
        feedback_type: FeedbackType | str,
        comments: str = "",
    ) -> LearningRecord | None:
        """
        Incorporate user feedback to reinforce, adjust, or invalidate learning.
        """
        if isinstance(feedback_type, str):
            feedback_type = FeedbackType(feedback_type)

        learning = self._learnings.get(learning_id)
        if learning is None:
            return None

        fb_record = UserFeedbackRecord(
            learning_id=learning_id,
            feedback_type=feedback_type,
            comments=comments,
        )
        self._feedback_records.append(fb_record)

        if feedback_type == FeedbackType.USEFUL:
            learning.feedback_score += 1
            learning.confidence = min(learning.confidence + 0.1, 1.0)
            learning.status = LearningStatus.REINFORCED
        elif feedback_type == FeedbackType.NOT_USEFUL:
            learning.feedback_score -= 1
            learning.confidence = max(learning.confidence - 0.25, 0.0)
            if learning.confidence < 0.4:
                learning.status = LearningStatus.INVALIDATED
        elif feedback_type == FeedbackType.CORRECTION:
            if comments:
                learning.recommendation = comments
            learning.status = LearningStatus.REINFORCED
            learning.confidence = min(learning.confidence + 0.1, 1.0)
        elif feedback_type == FeedbackType.PREFERRED_APPROACH:
            if comments:
                learning.recommendation = comments
            learning.importance = 1.0
            learning.confidence = 1.0
            learning.status = LearningStatus.REINFORCED

        logger.info(
            "learning_feedback_applied",
            learning_id=str(learning_id),
            feedback=feedback_type.value,
            new_confidence=learning.confidence,
            status=learning.status.value,
        )
        return learning

    def get_learning(self, learning_id: uuid.UUID) -> LearningRecord | None:
        """Retrieve a learning record by ID."""
        return self._learnings.get(learning_id)

    def list_learnings(self, project_id: uuid.UUID | None = None) -> list[LearningRecord]:
        """List all learning records, optionally scoped by project."""
        if project_id is None:
            return list(self._learnings.values())
        return [r for r in self._learnings.values() if r.project_id is None or r.project_id == project_id]
