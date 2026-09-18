"""
memory.decay — Recency scoring, time-decay, and expiration lifecycle (RAG V5)

Calculates:
  - Exponential time decay score based on elapsed time since last access/update
  - Expiration checks against memory TTL / expiration_at
  - Multi-signal memory score fusion
"""

from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Any

from memory.types import MemoryRecord, MemoryStatus

# Default decay half-life in days (e.g. score factor drops to 0.5 after 30 days without access)
DEFAULT_HALF_LIFE_DAYS = 30.0


def calculate_recency_score(
    last_accessed: datetime,
    current_time: datetime | None = None,
    half_life_days: float = DEFAULT_HALF_LIFE_DAYS,
) -> float:
    """
    Computes exponential time-decay factor in range (0.0, 1.0].
    decay = exp(-ln(2) * delta_days / half_life_days)
    """
    now = current_time or datetime.now(timezone.utc)
    if last_accessed.tzinfo is None:
        last_accessed = last_accessed.replace(tzinfo=timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)

    delta = (now - last_accessed).total_seconds()
    if delta <= 0:
        return 1.0

    delta_days = delta / 86400.0
    decay = math.exp(-math.log(2.0) * delta_days / half_life_days)
    return max(0.01, min(1.0, decay))


def is_memory_expired(record: MemoryRecord, current_time: datetime | None = None) -> bool:
    """Check if memory has an expiration timestamp that has passed."""
    if record.expiration_at is None:
        return False
    now = current_time or datetime.now(timezone.utc)
    exp = record.expiration_at
    if exp.tzinfo is None:
        exp = exp.replace(tzinfo=timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    return exp <= now


def compute_memory_score(
    semantic_score: float,
    importance: float,
    confidence: float,
    recency_score: float,
) -> float:
    """
    Combines retrieval signals deterministically:
      - Semantic relevance: 50%
      - Importance weight:  20%
      - Confidence weight:  15%
      - Recency weight:     15%
    """
    score = (
        (0.50 * max(0.0, min(1.0, semantic_score)))
        + (0.20 * max(0.0, min(1.0, importance)))
        + (0.15 * max(0.0, min(1.0, confidence)))
        + (0.15 * max(0.0, min(1.0, recency_score)))
    )
    return round(score, 4)
