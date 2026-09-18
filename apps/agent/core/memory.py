"""
core.memory — Memory Manager

Three-tier memory system:
  ┌──────────────┬────────────────┬──────────────────────────────────────────┐
  │ Tier         │ Storage        │ Contents                                 │
  ├──────────────┼────────────────┼──────────────────────────────────────────┤
  │ Working      │ In-process     │ Current turn context (discarded on turn end)│
  │ Session      │ Redis          │ Full message history, tool log (TTL 24h) │
  │ Long-term    │ PostgreSQL     │ Summarised episodes, facts, preferences  │
  └──────────────┴────────────────┴──────────────────────────────────────────┘

Responsibilities:
  - retrieve(): semantic search against long-term memory
  - persist(): summarise and write a completed turn to PostgreSQL
  - get_session_history(): load from Redis
  - save_session_history(): write to Redis
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import TYPE_CHECKING

import structlog

if TYPE_CHECKING:
    import redis.asyncio as aioredis
    from sqlalchemy.ext.asyncio import AsyncSession

logger = structlog.get_logger(__name__)


@dataclass
class MemoryEntry:
    id: uuid.UUID
    type: str          # 'episode' | 'fact' | 'preference'
    content: str
    project_id: uuid.UUID | None
    score: float       # cosine similarity score from retrieval


class Memory:
    """
    Manages all three memory tiers for a session.
    """

    def __init__(
        self,
        session_id: uuid.UUID,
        project_id: uuid.UUID | None,
        db: "AsyncSession",
        redis: "aioredis.Redis",
        embedding_router: object,  # ModelRouter — avoids circular import
    ) -> None:
        self.session_id = session_id
        self.project_id = project_id
        self._db = db
        self._redis = redis
        self._embedding_router = embedding_router

    async def retrieve(self, query: str, top_k: int = 5) -> list[MemoryEntry]:
        """
        Semantic search against agent_memory scoped to this session's project.
        Falls back to global (project_id=NULL) memories if project is set.
        """
        raise NotImplementedError  # TODO: implement in feature phase

    async def persist(self, user_message: str, assistant_response: str) -> None:
        """
        Summarise the completed turn and write to agent_memory (long-term tier).
        Also updates the Redis session history (session tier).
        """
        raise NotImplementedError  # TODO: implement in feature phase

    async def get_session_history(self) -> list[dict[str, str]]:
        """Load message history from Redis. Returns [] if no history exists."""
        raise NotImplementedError  # TODO: implement in feature phase

    async def save_session_history(self, history: list[dict[str, str]]) -> None:
        """Write message history to Redis with TTL."""
        raise NotImplementedError  # TODO: implement in feature phase
