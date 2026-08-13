import pytest
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock
from fastapi.testclient import TestClient

from main import app
from db.session import init_db
from core.research.providers.base import SearchResultItem
from core.research.providers.tavily import TavilyProvider
from core.research.providers.brave import BraveProvider
from core.research.providers.router import SearchProviderRouter
from core.research.planner import ResearchPlanner
from core.research.source_manager import SourceManager, ProcessedSource
from core.research.evidence_store import EvidenceStore, ExtractedEvidence
from core.research.verifier import ResearchVerifier
from core.research.orchestrator import ResearchOrchestrator

@pytest.fixture(autouse=True)
def setup_test_db():
    async def _reset():
        await init_db()
        from db.session import engine
        from db.models import Base
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    asyncio.run(_reset())

@pytest.mark.asyncio
async def test_tavily_provider_mocked():
    provider = TavilyProvider(api_key="test_tavily_key")
    mock_resp = MagicMock()
    mock_resp.json.return_value = {
        "results": [
            {"title": "Tavily Result", "url": "https://tavily.com/doc", "snippet": "Tavily content", "score": 0.95}
        ]
    }
    mock_resp.raise_for_status = MagicMock()

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_resp
        results = await provider.search("python async", max_results=1)

        assert len(results) == 1
        assert results[0].title == "Tavily Result"
        assert results[0].provider_name == "tavily"

@pytest.mark.asyncio
async def test_brave_provider_mocked():
    provider = BraveProvider(api_key="test_brave_key")
    mock_resp = MagicMock()
    mock_resp.json.return_value = {
        "web": {
            "results": [
                {"title": "Brave Result", "url": "https://brave.com/search", "description": "Brave content"}
            ]
        }
    }
    mock_resp.raise_for_status = MagicMock()

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_resp
        results = await provider.search("rust async", max_results=1)

        assert len(results) == 1
        assert results[0].title == "Brave Result"
        assert results[0].provider_name == "brave"

@pytest.mark.asyncio
async def test_provider_router_fallback():
    mock_tavily = MagicMock()
    mock_tavily.name = "tavily"
    mock_tavily.search = AsyncMock(side_effect=Exception("Tavily API error"))

    mock_brave = MagicMock()
    mock_brave.name = "brave"
    mock_brave.search = AsyncMock(return_value=[
        SearchResultItem(title="Brave Fallback", url="https://brave.com", snippet="Fallback text", score=0.8, provider_name="brave")
    ])

    router = SearchProviderRouter(tavily=mock_tavily, brave=mock_brave)
    results, provider_used = await router.search("test fallback")

    assert provider_used == "brave"
    assert len(results) == 1
    assert results[0].title == "Brave Fallback"

@pytest.mark.asyncio
async def test_source_manager_deduplication():
    router = MagicMock()
    sm = SourceManager(search_router=router)

    item1 = SearchResultItem(title="Page 1", url="https://example.com/page?ref=1", snippet="Snippet 1", provider_name="tavily")
    item2 = SearchResultItem(title="Page 1 Dup", url="https://example.com/page#section", snippet="Snippet 2", provider_name="tavily")

    deduped = sm.filter_and_deduplicate([item1, item2])
    assert len(deduped) == 1
    assert deduped[0].url == "https://example.com/page?ref=1"

@pytest.mark.asyncio
async def test_research_planner():
    planner = ResearchPlanner()
    plan = await planner.generate_plan("Analyze Next.js 14 Server Actions")

    assert plan.goal == "Analyze Next.js 14 Server Actions"
    assert len(plan.steps) >= 1
    assert len(plan.steps[0].queries) >= 1

@pytest.mark.asyncio
async def test_verifier_supported_and_unsupported_findings():
    verifier = ResearchVerifier()
    evidence = [
        ExtractedEvidence(
            claim="Next.js Server Actions execute on the server.",
            supporting_text="Server actions run exclusively on node server context.",
            source_url="https://nextjs.org/docs"
        )
    ]
    sources = [
        ProcessedSource(title="Next Docs", url="https://nextjs.org/docs", domain="nextjs.org", provider="tavily", content_excerpt="Server actions run on server")
    ]

    findings = [
        "Next.js Server Actions execute on the server.",
        "Quantum computing is built into Next.js 14."
    ]

    reports = await verifier.verify_findings(findings, evidence, sources)
    assert len(reports) == 2
    assert reports[0].supported is True
    assert reports[1].supported is False

def test_research_api_endpoints():
    client = TestClient(app)

    # 1. Start research session
    run_resp = client.post("/api/v1/research/run", json={"query": "Test API Research Session"})
    assert run_resp.status_code == 200
    data = run_resp.json()
    assert "id" in data
    assert data["status"] in ["idle", "planning", "researching", "completed"]
    session_id = data["id"]

    # 2. Get session details
    get_resp = client.get(f"/api/v1/research/{session_id}")
    assert get_resp.status_code == 200
    assert get_resp.json()["id"] == session_id

    # 3. Get session sources
    sources_resp = client.get(f"/api/v1/research/{session_id}/sources")
    assert sources_resp.status_code == 200
    assert isinstance(sources_resp.json(), list)

    # 4. Cancel session
    cancel_resp = client.post(f"/api/v1/research/{session_id}/cancel")
    assert cancel_resp.status_code == 200
    assert cancel_resp.json()["status"] == "cancelled"
