import pytest
import os
import time
from pydantic import BaseModel

from core.llm import GroqProvider, LLMRateLimitError
from core.research.providers.tavily import TavilyProvider
from core.research.providers.brave import BraveProvider
from core.browser.session_manager import BrowserSessionManager
from core.filesystem.permission_manager import permission_manager, PermissionLevel
from config import settings

LIVE_TEST_GUARD = os.getenv("COCOA_LIVE_TESTS") == "true"
skip_unless_live = pytest.mark.skipif(not LIVE_TEST_GUARD, reason="COCOA_LIVE_TESTS environment variable is not 'true'")

class SampleSchema(BaseModel):
    summary: str
    status: str

@pytest.mark.asyncio
@skip_unless_live
async def test_live_groq_llm_execution():
    """Level 3 E2E: Real Groq LLM API request and Pydantic structured response validation."""
    api_key = os.getenv("LLM_API_KEY") or os.getenv("GROQ_API_KEY") or settings.LLM_API_KEY
    if not api_key or api_key.startswith("sk-placeholder") or api_key == "none":
        pytest.skip("LLM_API_KEY not configured for live Groq test.")

    provider = GroqProvider(api_key=api_key, model=settings.LLM_MODEL or "llama-3.3-70b-versatile")
    try:
        start = time.time()
        text_resp = await provider.generate_text("Respond with the single word: READY")
        latency = time.time() - start

        assert "READY" in text_resp.upper()
        print(f"\n[LIVE E2E] Groq Response: '{text_resp}' (Latency: {latency:.2f}s)")

        # Pydantic Structured Generation
        struct_resp = await provider.generate_structured(
            prompt="Analyze system state and return summary='All systems active', status='OK'",
            schema=SampleSchema
        )
        assert isinstance(struct_resp, SampleSchema)
        assert struct_resp.status == "OK"
        print(f"[LIVE E2E] Groq Structured Response: {struct_resp}")
    except LLMRateLimitError:
        pytest.skip("Groq API rate limit (429) hit during live test.")

@pytest.mark.asyncio
@skip_unless_live
async def test_live_tavily_search_execution():
    """Level 3 E2E: Real Tavily Search API request and source parsing."""
    api_key = os.getenv("TAVILY_API_KEY") or getattr(settings, "TAVILY_API_KEY", None)
    if not api_key or api_key.startswith("tvly-placeholder"):
        pytest.skip("TAVILY_API_KEY not configured for live search test.")

    provider = TavilyProvider(api_key=api_key)
    start = time.time()
    results = await provider.search("FastAPI python web framework", max_results=3)
    latency = time.time() - start

    assert len(results) > 0
    assert results[0].url.startswith("http")
    assert len(results[0].title) > 0
    print(f"\n[LIVE E2E] Tavily Search returned {len(results)} items (Latency: {latency:.2f}s)")
    for r in results:
        print(f"  - [{r.provider_name}] {r.title} ({r.url})")

@pytest.mark.asyncio
@skip_unless_live
async def test_live_brave_search_execution():
    """Level 3 E2E: Real Brave Search API request."""
    api_key = os.getenv("BRAVE_API_KEY")
    if not api_key or api_key == "none":
        pytest.skip("BRAVE_API_KEY not configured in environment.")

    provider = BraveProvider(api_key=api_key)
    results = await provider.search("PostgreSQL database", max_results=2)
    assert len(results) > 0
    print(f"\n[LIVE E2E] Brave Search returned {len(results)} items")

@pytest.mark.asyncio
@skip_unless_live
async def test_live_playwright_chromium_browser_operations():
    """Level 3 E2E: Real Playwright Chromium browser launch, navigation, permission gate, and text extraction."""
    # 1. Permission Gate Check
    has_perm = await permission_manager.check_permission(
        tool_name="browser_navigate",
        path="https://example.com",
        operation="navigate",
        permission_level=PermissionLevel.BROWSER_READ
    )
    assert has_perm is True

    session_mgr = BrowserSessionManager(headless=True)
    session = await session_mgr.get_or_create_session(session_id="live_test_session")
    page_id, page = await session_mgr.create_page(session)

    try:
        start = time.time()
        response = await page.goto("https://example.com")
        latency = time.time() - start

        assert response.status == 200
        title = await page.title()
        content = await page.text_content("body")

        assert "Example Domain" in title
        assert "Example Domain" in content
        print(f"\n[LIVE E2E] Playwright Chromium Navigated to 'https://example.com' (Title: '{title}', Latency: {latency:.2f}s)")

    finally:
        await session_mgr.close_session(session.session_id)
        await session_mgr.close_all()
