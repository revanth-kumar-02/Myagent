"""
research.ranker — Multi-Signal Relevance Ranking for Web Results (V6)

Scoring signals:
  - Lexical query coverage (term matching in title and snippet): 45%
  - Search engine position decay: 30%
  - Domain authority heuristic: 15%
  - Content completeness: 10%
"""

from __future__ import annotations

import re
from typing import Sequence

from research.types import WebResult

# High-authority technical documentation and developer domains
_AUTHORITY_DOMAINS = {
    "github.com",
    "docs.python.org",
    "pypi.org",
    "developer.mozilla.org",
    "stackoverflow.com",
    "fastapi.tiangolo.com",
    "postgresql.org",
    "redis.io",
    "flutter.dev",
    "dart.dev",
    "medium.com",
    "dev.to",
    "wikipedia.org",
    "arxiv.org",
}


class RelevanceRanker:
    """
    Ranks WebResult items using multi-signal scoring.
    """

    def rank_results(
        self,
        query: str,
        results: Sequence[WebResult],
    ) -> list[WebResult]:
        """
        Calculates relevance scores and sorts results descending.
        """
        if not results:
            return []

        query_terms = [t.lower() for t in re.findall(r"\w+", query) if len(t) > 2]
        scored_results: list[tuple[float, WebResult]] = []

        for idx, res in enumerate(results):
            # 1. Lexical matching
            lexical_score = self._compute_lexical_score(query_terms, res.title, res.snippet)

            # 2. Position decay factor
            pos_score = max(0.2, 1.0 - (idx * 0.10))

            # 3. Domain authority
            domain_score = 1.0 if res.domain in _AUTHORITY_DOMAINS else 0.5

            # 4. Content completeness
            content_len = len(res.snippet)
            completeness = min(1.0, content_len / 150.0)

            final_score = (
                (0.45 * lexical_score)
                + (0.30 * pos_score)
                + (0.15 * domain_score)
                + (0.10 * completeness)
            )

            res.score = round(final_score, 4)
            scored_results.append((final_score, res))

        scored_results.sort(key=lambda x: x[0], reverse=True)
        return [item[1] for item in scored_results]

    def _compute_lexical_score(self, terms: list[str], title: str, snippet: str) -> float:
        """Compute lexical coverage of query terms in title (2x weight) and snippet."""
        if not terms:
            return 0.5

        t_lower = title.lower()
        s_lower = snippet.lower()

        title_hits = sum(1 for term in terms if term in t_lower)
        snip_hits = sum(1 for term in terms if term in s_lower)

        coverage = ((title_hits * 2.0) + snip_hits) / (len(terms) * 2.0)
        return min(1.0, coverage)
