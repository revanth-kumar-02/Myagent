"""
research.providers.duckduckgo — DuckDuckGo Fallback Provider

Used when Tavily is unavailable or rate-limited.
Uses the duckduckgo-search library (no API key required).
"""

from __future__ import annotations

import structlog
from duckduckgo_search import AsyncDDGS

from config import settings
from research.types import WebResult

logger = structlog.get_logger(__name__)


class DuckDuckGoProvider:
    """
    DuckDuckGo search via duckduckgo-search async interface.
    No API key required — fallback provider.
    """

    async def search(self, query: str, max_results: int = settings.web_search_max_results) -> list[WebResult]:
        """
        Search DuckDuckGo and return normalised WebResult list.
        """
        raise NotImplementedError  # TODO: implement in feature phase
