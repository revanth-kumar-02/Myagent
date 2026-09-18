"""
research.providers.tavily — Tavily Search Provider

Primary web research provider.
Uses the official tavily-python SDK.
Requires KORA_TAVILY_API_KEY in environment.
"""

from __future__ import annotations

import structlog
from tavily import AsyncTavilyClient

from config import settings
from research.types import WebResult

logger = structlog.get_logger(__name__)


class TavilyProvider:
    """
    Wraps the Tavily async client.
    Returns normalised WebResult objects.
    """

    def __init__(self) -> None:
        if not settings.tavily_api_key:
            raise ValueError("KORA_TAVILY_API_KEY is not set — Tavily provider cannot initialise")
        self._client = AsyncTavilyClient(api_key=settings.tavily_api_key)

    async def search(self, query: str, max_results: int = settings.web_search_max_results) -> list[WebResult]:
        """
        Search Tavily and return normalised WebResult list.
        Raises TavilyError on API failure (caller handles fallback).
        """
        raise NotImplementedError  # TODO: implement in feature phase


class TavilyError(Exception):
    """Raised on Tavily API failure."""
