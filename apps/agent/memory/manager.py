"""
memory.manager — Central Memory Subsystem Manager (RAG V5)

Orchestrates the entire Memory lifecycle:
  - Validation, sanitization, hashing, secret protection
  - Embedding via Central EmbeddingService (1024-dim)
  - Duplicate detection and conflict resolution / superseding
  - Multi-signal hybrid retrieval (semantic + importance + confidence + recency)
  - Expiration, archival, deletion, and statistical reporting
  - Project isolation and global fallback
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Sequence

import structlog
from sqlalchemy import select, update, delete, func, text
from sqlalchemy.ext.asyncio import AsyncSession

from memory.conflict import MemoryConflictResolver, cosine_similarity
from memory.decay import calculate_recency_score, compute_memory_score, is_memory_expired
from memory.types import (
    MemoryRecord,
    MemoryRetrievalResult,
    MemorySource,
    MemoryStats,
    MemoryStatus,
    MemoryType,
)
from memory.validator import MemoryValidationError, compute_content_hash, validate_candidate_memory
from rag.embedder import BaseEmbedder, EmbeddingService

logger = structlog.get_logger(__name__)


class MemoryManager:
    """
    Manages long-term memories in PostgreSQL + pgvector.
    Supports in-memory caching and fallback for standalone testing.
    """

    def __init__(
        self,
        db_session: AsyncSession | None = None,
        embedder: BaseEmbedder | None = None,
    ) -> None:
        self._db = db_session
        self._embedder = embedder or EmbeddingService()
        self._conflict_resolver = MemoryConflictResolver()
        # In-memory storage dictionary when running without DB session or as primary cache
        self._memory_store: dict[uuid.UUID, MemoryRecord] = {}

    async def create_memory(
        self,
        content: str,
        type: MemoryType | str,
        project_id: uuid.UUID | None = None,
        confidence: float = 1.0,
        importance: float = 0.5,
        source: MemorySource | str = MemorySource.USER_EXPLICIT,
        expiration_at: datetime | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> MemoryRecord:
        """
        Validate, embed, resolve conflicts, and persist a new long-term memory.
        """
        # 1. Type normalization
        if isinstance(type, str):
            type = MemoryType(type)
        if isinstance(source, str):
            source = MemorySource(source)

        # 2. Validation & secret protection
        clean_content, val_confidence, val_importance, content_hash = validate_candidate_memory(
            content=content,
            memory_type=type,
            confidence=confidence,
            importance=importance,
            source=source,
        )

        # 3. Duplicate check (same hash and project scope)
        existing_memories = await self._get_active_records(project_id)
        for existing in existing_memories:
            if existing.content_hash == content_hash and existing.type == type:
                logger.info(
                    "duplicate_memory_detected_returning_existing",
                    memory_id=str(existing.memory_id),
                    type=type.value,
                )
                return existing

        # 4. Generate Embedding
        embedding: list[float] | None = None
        try:
            embedding = await self._embedder.embed_query(clean_content)
        except Exception as e:
            logger.warning("memory_embedding_generation_failed", error=str(e))

        now = datetime.now(timezone.utc)
        record = MemoryRecord(
            memory_id=uuid.uuid4(),
            type=type,
            content=clean_content,
            source=source,
            confidence=val_confidence,
            importance=val_importance,
            project_id=project_id,
            content_hash=content_hash,
            embedding=embedding,
            created_at=now,
            updated_at=now,
            last_accessed_at=now,
            expiration_at=expiration_at,
            status=MemoryStatus.ACTIVE,
            metadata=metadata or {},
        )

        # 5. Conflict Resolution & Superseding
        if embedding:
            contradiction = self._conflict_resolver.find_contradiction(record, existing_memories)
            if contradiction:
                self._conflict_resolver.supersede(contradiction, record)
                # Persist superseded status of older memory
                await self._persist_record(contradiction)

        # 6. Persist candidate record
        await self._persist_record(record)
        logger.info(
            "memory_created",
            memory_id=str(record.memory_id),
            type=type.value,
            project_id=str(project_id) if project_id else "global",
            importance=val_importance,
        )
        return record

    async def retrieve_memories(
        self,
        query: str,
        project_id: uuid.UUID | None = None,
        memory_types: list[MemoryType | str] | None = None,
        top_k: int = 5,
        min_confidence: float = 0.0,
        include_global: bool = True,
        min_score: float = 0.25,
    ) -> list[MemoryRetrievalResult]:
        """
        Multi-signal retrieval combining semantic similarity, importance, confidence,
        and recency time-decay.
        """
        clean_query = query.strip()
        if not clean_query:
            return []

        # 1. Embed query
        query_embedding: list[float] | None = None
        try:
            query_embedding = await self._embedder.embed_query(clean_query)
        except Exception as e:
            logger.warning("query_embedding_failed", error=str(e))

        # 2. Filter candidates
        active_records = await self._get_active_records(project_id, include_global=include_global)
        if not active_records:
            return []

        # Normalize filter types
        filter_type_values = (
            {mt.value if isinstance(mt, MemoryType) else mt for mt in memory_types}
            if memory_types
            else None
        )

        now = datetime.now(timezone.utc)
        results: list[MemoryRetrievalResult] = []

        for rec in active_records:
            # Check expiration
            if is_memory_expired(rec, now):
                rec.status = MemoryStatus.EXPIRED
                await self._persist_record(rec)
                continue

            # Check memory types filter
            if filter_type_values and rec.type.value not in filter_type_values:
                continue

            # Check confidence
            if rec.confidence < min_confidence:
                continue

            # Calculate semantic similarity
            semantic_score = 0.0
            if query_embedding and rec.embedding:
                semantic_score = cosine_similarity(query_embedding, rec.embedding)
            else:
                # Text fallback match
                overlap = len(set(clean_query.lower().split()) & set(rec.content.lower().split()))
                semantic_score = min(1.0, overlap / max(1, len(clean_query.split())))

            # Calculate recency decay
            recency_score = calculate_recency_score(rec.last_accessed_at, now)

            # Combined multi-signal score
            combined_score = compute_memory_score(
                semantic_score=semantic_score,
                importance=rec.importance,
                confidence=rec.confidence,
                recency_score=recency_score,
            )

            if combined_score >= min_score:
                results.append(
                    MemoryRetrievalResult(
                        record=rec,
                        score=combined_score,
                        semantic_score=semantic_score,
                        recency_score=recency_score,
                        importance_boost=rec.importance,
                    )
                )

        # Sort descending by score
        results.sort(key=lambda r: r.score, reverse=True)
        top_results = results[:top_k]

        # Update last_accessed_at for retrieved items
        for res in top_results:
            res.record.last_accessed_at = now
            await self._persist_record(res.record)

        return top_results

    async def search_memories(
        self,
        query: str,
        project_id: uuid.UUID | None = None,
        top_k: int = 5,
    ) -> list[MemoryRecord]:
        """Fast semantic vector search returning MemoryRecords."""
        retrieved = await self.retrieve_memories(query, project_id=project_id, top_k=top_k)
        return [r.record for r in retrieved]

    async def update_memory(
        self,
        memory_id: uuid.UUID,
        content: str | None = None,
        importance: float | None = None,
        confidence: float | None = None,
        status: MemoryStatus | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> MemoryRecord | None:
        """Update an existing memory's fields."""
        record = await self.get_memory(memory_id)
        if not record:
            return None

        now = datetime.now(timezone.utc)
        if content is not None:
            clean_content, _, _, content_hash = validate_candidate_memory(
                content=content,
                memory_type=record.type,
                confidence=confidence if confidence is not None else record.confidence,
                importance=importance if importance is not None else record.importance,
                source=record.source,
            )
            record.content = clean_content
            record.content_hash = content_hash
            try:
                record.embedding = await self._embedder.embed_query(clean_content)
            except Exception as e:
                logger.warning("reembed_on_update_failed", error=str(e))

        if importance is not None:
            record.importance = max(0.0, min(1.0, float(importance)))
        if confidence is not None:
            record.confidence = max(0.0, min(1.0, float(confidence)))
        if status is not None:
            record.status = status
        if metadata is not None:
            record.metadata.update(metadata)

        record.updated_at = now
        await self._persist_record(record)
        return record

    async def archive_memory(self, memory_id: uuid.UUID) -> bool:
        """Transition memory to ARCHIVED."""
        record = await self.get_memory(memory_id)
        if not record:
            return False
        record.status = MemoryStatus.ARCHIVED
        record.updated_at = datetime.now(timezone.utc)
        await self._persist_record(record)
        return True

    async def delete_memory(self, memory_id: uuid.UUID) -> bool:
        """Delete memory permanently."""
        if memory_id in self._memory_store:
            del self._memory_store[memory_id]
        if self._db is not None:
            try:
                from db.schema import AgentMemory
                stmt = delete(AgentMemory).where(AgentMemory.id == memory_id)
                await self._db.execute(stmt)
                await self._db.commit()
            except Exception as e:
                logger.warning("db_delete_memory_failed", error=str(e))
        return True

    async def get_memory(self, memory_id: uuid.UUID) -> MemoryRecord | None:
        """Retrieve a single memory by ID."""
        if memory_id in self._memory_store:
            return self._memory_store[memory_id]

        if self._db is not None:
            try:
                from db.schema import AgentMemory
                stmt = select(AgentMemory).where(AgentMemory.id == memory_id)
                res = await self._db.execute(stmt)
                db_item = res.scalar_one_or_none()
                if db_item:
                    record = self._from_db_model(db_item)
                    self._memory_store[record.memory_id] = record
                    return record
            except Exception as e:
                logger.warning("db_get_memory_failed", error=str(e))

        return None

    async def get_memory_status(self, project_id: uuid.UUID | None = None) -> MemoryStats:
        """Calculate statistical breakdown of memory store."""
        records = list(self._memory_store.values())

        if project_id is not None:
            records = [r for r in records if r.project_id == project_id or r.project_id is None]

        total = len(records)
        active = sum(1 for r in records if r.status == MemoryStatus.ACTIVE)
        archived = sum(1 for r in records if r.status == MemoryStatus.ARCHIVED)
        expired = sum(1 for r in records if r.status == MemoryStatus.EXPIRED)
        superseded = sum(1 for r in records if r.status == MemoryStatus.SUPERSEDED)

        by_type: dict[str, int] = {}
        for r in records:
            t = r.type.value
            by_type[t] = by_type.get(t, 0) + 1

        return MemoryStats(
            total_memories=total,
            active_count=active,
            archived_count=archived,
            expired_count=expired,
            superseded_count=superseded,
            by_type=by_type,
            project_id=project_id,
        )

    # ── Internal Storage Helpers ───────────────────────────────────────────────

    async def _persist_record(self, record: MemoryRecord) -> None:
        """Persist memory in both memory store and database if session is present."""
        self._memory_store[record.memory_id] = record

        if self._db is not None:
            try:
                from db.schema import AgentMemory
                # Query if exists
                stmt = select(AgentMemory).where(AgentMemory.id == record.memory_id)
                res = await self._db.execute(stmt)
                db_item = res.scalar_one_or_none()

                if db_item:
                    db_item.content = record.content
                    db_item.type = record.type.value
                    db_item.source = record.source.value
                    db_item.confidence = record.confidence
                    db_item.importance = record.importance
                    db_item.content_hash = record.content_hash
                    db_item.status = record.status.value
                    db_item.embedding = record.embedding
                    db_item.updated_at = record.updated_at
                    db_item.last_accessed_at = record.last_accessed_at
                    db_item.expiration_at = record.expiration_at
                    db_item.metadata_ = record.metadata
                else:
                    new_item = AgentMemory(
                        id=record.memory_id,
                        project_id=record.project_id,
                        type=record.type.value,
                        content=record.content,
                        source=record.source.value,
                        confidence=record.confidence,
                        importance=record.importance,
                        content_hash=record.content_hash,
                        status=record.status.value,
                        embedding=record.embedding,
                        created_at=record.created_at,
                        updated_at=record.updated_at,
                        last_accessed_at=record.last_accessed_at,
                        expiration_at=record.expiration_at,
                        metadata_=record.metadata,
                    )
                    self._db.add(new_item)

                await self._db.commit()
            except Exception as e:
                logger.warning("db_persist_record_failed", error=str(e))

    async def _get_active_records(
        self,
        project_id: uuid.UUID | None = None,
        include_global: bool = True,
    ) -> list[MemoryRecord]:
        """Fetch active records matching project scope and global fallback."""
        records: list[MemoryRecord] = []

        # From memory store
        for r in self._memory_store.values():
            if r.status != MemoryStatus.ACTIVE:
                continue
            if project_id is not None:
                if r.project_id == project_id or (include_global and r.project_id is None):
                    records.append(r)
            else:
                if r.project_id is None or include_global:
                    records.append(r)

        return records

    def _from_db_model(self, db_item: Any) -> MemoryRecord:
        """Convert ORM AgentMemory model to domain MemoryRecord."""
        return MemoryRecord(
            memory_id=db_item.id,
            type=MemoryType(db_item.type) if db_item.type in [m.value for m in MemoryType] else MemoryType.USER_PREFERENCE,
            content=db_item.content,
            source=MemorySource(getattr(db_item, "source", "user_explicit")),
            confidence=getattr(db_item, "confidence", 1.0),
            importance=getattr(db_item, "importance", 0.5),
            project_id=db_item.project_id,
            content_hash=getattr(db_item, "content_hash", compute_content_hash(db_item.content)),
            embedding=db_item.embedding,
            created_at=db_item.created_at,
            updated_at=getattr(db_item, "updated_at", db_item.created_at),
            last_accessed_at=getattr(db_item, "last_accessed_at", db_item.created_at),
            expiration_at=getattr(db_item, "expiration_at", None),
            status=MemoryStatus(getattr(db_item, "status", "active")),
            metadata=getattr(db_item, "metadata_", {}),
        )
