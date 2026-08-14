import asyncio
import json
from core.llm import LLMProviderGateway, GroqProvider
from core.planner import AgentPlanner, TaskPlan
from core.tools.registry import tool_registry
from core.browser.tools import global_browser_toolset, BrowserOpenInput, BrowserExtractInput, BrowserCloseInput

async def main():
    print("==================================================")
    print("🚀 BATCH 1 REAL SMOKE TEST — GROQ + PLAYWRIGHT")
    print("==================================================")

    # 1. LLM GATEWAY + GROQ PLANNER VERIFICATION
    provider = LLMProviderGateway.get_provider()
    print(f"✅ Provider Detected: {type(provider).__name__}")
    print(f"✅ Target Model: {getattr(provider, 'model', 'N/A')}")
    
    planner = AgentPlanner(llm_provider=provider)
    user_goal = "Open the FastAPI documentation and find information about BackgroundTasks."
    print(f"\n📋 User Goal: '{user_goal}'")
    
    plan: TaskPlan = await planner.generate_plan(user_goal)
    print(f"✅ LLM Plan Generated via Groq ({len(plan.steps)} steps):")
    for idx, s in enumerate(plan.steps):
        print(f"   Step {idx+1}: [{s.tool}] {s.title} — {s.description}")

    # 2. REAL BROWSER EXECUTION VIA PLAYWRIGHT CHROMIUM
    print("\n🌐 Executing Real Playwright Browser Interaction...")
    target_url = "https://fastapi.tiangolo.com/tutorial/background-tasks/"
    
    open_res = await tool_registry.execute_tool("browser_open", {"url": target_url, "task_id": "smoke-test-1"})
    print(f"   browser_open status: {open_res.success}")
    assert open_res.success is True, f"Failed browser_open: {open_res.error}"
    page_id = open_res.data["page_id"]
    print(f"   Page ID: {page_id} | Page Title: '{open_res.data.get('title')}'")

    extract_res = await tool_registry.execute_tool("browser_extract", {"page_id": page_id})
    print(f"   browser_extract status: {extract_res.success}")
    assert extract_res.success is True, f"Failed browser_extract: {extract_res.error}"
    
    extracted_text = extract_res.data.get("text", "")
    print(f"   Extracted {len(extracted_text)} chars of untrusted page content.")
    assert "BackgroundTasks" in extracted_text or "background tasks" in extracted_text.lower(), "Expected BackgroundTasks keyword in page text"

    close_res = await tool_registry.execute_tool("browser_close", {"page_id": page_id, "session_id": "task-smoke-test-1"})
    print(f"   browser_close status: {close_res.success}")
    assert close_res.success is True

    print("\n==================================================")
    print("🎉 BATCH 1 SMOKE TEST PASSED SUCCESSFULLY!")
    print("==================================================")

if __name__ == "__main__":
    asyncio.run(main())
