"""
rag.chunker — Structural Chunker

Responsibilities:
  - Accept a ParsedDocument and produce a list of Chunks
  - Use structure-aware strategies per document type:
      CODE     → function/class boundary splitting
      MARKDOWN → heading-hierarchy splitting
      DOCUMENT → paragraph/section splitting
      PLAIN    → sliding window (token-based)
  - Each chunk carries full provenance metadata
  - Respects chunk_size_tokens and chunk_overlap_tokens from settings
  - Never embeds or stores chunks — that is the Embedder/Indexer's job

All chunking strategies target token counts (via tiktoken), not character counts.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

import structlog
import tiktoken

from config import settings
from rag.types import Chunk, DocumentType, ParsedDocument

if TYPE_CHECKING:
    pass

logger = structlog.get_logger(__name__)

# Use cl100k_base as a universal token counter (approximate for all models)
_TOKENIZER = tiktoken.get_encoding("cl100k_base")


def _count_tokens(text: str) -> int:
    return len(_TOKENIZER.encode(text))


class StructuralChunker:
    """
    Converts a ParsedDocument into a list of Chunks using structure-aware splitting.
    """

    def __init__(
        self,
        project_id: uuid.UUID,
        chunk_size: int = settings.rag_chunk_size_tokens,
        chunk_overlap: int = settings.rag_chunk_overlap_tokens,
    ) -> None:
        self.project_id = project_id
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def chunk(self, doc: ParsedDocument) -> list[Chunk]:
        """
        Dispatch to the appropriate chunking strategy and return Chunks.
        """
        match doc.doc_type:
            case DocumentType.CODE:
                return self._chunk_code(doc)
            case DocumentType.MARKDOWN:
                return self._chunk_markdown(doc)
            case DocumentType.DOCUMENT:
                return self._chunk_document(doc)
            case DocumentType.PLAIN:
                return self._chunk_sliding_window(doc)

    # ── Private strategies (stubs) ─────────────────────────────────────────────

    def _chunk_code(self, doc: ParsedDocument) -> list[Chunk]:
        """
        Split at function/class boundaries.
        Falls back to sliding window for files with no clear boundaries.
        Metadata includes: symbol (function/class name), start_line, end_line, language.
        """
        raise NotImplementedError  # TODO: implement in feature phase

    def _chunk_markdown(self, doc: ParsedDocument) -> list[Chunk]:
        """
        Split at heading boundaries (h1 > h2 > h3 hierarchy).
        Each chunk includes heading breadcrumb in metadata.
        """
        raise NotImplementedError  # TODO: implement in feature phase

    def _chunk_document(self, doc: ParsedDocument) -> list[Chunk]:
        """
        Split at paragraph/section boundaries.
        Falls back to sliding window for dense text.
        """
        raise NotImplementedError  # TODO: implement in feature phase

    def _chunk_sliding_window(self, doc: ParsedDocument) -> list[Chunk]:
        """
        Token-based sliding window with overlap.
        Used for plain text and as fallback for other types.
        """
        raise NotImplementedError  # TODO: implement in feature phase

    def _make_chunk(
        self,
        doc: ParsedDocument,
        index: int,
        content: str,
        extra_metadata: dict | None = None,
    ) -> Chunk:
        metadata = {**doc.metadata, **(extra_metadata or {})}
        return Chunk(
            chunk_index=index,
            content=content,
            doc_type=doc.doc_type,
            file_path=doc.file_path,
            project_id=self.project_id,
            metadata=metadata,
        )
