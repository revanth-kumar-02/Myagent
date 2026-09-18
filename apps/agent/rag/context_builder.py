"""
rag.context_builder — Document Intelligence Context Builder (RAG V3)

Responsibilities:
  - Assemble ranked RetrievedChunks into structured, token-bounded context strings
  - Format rich provenance tags:
      - Location (file_path, line span, cell_range)
      - Document structural cues (page, sheet, slide, title, section, symbol, headers)
      - Document type and relevance score
  - Enforce strict token limits to prevent LLM context overflows
"""

from __future__ import annotations

import uuid

import structlog
import tiktoken

from rag.types import RAGContext, RetrievedChunk

logger = structlog.get_logger(__name__)

_TOKENIZER = tiktoken.get_encoding("cl100k_base")

_CONTEXT_HEADER = "=== Project Knowledge Context ===\n\n"


def _format_provenance_header(rc: RetrievedChunk, index: int) -> str:
    """Construct a rich provenance header line for a chunk."""
    meta = rc.chunk.metadata

    # 1. Base Location
    if rc.start_line is not None and rc.end_line is not None:
        loc = f"[{index}] {rc.file_path}:{rc.start_line}-{rc.end_line}"
    elif rc.start_line is not None:
        loc = f"[{index}] {rc.file_path}:{rc.start_line}"
    else:
        loc = f"[{index}] {rc.file_path}"

    # 2. Structural Attributes & Tags
    doc_type_str = rc.doc_type.value if hasattr(rc.doc_type, "value") else str(rc.doc_type)
    tags = [f"type: {doc_type_str}"]

    # Code symbols
    if rc.symbol:
        tags.append(f"symbol: {rc.symbol}")

    # Headings / Sections
    if rc.headings:
        tags.append(f"heading: {' > '.join(rc.headings)}")
    elif rc.section:
        tags.append(f"section: {rc.section}")
    elif meta.get("heading"):
        tags.append(f"heading: {meta.get('heading')}")

    # Pages
    if rc.page_number is not None:
        tags.append(f"page: {rc.page_number}")

    # Sheets & Cell Ranges
    if rc.sheet_name:
        tags.append(f"sheet: {rc.sheet_name}")
    if rc.cell_range:
        tags.append(f"range: {rc.cell_range}")

    # Slides & Presentation Titles
    if rc.slide_number is not None:
        tags.append(f"slide: {rc.slide_number}")
    if rc.slide_title:
        tags.append(f"title: {rc.slide_title}")

    # CSV Headers & Rows
    if rc.headers:
        tags.append(f"headers: {', '.join(rc.headers[:5])}")
    if rc.row_start is not None and rc.row_end is not None:
        tags.append(f"rows: {rc.row_start}-{rc.row_end}")

    # Effective score
    score = rc.effective_score
    if score > 0.0:
        tags.append(f"score: {score:.3f}")

    return f"{loc} ({', '.join(tags)})\n"


class ContextBuilder:
    """
    Assembles ranked chunks into a formatted, token-bounded context string with rich provenance.
    """

    def __init__(self, max_context_tokens: int = 4096) -> None:
        self._max_tokens = max_context_tokens

    def build(
        self,
        query: str,
        chunks: list[RetrievedChunk],
        project_id: uuid.UUID,
        max_tokens: int | None = None,
    ) -> RAGContext:
        """
        Format chunks into a RAGContext, strictly bounded within the token budget.
        """
        budget = max_tokens or self._max_tokens
        lines: list[str] = [_CONTEXT_HEADER]
        used_tokens = len(_TOKENIZER.encode(_CONTEXT_HEADER))
        included: list[RetrievedChunk] = []

        for i, rc in enumerate(chunks, start=1):
            prov_header = _format_provenance_header(rc, i)
            entry = f"{prov_header}{rc.chunk.content.strip()}\n\n"
            entry_tokens = len(_TOKENIZER.encode(entry))

            if used_tokens + entry_tokens > budget:
                logger.debug(
                    "context_budget_reached",
                    chunk_index=i,
                    used=used_tokens,
                    budget=budget,
                )
                break

            lines.append(entry)
            used_tokens += entry_tokens
            included.append(rc)

        context_text = "".join(lines).strip()
        return RAGContext(
            context_text=context_text,
            sources=included,
            query=query,
            project_id=project_id,
            token_count=used_tokens,
        )
