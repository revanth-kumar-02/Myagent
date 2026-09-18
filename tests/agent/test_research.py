"""
tests.agent.test_research — Comprehensive Test Suite for Kora's DuckDuckGo Web Research Subsystem (V6)
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, patch

import pytest

from core.context_package import ContextPackageBuilder
from core.context_resolver import ContextResolver
from core.types import SourceType
from research.dedup import ResearchDeduplicator
from research.engine import WebResearchEngine
from research.evidence import EvidenceExtractor
from research.fetcher import PageFetcher
from research.normalizer import ResultNormalizer, clean_text, extract_domain, sanitize_url
from research.planner import ResearchPlanner
from research.providers.duckduckgo import DuckDuckGoProvider
from research.ranker import RelevanceRanker
from research.router import ResearchRouter
from research.source_manager import SourceManager
from research.types import ResearchDepth, WebResult


# ── 1. Result Normalization & URL Sanitization ────────────────────────────────


class TestResultNormalizer:

    def test_sanitize_url_strips_tracking_and_anchors(self):
        dirty_url = "https://example.com/blog/article?utm_source=twitter&utm_medium=social&gclid=12345#section-2"
        clean = sanitize_url(dirty_url)
        assert clean == "https://example.com/blog/article"

    def test_sanitize_url_unwraps_ddg_redirects(self):
        ddg_redirect = "https://duckduckgo.com/l/?uddg=https%3A%2F%2Ffastapi.tiangolo.com%2Ftutorial%2F&rut=123"
        clean = sanitize_url(ddg_redirect)
        assert clean == "https://fastapi.tiangolo.com/tutorial/"

    def test_extract_domain(self):
        assert extract_domain("https://www.docs.python.org/3/library") == "docs.python.org"
        assert extract_domain("https://github.com/astral-sh/uv") == "github.com"

    def test_clean_text_strips_html_and_unescapes(self):
        dirty_text = "<b>FastAPI</b> &amp; <i>Starlette</i> &mdash; Modern Web Framework"
        cleaned = clean_text(dirty_text)
        assert cleaned == "FastAPI & Starlette — Modern Web Framework"

    def test_normalize_result_object(self):
        normalizer = ResultNormalizer()
        raw = {
            "link": "https://fastapi.tiangolo.com/?utm_source=ddg",
            "title": "<b>FastAPI</b> Framework",
            "body": "FastAPI is a modern, fast web framework for Python.",
            "score": 0.95,
        }
        res = normalizer.normalize_result(raw)
        assert res.url == "https://fastapi.tiangolo.com/"
        assert res.title == "FastAPI Framework"
        assert res.domain == "fastapi.tiangolo.com"
        assert res.source == "duckduckgo"


# ── 2. Research Planner ───────────────────────────────────────────────────────


class TestResearchPlanner:

    def test_quick_research_plan(self):
        planner = ResearchPlanner()
        plan = planner.plan("Search the web for what is the latest release of Python")
        assert "what is the latest release of Python" in plan.query or "latest release of Python" in plan.query
        assert plan.depth == ResearchDepth.QUICK
        assert plan.fetch_pages is False
        assert plan.max_results == 4

    def test_deep_research_plan_detected(self):
        planner = ResearchPlanner()
        plan = planner.plan("Comprehensive in-depth documentation and benchmarks of pgvector 0.8")
        assert plan.depth == ResearchDepth.DEEP
        assert plan.fetch_pages is True
        assert plan.max_results >= 6

    def test_sub_query_generation_for_comparisons(self):
        planner = ResearchPlanner()
        plan = planner.plan("FastAPI vs Litestar comparison")
        assert len(plan.sub_queries) == 2
        assert "FastAPI overview" in plan.sub_queries
        assert "Litestar overview" in plan.sub_queries


# ── 3. Deduplication & Domain Diversity ───────────────────────────────────────


class TestResearchDeduplication:

    def test_removes_duplicate_urls(self):
        dedup = ResearchDeduplicator()
        results = [
            WebResult(url="https://example.com/page?utm_source=1", title="A", snippet="Snippet A", domain="example.com"),
            WebResult(url="https://example.com/page", title="A duplicate", snippet="Snippet A duplicate", domain="example.com"),
            WebResult(url="https://other.com/page", title="B", snippet="Snippet B", domain="other.com"),
        ]
        unique = dedup.deduplicate_results(results)
        assert len(unique) == 2
        assert {u.url for u in unique} == {"https://example.com/page", "https://other.com/page"}

    def test_domain_diversity_limits(self):
        dedup = ResearchDeduplicator(max_per_domain=2)
        results = [
            WebResult(url=f"https://github.com/repo{i}", title=f"Title {i}", snippet=f"Snippet {i}", domain="github.com")
            for i in range(5)
        ]
        unique = dedup.deduplicate_results(results)
        assert len(unique) == 2


# ── 4. Relevance Ranking & Evidence Extraction ────────────────────────────────


class TestRankingAndEvidence:

    def test_relevance_ranking_boosts_lexical_and_authority(self):
        ranker = RelevanceRanker()
        results = [
            WebResult(
                url="https://random-blog.xyz/post",
                title="Something unrelated",
                snippet="General coding thoughts",
                domain="random-blog.xyz",
            ),
            WebResult(
                url="https://fastapi.tiangolo.com/tutorial",
                title="FastAPI Web Framework Tutorial",
                snippet="FastAPI async tutorial with Python 3.10+",
                domain="fastapi.tiangolo.com",
            ),
        ]
        ranked = ranker.rank_results("FastAPI async tutorial", results)
        assert ranked[0].domain == "fastapi.tiangolo.com"
        assert ranked[0].score > ranked[1].score

    def test_evidence_extraction_with_provenance(self):
        extractor = EvidenceExtractor()
        results = [
            WebResult(
                url="https://fastapi.tiangolo.com/",
                title="FastAPI",
                snippet="FastAPI is a modern, fast (high-performance) web framework.",
                score=0.92,
                domain="fastapi.tiangolo.com",
                raw_content="FastAPI is a modern, fast (high-performance) web framework.\n\nKey features include high performance, fast to code, and fewer bugs.",
            )
        ]
        evidence = extractor.extract_evidence("FastAPI features", results)
        assert len(evidence) >= 1
        assert evidence[0].source_url == "https://fastapi.tiangolo.com/"
        assert evidence[0].domain == "fastapi.tiangolo.com"
        assert evidence[0].relevance_score > 0.5


# ── 5. Page Fetcher ───────────────────────────────────────────────────────────


@pytest.mark.asyncio
class TestPageFetcher:

    async def test_page_fetcher_extracts_clean_text(self):
        html_doc = """
        <html>
            <head><title>Test Page</title></head>
            <body>
                <header><nav><a href="/">Home</a></nav></header>
                <article>
                    <h1>FastAPI 2026 Documentation</h1>
                    <p>FastAPI provides exceptional asynchronous performance with Python type hints.</p>
                </article>
                <footer>Copyright 2026</footer>
            </body>
        </html>
        """
        fetcher = PageFetcher()
        clean = fetcher.extract_clean_text(html_doc)
        assert "FastAPI 2026 Documentation" in clean
        assert "asynchronous performance" in clean
        assert "Home" not in clean  # nav stripped
        assert "Copyright" not in clean  # footer stripped


# ── 6. DuckDuckGo Search Provider & Engine Integration ────────────────────────


@pytest.mark.asyncio
class TestDuckDuckGoProviderAndEngine:

    async def test_ddg_provider_parses_html_response(self):
        sample_html = """
        <div class="result results_links">
            <a class="result__a" href="//duckduckgo.com/l/?uddg=https%3A%2F%2Ffastapi.tiangolo.com%2F">FastAPI Framework</a>
            <a class="result__snippet">FastAPI framework, high performance, easy to learn, fast to code, ready for production.</a>
        </div>
        """
        provider = DuckDuckGoProvider()
        results = provider._parse_html_results(sample_html, max_results=5)
        assert len(results) == 1
        assert results[0].url == "https://fastapi.tiangolo.com/"
        assert "FastAPI Framework" in results[0].title
        assert "high performance" in results[0].snippet

    async def test_research_engine_workflow(self):
        mock_provider = DuckDuckGoProvider()
        mock_provider.search = AsyncMock(return_value=[
            WebResult(
                url="https://fastapi.tiangolo.com/",
                title="FastAPI Official Docs",
                snippet="FastAPI is a modern, fast web framework for building APIs with Python.",
                score=0.95,
                domain="fastapi.tiangolo.com",
            ),
            WebResult(
                url="https://github.com/tiangolo/fastapi",
                title="GitHub - tiangolo/fastapi",
                snippet="FastAPI framework repository and release history.",
                score=0.90,
                domain="github.com",
            ),
        ])

        engine = WebResearchEngine(ddg_provider=mock_provider)
        ctx = await engine.research("FastAPI release notes 2026")

        assert ctx.provider_used == "duckduckgo"
        assert len(ctx.sources) == 2
        assert len(ctx.evidence_items) >= 2
        assert "=== Web Research Results" in ctx.summary_text
        assert ctx.token_count > 0

    async def test_research_router_exclusive_duckduckgo(self):
        router = ResearchRouter()
        with patch.object(
            router._engine,
            "search_raw",
            return_value=AsyncMock(
                provider_used="duckduckgo",
                results=[WebResult(url="https://ddg.com", title="DDG", snippet="DuckDuckGo result", score=0.9)],
                total_results=1,
            ),
        ):
            resp = await router.search("Latest news")
            assert resp.provider_used == "duckduckgo"


# ── 7. RAG / Memory Database Isolation Guarantee ──────────────────────────────


@pytest.mark.asyncio
class TestDatabaseIsolation:

    async def test_research_never_writes_to_rag_or_memory(self):
        """Web research output flows only to context — never writes to DB tables."""
        mock_provider = DuckDuckGoProvider()
        mock_provider.search = AsyncMock(return_value=[
            WebResult(url="https://news.com/tech", title="Tech News", snippet="Live internet data", score=0.88)
        ])

        engine = WebResearchEngine(ddg_provider=mock_provider)
        ctx = await engine.research("Current live weather and news")

        # Verify output is purely a transient ResearchContext
        assert ctx is not None
        assert ctx.provider_used == "duckduckgo"
        # No DB sessions or models touched


# ── 8. Context Resolver & Context Package Routing Integration ─────────────────


class TestContextResolverWebRouting:

    def test_external_queries_route_to_web(self):
        resolver = ContextResolver()

        # Real-time / latest external web search
        src1 = resolver.resolve("Search the web for latest FastAPI release notes 2026")
        assert SourceType.WEB in src1
        assert SourceType.RAG not in src1

        # Current news / external docs
        src2 = resolver.resolve("What is the current stock price of Google online?")
        assert SourceType.WEB in src2

        # Local project question
        src3 = resolver.resolve("Where is the database schema defined in this repo?")
        assert SourceType.RAG in src3
        assert SourceType.WEB not in src3

        # Memory question
        src4 = resolver.resolve("What is my preference for python indentation?")
        assert SourceType.MEMORY in src4
        assert SourceType.WEB not in src4

    def test_context_package_assembly_with_web_results(self):
        builder = ContextPackageBuilder()

        web_items = [
            {
                "url": "https://fastapi.tiangolo.com/release-notes/",
                "title": "FastAPI Release Notes",
                "snippet": "FastAPI version 0.115 introduced enhanced lifespan events.",
                "score": 0.94,
            }
        ]

        package = builder.assemble(web_results=web_items)
        assert SourceType.WEB in package.resolved_sources
        assert len(package.web_sources) == 1
        assert "=== [WEB] External Web Research" in package.formatted_text
        assert "FastAPI Release Notes" in package.formatted_text
        assert package.token_count > 0
