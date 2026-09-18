"""
research.source_manager — Web Source Provenance Registry (V6)

Responsibilities:
  - Track metadata, domains, retrieval timestamps, and hashes for all consulted web sources
  - Prevent duplicate source registration
  - Provide queryable registry of sources for API responses and citations
"""

from __future__ import annotations

from typing import Sequence

from research.normalizer import ResultNormalizer, compute_text_hash, extract_domain, sanitize_url
from research.types import WebResult, WebSource


class SourceManager:
    """
    Registry for consulted web sources in research operations.
    """

    def __init__(self) -> None:
        self._sources: dict[str, WebSource] = {}
        self._normalizer = ResultNormalizer()

    def register_results(self, results: Sequence[WebResult]) -> list[WebSource]:
        """
        Register a batch of WebResults and return WebSource objects.
        """
        registered: list[WebSource] = []
        for res in results:
            canon_url = sanitize_url(res.url)
            if not canon_url:
                continue

            if canon_url in self._sources:
                existing = self._sources[canon_url]
                # Update content if raw content became available
                if res.raw_content and not existing.raw_content:
                    existing.raw_content = res.raw_content
                registered.append(existing)
            else:
                source = self._normalizer.to_web_source(res)
                self._sources[canon_url] = source
                registered.append(source)

        return registered

    def get_source(self, url: str) -> WebSource | None:
        """Get source by URL."""
        return self._sources.get(sanitize_url(url))

    def get_all_sources(self) -> list[WebSource]:
        """Return all tracked sources."""
        return list(self._sources.values())

    def clear(self) -> None:
        """Clear the registry."""
        self._sources.clear()
