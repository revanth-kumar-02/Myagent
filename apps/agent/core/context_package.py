"""
core.context_package — Multi-Source Bounded Context Assembly & Budgeting (RAG V4)

Responsibilities:
  - Assemble heterogeneous context items (RAG, Memory, Web) into a single unified package
  - Enforce strict deterministic budgeting per source type and globally
  - Clearly demarcate verified facts vs unverified web sources vs personal memory
  - Extract structured provenance sources for API responses
"""

from __future__ import annotations

import uuid
from typing import Any

import structlog
import tiktoken

from core.types import AgentContextPackage, ContextItem, Source, SourceType, WebSource
from rag.types import RAGContext, RetrievedChunk

logger = structlog.get_logger(__name__)

_TOKENIZER = tiktoken.get_encoding("cl100k_base")

# Deterministic budget limits
DEFAULT_MAX_RAG_CHUNKS = 8
DEFAULT_MAX_RAG_TOKENS = 3072
DEFAULT_MAX_MEMORY_ITEMS = 4
DEFAULT_MAX_MEMORY_TOKENS = 512
DEFAULT_MAX_WEB_SOURCES = 4
DEFAULT_MAX_WEB_TOKENS = 1024
DEFAULT_MAX_TOTAL_TOKENS = 6144


class ContextPackageBuilder:
    """
    Assembles multi-source context items with strict budget enforcement and grounding.
    """

    def __init__(
        self,
        max_rag_chunks: int = DEFAULT_MAX_RAG_CHUNKS,
        max_rag_tokens: int = DEFAULT_MAX_RAG_TOKENS,
        max_memory_items: int = DEFAULT_MAX_MEMORY_ITEMS,
        max_memory_tokens: int = DEFAULT_MAX_MEMORY_TOKENS,
        max_web_sources: int = DEFAULT_MAX_WEB_SOURCES,
        max_web_tokens: int = DEFAULT_MAX_WEB_TOKENS,
        max_total_tokens: int = DEFAULT_MAX_TOTAL_TOKENS,
    ) -> None:
        self.max_rag_chunks = max_rag_chunks
        self.max_rag_tokens = max_rag_tokens
        self.max_memory_items = max_memory_items
        self.max_memory_tokens = max_memory_tokens
        self.max_web_sources = max_web_sources
        self.max_web_tokens = max_web_tokens
        self.max_total_tokens = max_total_tokens

    def assemble(
        self,
        *,
        rag_chunks: list[RetrievedChunk] | None = None,
        memory_entries: list[Any] | None = None,
        web_results: list[dict[str, Any]] | None = None,
        active_sources: set[SourceType] | None = None,
    ) -> AgentContextPackage:
        """
        Assemble multi-source inputs into an AgentContextPackage within token budgets.
        """
        items: list[ContextItem] = []
        rag_sources: list[Source] = []
        web_sources: list[WebSource] = []
        resolved = active_sources or set()

        # 1. Process RAG Knowledge Chunks
        rag_text_blocks: list[str] = []
        rag_tokens_used = 0

        if rag_chunks:
            resolved.add(SourceType.RAG)
            for i, rc in enumerate(rag_chunks[: self.max_rag_chunks], start=1):
                chunk_tokens = len(_TOKENIZER.encode(rc.chunk.content))
                if rag_tokens_used + chunk_tokens > self.max_rag_tokens:
                    break

                # Create ContextItem
                item = ContextItem(
                    content=rc.chunk.content,
                    source_type=SourceType.RAG,
                    score=rc.effective_score,
                    file_path=rc.file_path,
                    start_line=rc.start_line,
                    end_line=rc.end_line,
                    symbol=rc.symbol,
                    page=rc.page_number,
                    sheet=rc.sheet_name,
                    slide=rc.slide_number,
                    chunk_id=rc.chunk_id,
                )
                items.append(item)

                # Create API Source
                source_record = Source(
                    chunk_id=rc.chunk_id,
                    file_path=rc.file_path,
                    start_line=rc.start_line,
                    end_line=rc.end_line,
                    symbol=rc.symbol,
                    page=rc.page_number,
                    sheet=rc.sheet_name,
                    slide=rc.slide_number,
                    score=rc.effective_score,
                )
                rag_sources.append(source_record)

                # Provenance line
                prov = f"[{i}] {rc.file_path}"
                if rc.start_line and rc.end_line:
                    prov += f":{rc.start_line}-{rc.end_line}"
                if rc.symbol:
                    prov += f" (symbol: {rc.symbol})"
                if rc.sheet_name:
                    prov += f" (sheet: {rc.sheet_name})"
                if rc.page_number:
                    prov += f" (page: {rc.page_number})"
                if rc.slide_number:
                    prov += f" (slide: {rc.slide_number})"

                rag_text_blocks.append(f"{prov}\n{rc.chunk.content.strip()}\n")
                rag_tokens_used += chunk_tokens

        # 2. Process Memory Entries
        mem_text_blocks: list[str] = []
        mem_tokens_used = 0

        if memory_entries:
            resolved.add(SourceType.MEMORY)
            for entry in memory_entries[: self.max_memory_items]:
                content = entry.content if hasattr(entry, "content") else str(entry)
                entry_type = entry.type if hasattr(entry, "type") else "user_preference"
                if hasattr(entry_type, "value"):
                    entry_type = entry_type.value
                score = entry.score if hasattr(entry, "score") else 1.0

                entry_tokens = len(_TOKENIZER.encode(content))
                if mem_tokens_used + entry_tokens > self.max_memory_tokens:
                    break

                item = ContextItem(
                    content=content,
                    source_type=SourceType.MEMORY,
                    score=score,
                    title=f"memory:{entry_type}",
                )
                items.append(item)
                mem_text_blocks.append(f"- [{entry_type.upper()}] (relevance: {score:.2f}) {content.strip()}")
                mem_tokens_used += entry_tokens

        # 3. Process Web Research Results
        web_text_blocks: list[str] = []
        web_tokens_used = 0

        if web_results:
            resolved.add(SourceType.WEB)
            for w in web_results[: self.max_web_sources]:
                title = w.get("title", "Web Result")
                url = w.get("url", "")
                snippet = w.get("snippet", w.get("content", ""))
                score = float(w.get("score", 0.0))

                w_tokens = len(_TOKENIZER.encode(snippet))
                if web_tokens_used + w_tokens > self.max_web_tokens:
                    break

                item = ContextItem(
                    content=snippet,
                    source_type=SourceType.WEB,
                    score=score,
                    url=url,
                    title=title,
                )
                items.append(item)

                web_src = WebSource(url=url, title=title, snippet=snippet, score=score)
                web_sources.append(web_src)

                web_text_blocks.append(f"[{title}]({url})\n{snippet.strip()}\n")
                web_tokens_used += w_tokens

        # 4. Assemble Grounded Prompt Sections
        sections: list[str] = []

        if rag_text_blocks:
            sections.append(
                "=== [RAG] Verified Project Knowledge (High Confidence) ===\n"
                + "\n".join(rag_text_blocks)
            )

        if mem_text_blocks:
            sections.append(
                "=== [MEMORY] User Preferences & Persistent Context ===\n"
                + "\n".join(mem_text_blocks)
            )

        if web_text_blocks:
            sections.append(
                "=== [WEB] External Web Research (Unverified / Live Data) ===\n"
                + "\n".join(web_text_blocks)
            )

        formatted_text = "\n\n".join(sections).strip()
        total_tokens = len(_TOKENIZER.encode(formatted_text)) if formatted_text else 0

        return AgentContextPackage(
            items=items,
            rag_sources=rag_sources,
            web_sources=web_sources,
            formatted_text=formatted_text,
            token_count=total_tokens,
            resolved_sources=resolved,
        )
