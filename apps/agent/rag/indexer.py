"""
rag.indexer — Indexer

Responsibilities:
  - Orchestrate the full ingestion pipeline: Scanner → Parser → Chunker → Embedder → DB
  - Handle added, changed, and deleted files correctly
  - Stream INDEX_PROGRESS WebSocket events per file
  - Write results to PostgreSQL (indexed_files + chunks tables)
  - Return IndexStats on completion

This is the only component that writes to the RAG database tables.
"""

from __future__ import annotations

import time
import uuid
from pathlib import Path
from typing import TYPE_CHECKING, Any, Awaitable, Callable

import structlog
from sqlalchemy import delete, func, select

from db.schema import Chunk as DBChunk, IndexedFile
from rag.chunker import StructuralChunker
from rag.embedder import EmbeddingService
from rag.parser import Parser
from rag.scanner import Scanner
from rag.types import FileEvent, FileEventType, IndexStats

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = structlog.get_logger(__name__)

WSSend = Callable[[dict[str, Any]], Awaitable[None]]


class Indexer:
    """
    Drives the full ingestion pipeline for a project.
    Streams progress events to the connected WebSocket client.
    """

    def __init__(
        self,
        project_id: uuid.UUID,
        root_path: Path,
        db: "AsyncSession",
        model_router: object | None = None,
        ws_send: WSSend | None = None,
    ) -> None:
        self.project_id = project_id
        self.root_path = Path(root_path)
        self._db = db
        self._ws_send = ws_send

        self._scanner = Scanner(project_id, root_path, db)
        self._parser = Parser()
        self._chunker = StructuralChunker(project_id)
        self._embedder = EmbeddingService(model_router)

    async def run(self, incremental: bool = True) -> IndexStats:
        """
        Run the indexing pipeline.

        If incremental=True: only process changed/added/deleted files.
        If incremental=False: re-index all files (full rebuild).

        Emits INDEX_PROGRESS WebSocket frames for each processed file.
        Returns IndexStats when complete.
        """
        start_time = time.monotonic()
        stats = IndexStats()
        file_events: list[FileEvent] = []

        try:
            # Collect all events
            async for event in self._scanner.scan():
                file_events.append(event)
        except Exception as e:
            logger.error("scanner_failed", error=str(e))
            stats.errors.append(f"Scanner error: {e}")
            return stats

        total = len(file_events)

        for i, event in enumerate(file_events):
            await self._emit_progress(event.file_path, event.event_type.value, done=i, total=total)

            try:
                match event.event_type:
                    case FileEventType.ADDED | FileEventType.CHANGED:
                        await self._ingest_file(event, stats)
                    case FileEventType.DELETED:
                        await self._delete_file(event, stats)
                    case FileEventType.SKIPPED:
                        stats.files_skipped += 1
            except Exception as e:
                err_msg = f"Failed processing {event.file_path}: {e}"
                logger.error("file_ingest_error", file=event.file_path, error=str(e))
                stats.errors.append(err_msg)

        stats.duration_ms = int((time.monotonic() - start_time) * 1000)
        logger.info(
            "indexing_complete",
            added=stats.files_added,
            changed=stats.files_changed,
            deleted=stats.files_deleted,
            skipped=stats.files_skipped,
            chunks=stats.chunks_total,
            duration_ms=stats.duration_ms,
        )
        return stats

    # ── Private methods ────────────────────────────────────────────────────────

    async def _ingest_file(self, event: FileEvent, stats: IndexStats) -> None:
        """Parse → chunk → embed → upsert to DB."""
        abs_path = self.root_path / event.file_path
        if not abs_path.exists():
            logger.warning("file_not_found_on_disk", path=str(abs_path))
            return

        # 1. Parse document
        parsed_doc = await self._parser.parse(abs_path)
        if parsed_doc is None:
            logger.debug("no_parsed_content", file=event.file_path)
            return

        # 2. Structural chunking
        chunks = self._chunker.chunk(parsed_doc)
        if not chunks:
            # Empty file or no content chunks
            logger.debug("no_chunks_extracted", file=event.file_path)
            return

        # 3. Batch embeddings
        try:
            chunks = await self._embedder.embed(chunks)
        except Exception as e:
            logger.warning("embedder_failed_indexing_without_vectors", file=event.file_path, error=str(e))

        # 4. Upsert indexed_files record
        stmt = select(IndexedFile).where(
            IndexedFile.project_id == self.project_id,
            IndexedFile.file_path == event.file_path,
        )
        result = await self._db.execute(stmt)
        indexed_file = result.scalar_one_or_none()

        if indexed_file is None:
            indexed_file = IndexedFile(
                id=uuid.uuid4(),
                project_id=self.project_id,
                file_path=event.file_path,
                content_hash=event.content_hash or "",
                file_size=event.file_size,
            )
            self._db.add(indexed_file)
            await self._db.flush()
            stats.files_added += 1
        else:
            indexed_file.content_hash = event.content_hash or ""
            indexed_file.file_size = event.file_size
            indexed_file.last_seen = func.now()
            # Delete existing chunks for this file
            await self._db.execute(
                delete(DBChunk).where(DBChunk.file_id == indexed_file.id)
            )
            stats.files_changed += 1

        # 5. Insert new chunks
        for chunk in chunks:
            db_chunk = DBChunk(
                id=chunk.id,
                project_id=self.project_id,
                file_id=indexed_file.id,
                chunk_index=chunk.chunk_index,
                content=chunk.content,
                embedding=chunk.embedding,
                metadata_={
                    **chunk.metadata,
                    "doc_type": chunk.doc_type.value,
                    "file_path": chunk.file_path,
                },
            )
            self._db.add(db_chunk)

        await self._db.commit()
        stats.chunks_total += len(chunks)

    async def _delete_file(self, event: FileEvent, stats: IndexStats) -> None:
        """Remove file from indexed_files (chunks cascade-deleted)."""
        await self._db.execute(
            delete(IndexedFile).where(
                IndexedFile.project_id == self.project_id,
                IndexedFile.file_path == event.file_path,
            )
        )
        await self._db.commit()
        stats.files_deleted += 1

    async def _emit_progress(
        self, file_path: str, event: str, done: int, total: int
    ) -> None:
        if self._ws_send is None:
            return
        await self._ws_send({
            "type": "INDEX_PROGRESS",
            "payload": {
                "file_path": file_path,
                "event": event,
                "done": done,
                "total": total,
            },
        })
