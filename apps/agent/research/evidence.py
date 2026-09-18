"""
research.evidence — Evidence Extraction and Grounding Layer (V6)

Responsibilities:
  - Extract salient factual evidence from search snippets and fetched web pages
  - Retain strict provenance (source URL, title, domain, timestamp, relevance score)
  - Format structured EvidenceItem objects for bounded context assembly
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Sequence

from research.types import EvidenceItem, WebResult


class EvidenceExtractor:
    """
    Extracts relevant factual evidence passages with full source provenance.
    """

    def extract_evidence(
        self,
        query: str,
        results: Sequence[WebResult],
        max_evidence_per_source: int = 2,
    ) -> list[EvidenceItem]:
        """
        Extract high-signal evidence passages from search results and page contents.
        """
        evidence_list: list[EvidenceItem] = []
        now = datetime.now(timezone.utc)
        query_terms = [t.lower() for t in re.findall(r"\w+", query) if len(t) > 2]

        for res in results:
            # 1. Primary snippet evidence
            if res.snippet:
                evidence_list.append(
                    EvidenceItem(
                        source_url=res.url,
                        source_title=res.title,
                        content=res.snippet,
                        relevance_score=res.score,
                        retrieved_at=now,
                        domain=res.domain,
                    )
                )

            # 2. Extract additional passages if full page content was fetched
            if res.raw_content:
                paragraphs = [p.strip() for p in res.raw_content.split("\n\n") if len(p.strip()) > 60]
                scored_paragraphs: list[tuple[float, str]] = []

                for para in paragraphs:
                    # Skip if identical to snippet
                    if res.snippet and (res.snippet in para or para in res.snippet):
                        continue
                    p_lower = para.lower()
                    hits = sum(1 for term in query_terms if term in p_lower)
                    if hits > 0:
                        para_score = min(1.0, res.score * (0.8 + (0.2 * hits / max(1, len(query_terms)))))
                        scored_paragraphs.append((para_score, para))

                scored_paragraphs.sort(key=lambda x: x[0], reverse=True)

                for p_score, para_text in scored_paragraphs[:max_evidence_per_source]:
                    evidence_list.append(
                        EvidenceItem(
                            source_url=res.url,
                            source_title=res.title,
                            content=para_text,
                            relevance_score=round(p_score, 4),
                            retrieved_at=now,
                            domain=res.domain,
                        )
                    )

        # Sort all evidence by relevance score descending
        evidence_list.sort(key=lambda e: e.relevance_score, reverse=True)
        return evidence_list
