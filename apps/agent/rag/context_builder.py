"""
rag.context_builder — Context Builder

Responsibilities:
  - Accept reranked RetrievedChunks + the original query
  - Format them into a bounded context string for the ContextManager
  - Include source citations (file path, line range, chunk index)
  - Enforce a maximum token budget for the RAG context block
  - Return a RAGContext with the formatted text and source list

The context builder is the final step in the RAG pipeline before
the assembled text enters the ContextWindow for model generation.
"""

from __future__ import annotations

import uuid

import structlog
import tiktoken

from rag.types import RAGContext, RetrievedChunk

logger = structlog.get_logger(__name__)

_TOKENIZER = tiktoken.get_encoding("cl100k_base")

_CONTEXT_HEADER = "=== Project Knowledge ===\n"
_SOURCE_TEMPLATE = "[{i}] {file_path}:{start_line}-{end_line}\n{content}\n"


class ContextBuilder:
    """
    Assembles ranked chunks into a formatted, token-bounded context string.
    """

    def __init__(self, max_context_tokens: int = 4096) -> None:
        self._max_tokens = max_context_tokens

    def build(
        self,
        query: str,
        chunks: list[RetrievedChunk],
        project_id: uuid.UUID,
    ) -> RAGContext:
        """
        Format chunks into a RAGContext, truncating if over token budget.

        Chunks are already sorted by relevance (reranker output).
        Higher-ranked chunks appear first in the context.
        """
        lines: list[str] = [_CONTEXT_HEADER]
        used_tokens = len(_TOKENIZER.encode(_CONTEXT_HEADER))
        included: list[RetrievedChunk] = []

        for i, rc in enumerate(chunks, start=1):
            meta = rc.chunk.metadata
            entry = _SOURCE_TEMPLATE.format(
                i=i,
                file_path=rc.chunk.file_path,
                start_line=meta.get("start_line", "?"),
                end_line=meta.get("end_line", "?"),
                content=rc.chunk.content,
            )
            entry_tokens = len(_TOKENIZER.encode(entry))

            if used_tokens + entry_tokens > self._max_tokens:
                logger.debug("context_budget_exceeded", chunk_index=i, used=used_tokens, budget=self._max_tokens)
                break

            lines.append(entry)
            used_tokens += entry_tokens
            included.append(rc)

        context_text = "".join(lines)
        return RAGContext(
            context_text=context_text,
            sources=included,
            query=query,
            project_id=project_id,
        )
