"""
research — Kora Web Research Subsystem (V6 DuckDuckGo)
"""

from research.dedup import ResearchDeduplicator
from research.engine import WebResearchEngine
from research.evidence import EvidenceExtractor
from research.fetcher import PageFetcher
from research.normalizer import ResultNormalizer, clean_text, compute_text_hash, extract_domain, sanitize_url
from research.planner import ResearchPlanner
from research.providers.duckduckgo import DuckDuckGoProvider
from research.ranker import RelevanceRanker
from research.router import ResearchRouter
from research.source_manager import SourceManager
from research.types import (
    EvidenceItem,
    ResearchContext,
    ResearchDepth,
    ResearchPlan,
    ResearchResponse,
    WebResult,
    WebSource,
)

__all__ = [
    "WebResearchEngine",
    "ResearchRouter",
    "DuckDuckGoProvider",
    "ResearchPlanner",
    "PageFetcher",
    "ResultNormalizer",
    "ResearchDeduplicator",
    "RelevanceRanker",
    "EvidenceExtractor",
    "SourceManager",
    "ResearchDepth",
    "ResearchPlan",
    "WebResult",
    "WebSource",
    "EvidenceItem",
    "ResearchContext",
    "ResearchResponse",
    "sanitize_url",
    "extract_domain",
    "clean_text",
    "compute_text_hash",
]
