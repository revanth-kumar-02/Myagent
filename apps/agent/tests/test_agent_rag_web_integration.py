import pytest
import uuid
import os
from unittest.mock import AsyncMock, patch, MagicMock

from core.rag.intent_router import ContextIntentRouter, ContextRoutingMode, ContextRoutingDecision
from core.rag.context_builder import (
    UnifiedAgentContextBuilder,
    ProjectRagContextBuilder,
    BoundedProjectChunk,
    WebContextItem,
    ProjectContextResult,
    UnifiedAgentContext
)
import hashlib
from core.research.providers.base import WebSearchProvider, SearchResultItem
from core.research.providers.router import SearchProviderRouter
from core.planner import AgentPlanner, TaskPlan, PlanStepSchema
from core.agent import AgentOrchestrator
from db.models import Task, Project, ProjectChunk, ProjectFile
from db.session import AsyncSessionLocal

class MockTavilyProvider(WebSearchProvider):
    def __init__(self, should_fail: bool = False):
        self.should_fail = should_fail
        self.call_count = 0

    @property
    def name(self) -> str:
        return "tavily"

    async def search(self, query: str, max_results: int = 5):
        self.call_count += 1
        if self.should_fail:
            raise RuntimeError("Tavily API 429 Rate Limit Exceeded")
        return [
            SearchResultItem(
                title="Tavily Python 3.14 Release Notes",
                url="https://python.org/news/3.14",
                snippet="Python 3.14 introduces new features including enhanced JIT compiler.",
                score=0.95,
                provider_name="tavily",
                metadata={"domain": "python.org"}
            )
        ]

    async def extract(self, urls):
        return {}

class MockDuckDuckGoProvider(WebSearchProvider):
    def __init__(self, should_fail: bool = False):
        self.should_fail = should_fail
        self.call_count = 0

    @property
    def name(self) -> str:
        return "duckduckgo"

    async def search(self, query: str, max_results: int = 5):
        self.call_count += 1
        if self.should_fail:
            raise RuntimeError("DuckDuckGo Network Failure")
        return [
            SearchResultItem(
                title="DuckDuckGo Python 3.14 Documentation",
                url="https://docs.python.org/3.14/",
                snippet="Official documentation for Python 3.14 release.",
                score=0.91,
                provider_name="duckduckgo",
                metadata={"domain": "docs.python.org"}
            )
        ]

    async def extract(self, urls):
        return {}

@pytest.mark.asyncio
async def test_scenario_1_project_rag_only():
    """Scenario 1: Project-code question -> routes to PROJECT_RAG only."""
    router = ContextIntentRouter()
    goal = "Where is the authenticate_user method defined in this codebase?"
    project_id = "proj_test_1"

    decision = await router.route(goal, project_id=project_id)
    assert decision.mode == ContextRoutingMode.PROJECT_RAG
    assert decision.needs_rag is True
    assert decision.needs_web is False

@pytest.mark.asyncio
async def test_scenario_2_web_research_tavily_primary():
    """Scenario 2: Current external question -> routes to WEB_RESEARCH, Tavily primary succeeds."""
    router = ContextIntentRouter()
    goal = "What are the latest breaking changes in React 19 released this year?"
    
    decision = await router.route(goal, project_id=None)
    assert decision.mode == ContextRoutingMode.WEB_RESEARCH
    assert decision.needs_rag is False
    assert decision.needs_web is True

    tavily = MockTavilyProvider(should_fail=False)
    ddg = MockDuckDuckGoProvider(should_fail=False)
    search_router = SearchProviderRouter(tavily=tavily, duckduckgo=ddg)

    results, provider_used = await search_router.search(goal)
    assert provider_used == "tavily"
    assert len(results) == 1
    assert tavily.call_count == 1
    assert ddg.call_count == 0

@pytest.mark.asyncio
async def test_scenario_3_web_research_duckduckgo_fallback():
    """Scenario 3: Force Tavily failure -> fallback strictly to DuckDuckGo."""
    tavily = MockTavilyProvider(should_fail=True)
    ddg = MockDuckDuckGoProvider(should_fail=False)
    search_router = SearchProviderRouter(tavily=tavily, duckduckgo=ddg)

    query = "latest fastAPI updates"
    results, provider_used = await search_router.search(query)

    assert provider_used == "duckduckgo"
    assert len(results) == 1
    assert tavily.call_count == 1
    assert ddg.call_count == 1
    assert "DuckDuckGo" in results[0].title

@pytest.mark.asyncio
async def test_scenario_4_both_rag_and_web():
    """Scenario 4: Question requiring project context + live external info -> routes to BOTH."""
    router = ContextIntentRouter()
    goal = "How do our current project auth settings compare with the latest OAuth2 RFC standard?"
    project_id = "proj_test_4"

    decision = await router.route(goal, project_id=project_id)
    assert decision.mode == ContextRoutingMode.BOTH
    assert decision.needs_rag is True
    assert decision.needs_web is True

