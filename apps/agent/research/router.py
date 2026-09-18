"""
research.router — Research Router

Responsibilities:
  - Try Tavily (primary provider) first
  - Fall back to DuckDuckGo on Tavily failure or missing API key
  - Normalise results from both providers to the same WebResult schema
  - Keep web research completely isolated from the RAG pipeline
    (results are NEVER written to the RAG database)

Separation guarantee:
  This module's output flows only to the ContextBuilder / Executor.
  It does not import from rag.* and does not write to the DB.
"""

from __future__ import annotations

import structlog

from config import settings
from research.normalizer import ResultNormalizer
from research.providers.duckduckgo import DuckDuckGoProvider
from research.providers.tavily import TavilyError, TavilyProvider
from research.types import ResearchResponse, WebResult

logger = structlog.get_logger(__name__)


class ResearchRouter:
    """
    Tavily → DuckDuckGo fallback router.
    Instantiated once and shared across sessions.
    """

    def __init__(self) -> None:
        self._normalizer = ResultNormalizer()
        self._ddg = DuckDuckGoProvider()
        self._tavily: TavilyProvider | None = None

        if settings.tavily_api_key:
            try:
                self._tavily = TavilyProvider()
            except ValueError:
                logger.warning("tavily_init_failed_missing_key")

    async def search(
        self,
        query: str,
        max_results: int = settings.web_search_max_results,
    ) -> ResearchResponse:
        """
        Search the web. Tries Tavily first; falls back to DuckDuckGo.
        Returns a ResearchResponse with normalised WebResult list.
        """
        if self._tavily is not None:
            try:
                results = await self._tavily.search(query, max_results)
                return ResearchResponse(
                    query=query,
                    results=results,
                    provider_used="tavily",
                    total_results=len(results),
                )
            except TavilyError as e:
                logger.warning("tavily_fallback", error=str(e))

        results = await self._ddg.search(query, max_results)
        return ResearchResponse(
            query=query,
            results=results,
            provider_used="duckduckgo",
            total_results=len(results),
        )
