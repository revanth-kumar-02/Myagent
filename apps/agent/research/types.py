"""
research.types — Web Research type definitions.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class WebResult:
    """Normalised result from any web search provider."""
    url: str
    title: str
    snippet: str
    score: float        # provider-assigned relevance score (0-1)
    source: str         # provider name: "tavily" | "duckduckgo"
    raw_content: str | None = None  # full page content if fetched


@dataclass
class ResearchResponse:
    """Assembled web research response."""
    query: str
    results: list[WebResult]
    provider_used: str
    total_results: int
