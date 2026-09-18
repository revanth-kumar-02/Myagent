"""
memory.conflict — Conflict resolution, contradiction detection, and superseding (RAG V5)

Handles:
  - Duplicate detection by content hash
  - Contradiction and update detection by semantic similarity and subject overlap
  - Superseding older memories deterministically
"""

from __future__ import annotations

import math
from typing import Sequence

import structlog

from memory.types import MemoryRecord, MemoryStatus, MemoryType

logger = structlog.get_logger(__name__)

# Cosine similarity threshold to consider two memories as referring to the same topic/rule
CONFLICT_SIMILARITY_THRESHOLD = 0.82


def cosine_similarity(v1: Sequence[float], v2: Sequence[float]) -> float:
    """Compute cosine similarity between two float vectors."""
    if not v1 or not v2 or len(v1) != len(v2):
        return 0.0
    dot = sum(a * b for a, b in zip(v1, v2))
    norm_a = math.sqrt(sum(a * a for a, b in zip(v1, v2)))
    norm_b = math.sqrt(sum(b * b for a, b in zip(v1, v2)))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)


class MemoryConflictResolver:
    """
    Evaluates new candidate memories against existing active memories.
    """

    def find_contradiction(
        self,
        candidate: MemoryRecord,
        existing_memories: list[MemoryRecord],
        threshold: float = CONFLICT_SIMILARITY_THRESHOLD,
    ) -> MemoryRecord | None:
        """
        Find an existing active memory of the same type and scope that contradicts or
        is being updated by the candidate memory.
        """
        if not candidate.embedding:
            return None

        for existing in existing_memories:
            if existing.status != MemoryStatus.ACTIVE:
                continue
            # Must match memory type and project scope
            if existing.type != candidate.type:
                continue
            if existing.project_id != candidate.project_id:
                continue
            # If same content hash, it's an exact duplicate, handled separately
            if existing.content_hash == candidate.content_hash:
                continue

            if existing.embedding:
                sim = cosine_similarity(candidate.embedding, existing.embedding)
                if sim >= threshold:
                    logger.info(
                        "memory_contradiction_detected",
                        candidate_id=str(candidate.memory_id),
                        existing_id=str(existing.memory_id),
                        similarity=round(sim, 3),
                        memory_type=candidate.type.value,
                    )
                    return existing

        return None

    def supersede(
        self,
        older: MemoryRecord,
        newer: MemoryRecord,
    ) -> tuple[MemoryRecord, MemoryRecord]:
        """
        Updates older memory to SUPERSEDED and links provenance IDs between them.
        """
        older.status = MemoryStatus.SUPERSEDED
        older.metadata["superseded_by"] = str(newer.memory_id)
        newer.metadata["supersedes_id"] = str(older.memory_id)

        logger.info(
            "memory_superseded",
            older_id=str(older.memory_id),
            newer_id=str(newer.memory_id),
        )
        return older, newer