@pytest.mark.asyncio
async def test_scenario_5_none_simple_task():
    """Scenario 5: Simple local task / computation -> routes to NONE."""
    router = ContextIntentRouter()
    goal = "Calculate the sum of 12 and 45 and echo the result"

    decision = await router.route(goal, project_id=None)
    assert decision.mode == ContextRoutingMode.NONE
    assert decision.needs_rag is False
    assert decision.needs_web is False

@pytest.mark.asyncio
async def test_scenario_6_strict_project_isolation():
    """Scenario 6: Enforce project isolation. Project A chunks must never appear in Project B search."""
    from core.rag.retriever import ProjectRagRetriever

    retriever = ProjectRagRetriever()
    proj_a_id = f"proj_iso_a_{uuid.uuid4().hex[:6]}"
    proj_b_id = f"proj_iso_b_{uuid.uuid4().hex[:6]}"

    async with AsyncSessionLocal() as db:
        pa = Project(id=proj_a_id, title="Project Alpha")
        pb = Project(id=proj_b_id, title="Project Beta")
        db.add_all([pa, pb])

        content_a = "def get_alpha_private_key(): return 'ALPHA_12345'"
        chunk_a = ProjectChunk(
            id=str(uuid.uuid4()),
            project_id=proj_a_id,
            file_path="src/secret_service.py",
            chunk_index=0,
            content=content_a,
            content_hash=hashlib.sha256(content_a.encode()).hexdigest(),
            language="python",
            symbol="get_alpha_private_key"
        )
        # Add chunk only to Project B
        content_b = "def get_beta_private_key(): return 'BETA_98765'"
        chunk_b = ProjectChunk(
            id=str(uuid.uuid4()),
            project_id=proj_b_id,
            file_path="src/beta_service.py",
            chunk_index=0,
            content=content_b,
            content_hash=hashlib.sha256(content_b.encode()).hexdigest(),
            language="python",
            symbol="get_beta_private_key"
        )
        db.add_all([chunk_a, chunk_b])
        await db.commit()

    # Search in Project A for private key
    results_a = await retriever.search("private key", project_id=proj_a_id, limit=5)
    for r in results_a:
        assert r.project_id == proj_a_id
        assert "ALPHA" in r.content
        assert "BETA" not in r.content

    # Search in Project B for private key
    results_b = await retriever.search("private key", project_id=proj_b_id, limit=5)
    for r in results_b:
        assert r.project_id == proj_b_id
        assert "BETA" in r.content
        assert "ALPHA" not in r.content

@pytest.mark.asyncio
async def test_scenario_7_orchestrator_end_to_end_provenance():
    """Scenario 7: Full AgentOrchestrator run_goal verifies routing, context merging, and provenance in task.plan_data."""
    # Setup mock components
    mock_tavily = MockTavilyProvider(should_fail=False)
    mock_ddg = MockDuckDuckGoProvider(should_fail=False)
    mock_search = SearchProviderRouter(tavily=mock_tavily, duckduckgo=mock_ddg)

    # Setup orchestrator with deterministic mocks
    orchestrator = AgentOrchestrator(
        search_router=mock_search
    )

    # Create dummy project
    test_proj_id = f"proj_provenance_{uuid.uuid4().hex[:6]}"
    async with AsyncSessionLocal() as db:
        p = Project(id=test_proj_id, title="Provenance Project")
        db.add(p)
        content_auth = "class AuthHandler:\n    def verify(self, token): return True"
        c = ProjectChunk(
            id=str(uuid.uuid4()),
            project_id=test_proj_id,
            file_path="core/auth_handler.py",
            chunk_index=0,
            content=content_auth,
            content_hash=hashlib.sha256(content_auth.encode()).hexdigest(),
            language="python",
            symbol="AuthHandler"
        )
        db.add(c)
        await db.commit()

    goal = "Review our project AuthHandler implementation and check latest OAuth2 best practices"
    task = await orchestrator.run_goal(goal, project_id=test_proj_id)

    assert task is not None
    assert task.plan_data is not None
    assert task.plan_data["context_routing"] == ContextRoutingMode.BOTH.value
    assert task.plan_data["needs_rag"] is True
    assert task.plan_data["needs_web"] is True
    assert task.plan_data["rag_chunks_count"] > 0
    assert task.plan_data["web_sources_count"] > 0

    sources = task.plan_data["sources"]
    assert any(s.get("type") == "project" and "core/auth_handler.py" in s.get("path", "") for s in sources)
    assert any(s.get("type") == "web" and ("tavily" in s.get("title", "").lower() or "python" in s.get("title", "").lower()) for s in sources)
