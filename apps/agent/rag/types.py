"""
rag.types — Shared type definitions for the RAG pipeline (RAG V3).
"""

from __future__ import annotations

import os
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

# Maximum supported file size (25 MB) — files above this are skipped
MAX_FILE_SIZE_BYTES = 26_214_400


class FileEventType(str, Enum):
    ADDED   = "added"
    CHANGED = "changed"
    DELETED = "deleted"
    SKIPPED = "skipped"


class DocumentType(str, Enum):
    CODE        = "code"
    MARKDOWN    = "markdown"
    DOCUMENT    = "document"       # PDF, DOCX, DOC, PPTX, PPT
    SPREADSHEET = "spreadsheet"    # XLS, XLSX, CSV
    PLAIN       = "plain"


class SearchMode(str, Enum):
    HYBRID   = "hybrid"
    SEMANTIC = "semantic"
    KEYWORD  = "keyword"


@dataclass
class FileEvent:
    file_path: str
    event_type: FileEventType
    content_hash: str | None        # None for DELETED events
    file_size: int | None = None


@dataclass
class ParsedDocument:
    file_path: str
    doc_type: DocumentType
    content: str
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def file_name(self) -> str:
        return os.path.basename(self.file_path)

    @property
    def extension(self) -> str:
        return os.path.splitext(self.file_path)[1].lower()


@dataclass
class Chunk:
    """A single indexable unit of content with structural metadata."""
    chunk_index: int
    content: str
    doc_type: DocumentType
    file_path: str
    project_id: uuid.UUID
    metadata: dict[str, Any] = field(default_factory=dict)
    id: uuid.UUID = field(default_factory=uuid.uuid4)
    embedding: list[float] | None = None

    @property
    def file_name(self) -> str:
        return os.path.basename(self.file_path)


@dataclass
class RetrievedChunk:
    """A chunk returned from retrieval, with multi-signal scores & provenance."""
    chunk: Chunk
    dense_rank: int | None = None       # rank from vector search
    sparse_rank: int | None = None      # rank from full-text search
    dense_score: float | None = None    # cosine similarity score (0.0 - 1.0)
    sparse_score: float | None = None   # BM25/ts_rank score
    exact_match_boost: float = 0.0      # boost for exact symbol/token matches
    path_match_boost: float = 0.0       # boost for file path query matches
    metadata_boost: float = 0.0         # boost for metadata/structural matches
    structural_boost: float = 0.0       # boost for page/sheet/slide/symbol queries
    rrf_score: float = 0.0              # Reciprocal Rank Fusion score
    combined_score: float = 0.0         # Final multi-signal combined score
    reranker_score: float | None = None # cross-encoder score (post-rerank)
    db_id: uuid.UUID | None = None      # chunk.id in PostgreSQL

    # Convenience accessors for rich provenance
    @property
    def file_path(self) -> str:
        return self.chunk.file_path

    @property
    def file_name(self) -> str:
        return os.path.basename(self.chunk.file_path)

    @property
    def chunk_id(self) -> uuid.UUID:
        return self.db_id or self.chunk.id

    @property
    def doc_type(self) -> DocumentType:
        return self.chunk.doc_type

    @property
    def content(self) -> str:
        return self.chunk.content

    @property
    def start_line(self) -> int | None:
        return self.chunk.metadata.get("start_line")

    @property
    def end_line(self) -> int | None:
        return self.chunk.metadata.get("end_line")

    @property
    def symbol(self) -> str | None:
        return self.chunk.metadata.get("symbol")

    @property
    def headings(self) -> list[str] | None:
        return self.chunk.metadata.get("headings")

    @property
    def section(self) -> str | None:
        return self.chunk.metadata.get("section")

    @property
    def page_number(self) -> int | None:
        return self.chunk.metadata.get("page_number") or self.chunk.metadata.get("page")

    @property
    def sheet_name(self) -> str | None:
        return self.chunk.metadata.get("sheet_name") or self.chunk.metadata.get("sheet")

    @property
    def cell_range(self) -> str | None:
        return self.chunk.metadata.get("cell_range")

    @property
    def slide_number(self) -> int | None:
        return self.chunk.metadata.get("slide_number") or self.chunk.metadata.get("slide")

    @property
    def slide_title(self) -> str | None:
        return self.chunk.metadata.get("slide_title") or self.chunk.metadata.get("title")

    @property
    def headers(self) -> list[str] | None:
        return self.chunk.metadata.get("headers")

    @property
    def row_start(self) -> int | None:
        return self.chunk.metadata.get("row_start")

    @property
    def row_end(self) -> int | None:
        return self.chunk.metadata.get("row_end")

    @property
    def effective_score(self) -> float:
        """Returns reranker score if present, else combined score or rrf score."""
        if self.reranker_score is not None:
            return self.reranker_score
        if self.combined_score > 0.0:
            return self.combined_score
        return self.rrf_score


@dataclass
class RetrievalResult:
    """Public retrieval API response container."""
    chunks: list[RetrievedChunk]
    query: str
    project_id: uuid.UUID
    mode: SearchMode
    total_count: int = 0
    latency_ms: int = 0


@dataclass
class RAGContext:
    """Assembled context ready for the ContextManager."""
    context_text: str
    sources: list[RetrievedChunk]
    query: str
    project_id: uuid.UUID
    token_count: int = 0


@dataclass
class IndexStats:
    files_added: int = 0
    files_changed: int = 0
    files_deleted: int = 0
    files_skipped: int = 0
    chunks_total: int = 0
    duration_ms: int = 0
    errors: list[str] = field(default_factory=list)
