"""
research.dedup — Search Result and Evidence Deduplication (V6)

Responsibilities:
  - Canonical URL deduplication
  - Domain diversity enforcement (e.g. max 2 results per domain)
  - Near-duplicate content filtering via Jaccard token overlap & content hashes
"""

from __future__ import annotations

from typing import Sequence

from research.normalizer import compute_text_hash, extract_domain, sanitize_url
from research.types import WebResult, WebSource


class ResearchDeduplicator:
    """
    Filters redundant search results and near-duplicate source materials.
    """

    def __init__(
        self,
        max_per_domain: int = 2,
        similarity_threshold: float = 0.75,
    ) -> None:
        self.max_per_domain = max_per_domain
        self.similarity_threshold = similarity_threshold

    def deduplicate_results(self, results: Sequence[WebResult]) -> list[WebResult]:
        """
        Deduplicates a list of WebResults by canonical URL, domain diversity, and content similarity.
        """
        seen_urls: set[str] = set()
        domain_counts: dict[str, int] = {}
        unique_results: list[WebResult] = []

        for res in results:
            canon_url = sanitize_url(res.url)
            if not canon_url or canon_url in seen_urls:
                continue

            domain = res.domain or extract_domain(canon_url)
            if domain:
                if domain_counts.get(domain, 0) >= self.max_per_domain:
                    continue

            # Check near-duplicate snippet content with already accepted results
            if self._is_near_duplicate(res.snippet, [u.snippet for u in unique_results]):
                continue

            seen_urls.add(canon_url)
            res.url = canon_url
            if domain:
                domain_counts[domain] = domain_counts.get(domain, 0) + 1
            unique_results.append(res)

        return unique_results

    def _is_near_duplicate(self, text: str, existing_texts: list[str]) -> bool:
        """Check Jaccard word-set similarity against existing snippets."""
        if not text or not existing_texts:
            return False

        words = set(text.lower().split())
        if len(words) < 5:
            return False

        for existing in existing_texts:
            ex_words = set(existing.lower().split())
            if not ex_words:
                continue
            intersection = len(words & ex_words)
            union = len(words | ex_words)
            if union > 0 and (intersection / union) >= self.similarity_threshold:
                return True

        return False
