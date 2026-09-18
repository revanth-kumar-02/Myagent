"""
core.memory — Session & Long-Term Memory Manager (RAG V5)

Three-tier memory architecture:
  ┌──────────────┬────────────────┬──────────────────────────────────────────┐
  │ Tier         │ Storage        │ Contents                                 │
  ├──────────────┼────────────────┼──────────────────────────────────────────┤
  │ Working      │ In-process     │ Current turn context (discarded on end)  │
  │ Session      │ Redis          │ Message history, tool logs (TTL 24h)     │
  │ Long-term    │ PostgreSQL     │ Preferences, profile, learnings, patterns│
  └──────────────┴────────────────┴──────────────────────────────────────────┘
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import structlog

from memory.manager import MemoryManager
from memory.types import MemoryRecord, MemoryRetrievalResult, MemorySource, MemoryType

if TYPE_CHECKING:
    import redis.asyncio as aioredis
    from sqlalchemy.ext.asyncio import AsyncSession

logger = structlog.get_logger(__name__)

SESSION_HISTORY_TTL_SECONDS = 86400  # 24 hours


@dataclass
class MemoryEntry:
    id: uuid.UUID
    type: str  # 'user_preference' | 'project_context' | 'agent_learning' | etc.
    content: str
    project_id: uuid.UUID | None
    score: float  # Multi-signal retrieval score


class Memory:
    """
    Manages session and long-term memory tiers for an active agent session.
    """

    def __init__(
        self,
        session_id: uuid.UUID,
        project_id: uuid.UUID | None,
        db: "AsyncSession" | None,
        redis: "aioredis.Redis" | None = None,
        embedding_router: object | None = None,
        memory_manager: MemoryManager | None = None,
    ) -> None:
        self.session_id = session_id
        self.project_id = project_id
        self._db = db
        self._redis = redis
        self._embedding_router = embedding_router
        self._manager = memory_manager or MemoryManager(db_session=db)

    @property
    def manager(self) -> MemoryManager:
        return self._manager

    async def retrieve(
        self,
        query: str,
        top_k: int = 5,
        memory_types: list[MemoryType | str] | None = None,
    ) -> list[MemoryEntry]:
        """
        Semantic and multi-signal search against long-term memory scoped to project/global.
        """
        results = await self._manager.retrieve_memories(
            query=query,
            project_id=self.project_id,
            memory_types=memory_types,
            top_k=top_k,
        )
        return [
            MemoryEntry(
                id=res.record.memory_id,
                type=res.record.type.value,
                content=res.record.content,
                project_id=res.record.project_id,
                score=res.score,
            )
            for res in results
        ]

    async def persist(
        self,
        user_message: str,
        assistant_response: str,
        memory_type: MemoryType = MemoryType.TASK_CONTEXT,
        source: MemorySource = MemorySource.AGENT_TURN,
    ) -> MemoryRecord | None:
        """
        Persist a validated summary or key decision to long-term memory.
        """
        summary_content = f"Turn: User asked '{user_message[:100]}', Assistant: '{assistant_response[:100]}'"
        try:
            return await self._manager.create_memory(
                content=summary_content,
                type=memory_type,
                project_id=self.project_id,
                source=source,
                metadata={"session_id": str(self.session_id)},
            )
        except Exception as e:
            logger.warning("persist_long_term_memory_failed", error=str(e))
            return None

    async def get_session_history(self) -> list[dict[str, str]]:
        """Load message history from Redis. Returns [] if not available or no history."""
        if not self._redis:
            return []
        key = f"session:{self.session_id}:history"
        try:
            raw = await self._redis.get(key)
            if raw:
                return json.loads(raw)
        except Exception as e:
            logger.warning("get_session_history_failed", error=str(e))
        return []

    async def save_session_history(self, history: list[dict[str, str]]) -> None:
        """Write message history to Redis with 24h TTL."""
        if not self._redis:
            return
        key = f"session:{self.session_id}:history"
        try:
            await self._redis.setex(
                name=key,
                time=SESSION_HISTORY_TTL_SECONDS,
                value=json.dumps(history),
            )
        except Exception as e:
            logger.warning("save_session_history_failed", error=str(e))
