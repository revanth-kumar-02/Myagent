"""
research.normalizer — Result Normalizer

Converts provider-specific result formats to the unified WebResult schema.
"""

from __future__ import annotations

from research.types import WebResult


class ResultNormalizer:
    """Converts raw provider dicts to normalised WebResult objects."""

    def from_tavily(self, raw: dict) -> WebResult:
        return WebResult(
            url=raw.get("url", ""),
            title=raw.get("title", ""),
            snippet=raw.get("content", ""),
            score=float(raw.get("score", 0.0)),
            source="tavily",
            raw_content=raw.get("raw_content"),
        )

    def from_duckduckgo(self, raw: dict) -> WebResult:
        return WebResult(
            url=raw.get("href", ""),
            title=raw.get("title", ""),
            snippet=raw.get("body", ""),
            score=0.5,           # DDG provides no relevance score; fixed midpoint
            source="duckduckgo",
        )
