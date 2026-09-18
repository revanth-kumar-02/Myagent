"""
research.planner — Research Query Formulation and Depth Planning (V6)

Responsibilities:
  - Formulate optimal search query terms
  - Decompose multi-faceted research requests into sub-queries
  - Determine research depth (QUICK vs DEEP)
  - Decide whether full page fetching is required
"""

from __future__ import annotations

import re
from typing import Sequence

from research.types import ResearchDepth, ResearchPlan

# Keywords indicating deep research necessity
_DEEP_KEYWORDS = [
    re.compile(r"\b(?:in-depth|detailed|documentation|full spec|benchmarks?|deep dive|comprehensive|deep research|compare in detail)\b", re.IGNORECASE),
    re.compile(r"\b(?:architecture of|technical specifications|step by step guide|whitepaper|changelog)\b", re.IGNORECASE),
]

# Stopwords/phrases to remove from search queries for better DDG indexing
_SEARCH_PREFIXES = [
    re.compile(r"^(?:search the web for|search online for|look up|search for|google|find me|what is the|tell me about)\s+", re.IGNORECASE),
    re.compile(r"^(?:can you search|please search|look on duckduckgo for)\s+", re.IGNORECASE),
]


class ResearchPlanner:
    """
    Analyzes research intent to produce a concrete ResearchPlan.
    """

    def plan(
        self,
        user_message: str,
        explicit_depth: ResearchDepth | None = None,
        max_results: int | None = None,
    ) -> ResearchPlan:
        """
        Formulate a ResearchPlan based on user request.
        """
        msg_clean = user_message.strip()

        # 1. Clean query for search engine
        query = self._sanitize_query(msg_clean)

        # 2. Determine Depth
        if explicit_depth is not None:
            depth = explicit_depth
        else:
            is_deep = any(p.search(msg_clean) for p in _DEEP_KEYWORDS)
            depth = ResearchDepth.DEEP if is_deep else ResearchDepth.QUICK

        # 3. Determine max_results & page fetching
        if depth == ResearchDepth.DEEP:
            target_results = max_results or 6
            fetch_pages = True
        else:
            target_results = max_results or 4
            fetch_pages = False

        # 4. Decompose sub-queries if query contains multiple parts (e.g. "compare X vs Y")
        sub_queries = self._generate_sub_queries(query, msg_clean)

        return ResearchPlan(
            query=query,
            sub_queries=sub_queries,
            depth=depth,
            max_results=target_results,
            fetch_pages=fetch_pages,
        )

    def _sanitize_query(self, message: str) -> str:
        """Extract clean query keywords."""
        q = message
        for p in _SEARCH_PREFIXES:
            q = p.sub("", q)
        q = q.strip(" ?.!\"'")
        return q if len(q) >= 3 else message.strip()

    def _generate_sub_queries(self, query: str, full_msg: str) -> list[str]:
        """Generate targeted sub-queries for comparative or multi-topic questions."""
        sub_queries: list[str] = []

        # Check comparison: "X vs Y" or "compare X and Y"
        match = re.search(r"(\b[\w\.-]+)\s+(?:vs|versus|compared to)\s+([\w\.-]+)", query, re.IGNORECASE)
        if match:
            term1 = match.group(1).strip()
            term2 = match.group(2).strip()
            if term1 and term2:
                sub_queries.append(f"{term1} overview")
                sub_queries.append(f"{term2} overview")

        return sub_queries
