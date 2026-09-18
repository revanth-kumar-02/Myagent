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

import uuid
from pathlib import Path
from typing import Callable, Awaitable, TYPE_CHECKING

import structlog

from rag.chunker import StructuralChunker
from rag.embedder import EmbeddingService
from rag.parser import Parser
from rag.scanner import Scanner
from rag.types import FileEventType, IndexStats

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = structlog.get_logger(__name__)

WSSend = Callable[[dict], Awaitable[None]]


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
        model_router: object,
        ws_send: WSSend | None = None,
    ) -> None:
        self.project_id = project_id
        self.root_path = root_path
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
        stats = IndexStats()
        file_events = []

        # Collect all events first to know total count for progress reporting
        async for event in self._scanner.scan():
            file_events.append(event)

        total = len(file_events)

        for i, event in enumerate(file_events):
            await self._emit_progress(event.file_path, event.event_type.value, done=i, total=total)

            match event.event_type:
                case FileEventType.ADDED | FileEventType.CHANGED:
                    await self._ingest_file(event, stats)
                case FileEventType.DELETED:
                    await self._delete_file(event, stats)
                case FileEventType.SKIPPED:
                    stats.files_skipped += 1

        return stats

    # ── Private methods (stubs) ────────────────────────────────────────────────

    async def _ingest_file(self, event: object, stats: IndexStats) -> None:
        """Parse → chunk → embed → upsert to DB."""
        raise NotImplementedError  # TODO: implement in feature phase

    async def _delete_file(self, event: object, stats: IndexStats) -> None:
        """Remove file from indexed_files (chunks cascade-deleted)."""
        raise NotImplementedError  # TODO: implement in feature phase

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
