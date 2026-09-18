"""
rag.types — Shared type definitions for the RAG pipeline.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class FileEventType(str, Enum):
    ADDED   = "added"
    CHANGED = "changed"
    DELETED = "deleted"
    SKIPPED = "skipped"


class DocumentType(str, Enum):
    CODE     = "code"
    MARKDOWN = "markdown"
    DOCUMENT = "document"   # PDF, DOCX, PPTX
    PLAIN    = "plain"


@dataclass
class FileEvent:
    file_path: str
    event_type: FileEventType
    content_hash: str | None     # None for DELETED events
    file_size: int | None = None


@dataclass
class ParsedDocument:
    file_path: str
    doc_type: DocumentType
    content: str
    metadata: dict[str, Any] = field(default_factory=dict)
    # metadata: language (for code), headings (for md), title (for docs), encoding


@dataclass
class Chunk:
    """A single indexable unit of content."""
    chunk_index: int
    content: str
    doc_type: DocumentType
    file_path: str
    project_id: uuid.UUID
    metadata: dict[str, Any] = field(default_factory=dict)
    # metadata: start_line, end_line, symbol (function/class name for code), headings[]
    id: uuid.UUID = field(default_factory=uuid.uuid4)
    embedding: list[float] | None = None


@dataclass
class RetrievedChunk:
    """A chunk returned from hybrid retrieval, with scores."""
    chunk: Chunk
    dense_rank: int | None = None       # rank from vector search
    sparse_rank: int | None = None      # rank from full-text search
    rrf_score: float = 0.0             # Reciprocal Rank Fusion score
    reranker_score: float | None = None # cross-encoder score (post-rerank)
    db_id: uuid.UUID | None = None     # chunk.id in PostgreSQL


@dataclass
class RAGContext:
    """Assembled context ready for the ContextManager."""
    context_text: str
    sources: list[RetrievedChunk]
    query: str
    project_id: uuid.UUID


@dataclass
class IndexStats:
    files_added: int = 0
    files_changed: int = 0
    files_deleted: int = 0
    files_skipped: int = 0
    chunks_total: int = 0
    duration_ms: int = 0
