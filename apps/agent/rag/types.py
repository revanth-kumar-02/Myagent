"""
rag.types — Shared type definitions for the RAG pipeline.
"""

from __future__ import annotations

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
    SPREADSHEET = "spreadsheet"    # XLS, XLSX
    PLAIN       = "plain"


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
    # Metadata keys (type-dependent):
    #   code:        language, line_count, file_size
    #   markdown:    headings (list), line_count
    #   document:    title, page_count, author (PDF); section_count (DOCX); slide_count (PPTX)
    #   spreadsheet: sheet_names (list), sheet_count, total_rows
    #   plain:       extension, line_count, encoding


@dataclass
class Chunk:
    """A single indexable unit of content."""
    chunk_index: int
    content: str
    doc_type: DocumentType
    file_path: str
    project_id: uuid.UUID
    metadata: dict[str, Any] = field(default_factory=dict)
    # Metadata keys (type-dependent):
    #   ALL:         start_line, end_line
    #   code:        symbol, language
    #   markdown:    headings (breadcrumb list), level
    #   document:    page, slide, section
    #   spreadsheet: sheet_name, row_start, row_end
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
    # Convenience accessors
    @property
    def file_path(self) -> str:
        return self.chunk.file_path
    @property
    def chunk_id(self) -> uuid.UUID:
        return self.db_id or self.chunk.id
    @property
    def start_line(self) -> int | None:
        return self.chunk.metadata.get("start_line")
    @property
    def end_line(self) -> int | None:
        return self.chunk.metadata.get("end_line")


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
    errors: list[str] = field(default_factory=list)
