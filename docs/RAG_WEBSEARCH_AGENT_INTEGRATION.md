# Cocoa Agent Integration: Project RAG + Live Web Research

## 1. Executive Summary
This document records the end-to-end integration of the Project RAG and Live Web Research systems into Cocoa's core autonomous agent execution lifecycle (`AgentOrchestrator`, `AgentPlanner`, `AgentExecutor`, and Desktop UI).

The agent now dynamically evaluates incoming user goals to route them into one of four context modes:
1. **`PROJECT_RAG`**: Local codebase questions (retrieves structural chunks from PostgreSQL + pgvector / SQLite vector fallback).
2. **`WEB_RESEARCH`**: Live external knowledge (queries locked search providers: Tavily primary $\rightarrow$ DuckDuckGo fallback).
3. **`BOTH`**: Tasks requiring local codebase context coupled with external documentation/standards.
4. **`NONE`**: Pure computations or direct tool actions requiring no contextual augmentation.

Strict workspace/project isolation is enforced at every layer, and full source provenance (chunk line numbers, symbols, relevance scores, domains, URLs, and publication dates) is stored in `task.plan_data` and displayed on the Cocoa Desktop UI.

---

## 2. Architecture & Pipeline

```
                                  [ User Goal Statement ]
                                             │
                                             ▼
                             ┌───────────────────────────────┐
                             │   ContextIntentRouter.route   │
                             └───────────────┬───────────────┘
                                             │
             ┌───────────────────────────────┼───────────────────────────────┐
             ▼                               ▼                               ▼
    [ PROJECT_RAG ]                   [ WEB_RESEARCH ]                   [ BOTH ]
  (Local repository)                 (External world)               (Project + Web)
             │                               │                               │
             ▼                               ▼                               ▼
┌─────────────────────────┐     ┌─────────────────────────┐     ┌─────────────────────────┐
│ ProjectContextBuilder   │     │  SearchProviderRouter   │     │  Combined Extraction    │
│  - pgvector/cosine      │     │  - Primary: Tavily      │     │  - RAG Code Chunks      │
│  - Symbol bonus         │     │  - Fallback: DuckDuckGo │     │  - Web Source Snippets  │
└────────────┬────────────┘     └────────────┬────────────┘     └────────────┬────────────┘
             │                               │                               │
             └───────────────────────────────┼───────────────────────────────┘
                                             ▼
                             ┌───────────────────────────────┐
                             │  UnifiedAgentContextBuilder   │
                             │  - Strict Source Provenance   │
                             │  - Token/Char Bounded Context │
                             └───────────────┬───────────────┘
                                             │
                                             ▼
                             ┌───────────────────────────────┐
                             │     Task.plan_data Storage    │
                             │  (Routing mode, counts, URLs) │
                             └───────────────┬───────────────┘
                                             │
                                             ▼
                             ┌───────────────────────────────┐
                             │         AgentPlanner          │
                             │   (Context-Informed DAG Plan) │
                             └───────────────┬───────────────┘
                                             │
                                             ▼
                             ┌───────────────────────────────┐
                             │         AgentExecutor         │
                             │   (Execute DAG + Verify)      │
                             └───────────────────────────────┘
```

---

## 3. Files Created & Modified

| File | Change | Description |
|---|---|---|
| `apps/agent/core/rag/intent_router.py` | **NEW** | `ContextIntentRouter` detecting `PROJECT_RAG`, `WEB_RESEARCH`, `BOTH`, `NONE` with heuristic rules + pattern matchers. |
| `apps/agent/core/rag/context_builder.py` | **MODIFIED** | Added `published_date` to `WebContextItem`, formatted publication metadata in unified prompt sections. |
| `apps/agent/core/planner.py` | **MODIFIED** | Updated `generate_plan(goal, project_id, context=...)` to accept `UnifiedAgentContext` and inject structured provenance sections into system prompts. Enhanced fallback planner. |
| `apps/agent/core/research/providers/router.py` | **MODIFIED** | Added `search_provider_router` module singleton. Enforced locked Tavily $\rightarrow$ DuckDuckGo routing. |
| `apps/agent/core/agent.py` | **MODIFIED** | Injected context routing into `AgentOrchestrator.run_goal()`. Retrieves RAG chunks and/or Web results, stores provenance in `task.plan_data`, and feeds context to planner. |
| `apps/desktop/src/lib/api/types.ts` | **MODIFIED** | Added `plan_data?: Record<string, any>` to `Task` interface. |
| `apps/desktop/src/views/Tasks.svelte` | **MODIFIED** | Added Context Routing Mode badges (`Project RAG`, `Web Research`, `Project + Web`, `Direct Execution`) and a "Context Pipeline & Provenance" card showing chunk/web counts, reasoning, and clickable sources. |
| `apps/agent/tests/test_agent_rag_web_integration.py` | **NEW** | 7 end-to-end integration tests verifying all routing scenarios, isolation, and orchestrator execution. |

---

## 4. Test Verification & Results

All 18 tests across the Project RAG and Web Research test suites pass with 100% success rate:

```bash
$ .venv/bin/python -m pytest tests/test_project_rag.py tests/test_web_research_v1.py tests/test_agent_rag_web_integration.py

tests/test_project_rag.py ......                                         [ 33%]
tests/test_web_research_v1.py .....                                      [ 61%]
tests/test_agent_rag_web_integration.py .......                          [100%]

======================= 18 passed, 74 warnings in 13.78s =======================
```

### Scenario Breakdown
1. **Scenario 1: Project-code question $\rightarrow$ RAG Only**
   - Goal: *"Where is the authenticate_user method defined in this codebase?"*
   - Outcome: `PROJECT_RAG` chosen, RAG retrieved, zero web calls.
2. **Scenario 2: Current/external question $\rightarrow$ Tavily Primary**
   - Goal: *"What are the latest breaking changes in React 19 released this year?"*
   - Outcome: `WEB_RESEARCH` chosen, Tavily called as primary, 0 DuckDuckGo calls.
3. **Scenario 3: Primary Provider Failure $\rightarrow$ DuckDuckGo Fallback**
   - Simulation: Tavily raises HTTP 429 rate limit error.
   - Outcome: Seamless fallback to DuckDuckGo, `provider_used="duckduckgo"`, zero fabricated mock items.
4. **Scenario 4: Project Context + External Web $\rightarrow$ Both**
   - Goal: *"How do our current project auth settings compare with the latest OAuth2 RFC standard?"*
   - Outcome: `BOTH` chosen, local codebase chunks and external RFC references merged into `UnifiedAgentContext`.
5. **Scenario 5: Simple computation / command $\rightarrow$ None**
   - Goal: *"Calculate the sum of 12 and 45 and echo the result"*
   - Outcome: `NONE` chosen, direct agent execution without wasteful retrieval overhead.
6. **Scenario 6: Strict Project Isolation**
   - Verified that chunks belonging to Project Alpha are completely invisible and unsearchable to queries issued for Project Beta.
7. **Scenario 7: Full AgentOrchestrator End-to-End Run & Provenance Survival**
   - Ran `orchestrator.run_goal()`. Verified `task.plan_data` holds `context_routing`, `rag_chunks_count`, `web_sources_count`, and the exact list of code symbols and web URLs.
