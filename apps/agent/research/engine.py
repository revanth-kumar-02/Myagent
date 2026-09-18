"""
research.engine — Central Web Research Subsystem Orchestrator (V6)

Complete Architecture:
  User Request
  → Research Planner
  → DuckDuckGo Search (Exclusive Provider)
  → Result Normalizer
  → Page Fetcher (when deep research requested)
  → Deduplication (URLs, domains, content)
  → Relevance Ranking
  → Evidence Extraction
  → Source Manager
  → Bounded Research Context (for Context Resolver / Agent Core)

Guarantees:
  - Uses ONLY DuckDuckGo (no Tavily, no external fallbacks)
  - Output flows strictly to Agent Context (never written to RAG / Memory DB)
  - Deterministic bounded token budgeting
"""

from __future__ import annotations

import asyncio
from typing import Sequence

import structlog
import tiktoken

from research.dedup import ResearchDeduplicator
from research.evidence import EvidenceExtractor
from research.fetcher import PageFetcher
from research.normalizer import ResultNormalizer
from research.planner import ResearchPlanner
from research.providers.duckduckgo import DuckDuckGoProvider
from research.ranker import RelevanceRanker
from research.source_manager import SourceManager
from research.types import (
    EvidenceItem,
    ResearchContext,
    ResearchDepth,
    ResearchPlan,
    ResearchResponse,
    WebResult,
    WebSource,
)

logger = structlog.get_logger(__name__)

_TOKENIZER = tiktoken.get_encoding("cl100k_base")
DEFAULT_MAX_RESEARCH_TOKENS = 2048


class WebResearchEngine:
    """
    Central orchestrator for DuckDuckGo Web Research.
    """

    def __init__(
        self,
        ddg_provider: DuckDuckGoProvider | None = None,
        fetcher: PageFetcher | None = None,
        max_context_tokens: int = DEFAULT_MAX_RESEARCH_TOKENS,
    ) -> None:
        self._provider = ddg_provider or DuckDuckGoProvider()
        self._fetcher = fetcher or PageFetcher()
        self._planner = ResearchPlanner()
        self._normalizer = ResultNormalizer()
        self._deduplicator = ResearchDeduplicator()
        self._ranker = RelevanceRanker()
        self._evidence_extractor = EvidenceExtractor()
        self._source_manager = SourceManager()
        self.max_context_tokens = max_context_tokens

    async def research(
        self,
        query: str,
        depth: ResearchDepth | None = None,
        max_results: int | None = None,
    ) -> ResearchContext:
        """
        Execute full research workflow and assemble a bounded ResearchContext.
        """
        # 1. Plan
        plan = self._planner.plan(query, explicit_depth=depth, max_results=max_results)

        # 2. Search DuckDuckGo (primary query + optional sub-queries)
        raw_results = await self._provider.search(plan.query, max_results=plan.max_results)

        if plan.sub_queries:
            sub_tasks = [self._provider.search(sq, max_results=2) for sq in plan.sub_queries[:2]]
            sub_res_lists = await asyncio.gather(*sub_tasks, return_exceptions=True)
            for sub_res in sub_res_lists:
                if isinstance(sub_res, list):
                    raw_results.extend(sub_res)

        if not raw_results:
            logger.info("web_research_no_results_found", query=plan.query)
            return ResearchContext(
                query=plan.query,
                summary_text="No relevant web search results found.",
                evidence_items=[],
                sources=[],
                token_count=0,
                provider_used="duckduckgo",
            )

        # 3. Normalize & Deduplicate
        normalized = [self._normalizer.normalize_result(r) for r in raw_results]
        deduped = self._deduplicator.deduplicate_results(normalized)

        # 4. Fetch Pages (if DEEP mode or plan requested)
        if plan.fetch_pages and deduped:
            urls_to_fetch = [r.url for r in deduped[:3]]  # Top 3 URLs
            page_contents = await self._fetcher.fetch_pages_batch(urls_to_fetch)
            for r in deduped:
                if r.url in page_contents and page_contents[r.url]:
                    r.raw_content = page_contents[r.url]

        # 5. Multi-Signal Relevance Ranking
        ranked = self._ranker.rank_results(plan.query, deduped)

        # 6. Extract Evidence & Register Sources
        evidence = self._evidence_extractor.extract_evidence(plan.query, ranked)
        sources = self._source_manager.register_results(ranked)

        # 7. Build Bounded Context Summary
        summary_text, token_count = self._build_bounded_summary(plan.query, ranked, evidence)

        return ResearchContext(
            query=plan.query,
            summary_text=summary_text,
            evidence_items=evidence,
            sources=sources,
            token_count=token_count,
            provider_used="duckduckgo",
        )

    async def search_raw(
        self,
        query: str,
        max_results: int = 5,
    ) -> ResearchResponse:
        """
        Direct search interface returning ResearchResponse.
        """
        ctx = await self.research(query, max_results=max_results)
        results = [
            WebResult(
                url=s.url,
                title=s.title,
                snippet=s.snippet,
                score=s.score,
                domain=s.domain,
                source="duckduckgo",
                raw_content=s.raw_content,
            )
            for s in ctx.sources
        ]
        return ResearchResponse(
            query=query,
            results=results,
            provider_used="duckduckgo",
            total_results=len(results),
            evidence_items=ctx.evidence_items,
            context_text=ctx.summary_text,
        )

    def _build_bounded_summary(
        self,
        query: str,
        results: Sequence[WebResult],
        evidence: Sequence[EvidenceItem],
    ) -> tuple[str, int]:
        """Format bounded evidence passages within token limit."""
        blocks: list[str] = [f"=== Web Research Results for '{query}' (via DuckDuckGo) ==="]
        tokens_used = len(_TOKENIZER.encode(blocks[0]))

        # Include evidence items
        for ev in evidence:
            citation = f"[{ev.source_title}]({ev.source_url}) [relevance: {ev.relevance_score:.2f}]"
            block = f"{citation}\n{ev.content.strip()}\n"
            block_tokens = len(_TOKENIZER.encode(block))

            if tokens_used + block_tokens > self.max_context_tokens:
                break

            blocks.append(block)
            tokens_used += block_tokens

        formatted = "\n\n".join(blocks)
        total_tokens = len(_TOKENIZER.encode(formatted))
        return formatted, total_tokens
