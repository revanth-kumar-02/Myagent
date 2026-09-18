"""
research.router — Research Router (V6)

Exclusive DuckDuckGo Routing:
  - Directs all web search requests exclusively to DuckDuckGoProvider / WebResearchEngine
  - No Tavily or other search providers
  - Guarantees search output flows only to the Agent Context Layer
  - Strict isolation: Results are NEVER written to PostgreSQL RAG or Memory tables
"""

from __future__ import annotations

import structlog

from config import settings
from research.engine import WebResearchEngine
from research.normalizer import ResultNormalizer
from research.providers.duckduckgo import DuckDuckGoProvider
from research.types import ResearchDepth, ResearchResponse, WebResult

logger = structlog.get_logger(__name__)


class ResearchRouter:
    """
    Exclusive DuckDuckGo Research Router.
    """

    def __init__(
        self,
        engine: WebResearchEngine | None = None,
    ) -> None:
        self._engine = engine or WebResearchEngine()
        self._provider = DuckDuckGoProvider()
        self._normalizer = ResultNormalizer()

    async def search(
        self,
        query: str,
        max_results: int = settings.web_search_max_results,
        depth: ResearchDepth | None = None,
    ) -> ResearchResponse:
        """
        Execute web research via DuckDuckGo and return normalized ResearchResponse.
        """
        return await self._engine.search_raw(query=query, max_results=max_results)
