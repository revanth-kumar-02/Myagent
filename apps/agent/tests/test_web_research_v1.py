import pytest
from core.research.providers.base import WebSearchProvider, SearchResultItem
from core.research.providers.tavily import TavilyProvider
from core.research.providers.duckduckgo import DuckDuckGoProvider
from core.research.providers.router import SearchProviderRouter
from core.rag.context_builder import unified_agent_context_builder, BoundedProjectChunk

@pytest.fixture(scope="module")
def anyio_backend():
    return "asyncio"

@pytest.mark.asyncio
async def test_locked_provider_hierarchy():
    """Verify provider order is locked: Tavily = PRIMARY, DuckDuckGo = FALLBACK."""
    router = SearchProviderRouter()
    assert isinstance(router.primary, TavilyProvider)
    assert router.primary.name == "tavily"
    assert isinstance(router.fallback, DuckDuckGoProvider)
    assert router.fallback.name == "duckduckgo"

@pytest.mark.asyncio
async def test_duckduckgo_provider_real_search():
    """Verify DuckDuckGo fallback queries real web without mock results."""
    ddg = DuckDuckGoProvider()
    results = await ddg.search("python documentation official", max_results=3)
    assert len(results) >= 1
    first = results[0]
    assert first.provider_name == "duckduckgo"
    assert first.url.startswith("http")
    assert "/y.js" not in first.url  # Ad links filtered
    assert len(first.title) > 0
    assert first.score > 0.0

@pytest.mark.asyncio
async def test_router_fallback_execution():
    """Verify router automatically falls back to DuckDuckGo when Tavily fails."""
    # Create failing Tavily provider
    failing_tavily = TavilyProvider(api_key="invalid_test_key_xyz")
    router = SearchProviderRouter(tavily=failing_tavily)

    results, provider_used = await router.search("sqlite database documentation", max_results=2)
    assert provider_used == "duckduckgo"
    assert len(results) >= 1
    for r in results:
        assert r.provider_name == "duckduckgo"
        assert r.url.startswith("http")

@pytest.mark.asyncio
async def test_router_no_mock_results_on_failure():
    """Verify router does NOT return fake mock results if providers fail."""
    class AlwaysFailingProvider(WebSearchProvider):
        @property
        def name(self) -> str:
            return "failing"
        async def search(self, query: str, max_results: int = 5):
            raise RuntimeError("Network disconnected")
        async def extract(self, urls):
            return {}

    router = SearchProviderRouter(
        tavily=AlwaysFailingProvider(),
        duckduckgo=AlwaysFailingProvider()
    )
    results, provider_used = await router.search("any query", max_results=5)
    assert provider_used == "none"
    assert len(results) == 0  # Absolutely NO mock/fake search items

@pytest.mark.asyncio
async def test_unified_agent_context_provenance():
    """Verify unified context clearly separates and labels PROJECT_CONTEXT and WEB_CONTEXT."""
    web_sources = [
        {
            "title": "Python 3.12 Release Notes",
            "url": "https://docs.python.org/3/whatsnew/3.12.html",
            "domain": "docs.python.org",
            "relevance": 0.88,
            "content_excerpt": "Python 3.12 includes sub-interpreters and improved error messages."
        }
    ]

    unified = await unified_agent_context_builder.build_unified_context(
        query="python 3.12 features",
        project_id=None,
        web_sources=web_sources
    )

    assert "==== WEB RESEARCH CONTEXT (LIVE EXTERNAL SOURCES) ====" in unified.formatted_prompt_context
    assert "https://docs.python.org/3/whatsnew/3.12.html" in unified.formatted_prompt_context
    assert len(unified.web_items) == 1
    assert unified.web_items[0].relevance == 0.88
