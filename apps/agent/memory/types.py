"""
memory.types — Domain types and enumerations for Kora's Long-Term Memory Layer (RAG V5)
"""

from __future__ import annotations

import enum
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


class MemoryType(str, enum.Enum):
    """
    Classifies the nature and domain of the memory.
    """
    USER_PREFERENCE = "user_preference"              # Indentation, favorite tools, tone, style
    USER_PROFILE_CONTEXT = "user_profile_context"    # Role, background, hardware, timezone
    PROJECT_CONTEXT = "project_context"              # Project architectural decisions, custom conventions
    TASK_CONTEXT = "task_context"                    # Ongoing multi-step task state and milestones
    AGENT_LEARNING = "agent_learning"                # Learned bug fixes, operational lessons
    DECISION = "decision"                            # Key technical or design decisions agreed with user
    WORKFLOW_PATTERN = "workflow_pattern"            # Preferred git flow, testing flow, deploy patterns


class MemoryStatus(str, enum.Enum):
    """
    Lifecycle status of a memory record.
    """
    ACTIVE = "active"          # Ready for retrieval
    ARCHIVED = "archived"      # Manually archived or retired
    EXPIRED = "expired"        # Exceeded TTL / expiration date
    SUPERSEDED = "superseded"  # Replaced by newer contradictory memory


class MemorySource(str, enum.Enum):
    """
    Origin of the memory content.
    """
    USER_EXPLICIT = "user_explicit"  # User directly said "Remember that..."
    AGENT_TURN = "agent_turn"        # Extracted from completed interaction turn
    TOOL_OUTPUT = "tool_output"      # Learned from tool results or test outcomes
    INFERRED = "inferred"            # Inferred from repeated patterns
    SYSTEM = "system"                # Seeded system memory or administrative


@dataclass
class MemoryRecord:
    """
    Core long-term memory record stored in PostgreSQL + pgvector.
    """
    memory_id: uuid.UUID = field(default_factory=uuid.uuid4)
    type: MemoryType = MemoryType.USER_PREFERENCE
    content: str = ""
    source: MemorySource = MemorySource.USER_EXPLICIT
    confidence: float = 1.0          # 0.0 to 1.0 (how certain the system is)
    importance: float = 0.5          # 0.0 to 1.0 (priority for retention & retrieval)
    project_id: uuid.UUID | None = None  # None = Global user memory
    content_hash: str = ""           # SHA-256 of normalized content
    embedding: list[float] | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    last_accessed_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    expiration_at: datetime | None = None
    status: MemoryStatus = MemoryStatus.ACTIVE
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def is_active(self) -> bool:
        return self.status == MemoryStatus.ACTIVE


@dataclass
class MemoryRetrievalResult:
    """
    Retrieval result containing the MemoryRecord and multi-signal scoring breakdown.
    """
    record: MemoryRecord
    score: float                     # Combined final ranking score
    semantic_score: float = 0.0      # Cosine similarity (0.0 to 1.0)
    recency_score: float = 1.0       # Time decay factor (0.0 to 1.0)
    importance_boost: float = 0.0    # Boost derived from importance (0.0 to 1.0)

    @property
    def content(self) -> str:
        return self.record.content

    @property
    def type(self) -> str:
        return self.record.type.value

    @property
    def memory_id(self) -> uuid.UUID:
        return self.record.memory_id


@dataclass
class MemoryStats:
    """
    Statistical summary of stored memories.
    """
    total_memories: int = 0
    active_count: int = 0
    archived_count: int = 0
    expired_count: int = 0
    superseded_count: int = 0
    by_type: dict[str, int] = field(default_factory=dict)
    project_id: uuid.UUID | None = None
