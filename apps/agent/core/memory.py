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

from memory.extractor import MemoryCandidateDetector
from memory.manager import MemoryManager
from memory.types import MemoryRecord, MemoryRetrievalResult, MemorySource, MemoryType

if TYPE_CHECKING:
    import redis.asyncio as aioredis
    from sqlalchemy.ext.asyncio import AsyncSession
    from graph.service import KnowledgeGraphService

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
        graph_service: KnowledgeGraphService | None = None,
    ) -> None:
        self.session_id = session_id
        self.project_id = project_id
        self._db = db
        self._redis = redis
        self._embedding_router = embedding_router
        self._manager = memory_manager or MemoryManager(db_session=db)
        self._graph_service = graph_service
        self._detector = MemoryCandidateDetector()

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
        assistant_response: str = "",
        memory_type: MemoryType | None = None,
        source: MemorySource | None = None,
    ) -> MemoryRecord | None:
        """
        Extract meaningful long-term memory candidates and persist them.
        Transient chat / noise is rejected and not stored.
        """
        candidate = self._detector.detect(
            user_message=user_message,
            assistant_response=assistant_response,
            project_id=self.project_id,
        )

        if candidate is None:
            logger.debug("memory_persist_skipped_no_durable_candidate", user_message=user_message[:60])
            return None

        # Resolve type and source overrides if explicitly passed
        target_type = memory_type or candidate.type
        target_source = source or candidate.source

        try:
            record = await self._manager.create_memory(
                content=candidate.content,
                type=target_type,
                project_id=self.project_id,
                confidence=candidate.confidence,
                importance=candidate.importance,
                source=target_source,
                metadata={
                    "session_id": str(self.session_id),
                    **candidate.metadata,
                },
            )

            # Link into Knowledge Graph
            if self._graph_service is not None:
                try:
                    await self._graph_service.index_memory(
                        content=candidate.content,
                        memory_type=target_type.value,
                        memory_id=record.memory_id,
                        project_id=self.project_id,
                        source=target_source.value,
                    )
                except Exception as g_err:
                    logger.warning("memory_graph_index_failed", error=str(g_err))

            logger.info(
                "automatic_memory_persisted",
                memory_id=str(record.memory_id),
                type=target_type.value,
                content=candidate.content[:80],
            )
            return record
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
                parsed = json.loads(raw)
                if isinstance(parsed, list):
                    return parsed  # type: ignore[no-any-return]
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
