# KORA — RAG V4: AGENT CONTEXT SPECIFICATION

## Overview

Kora RAG V4 integrates the retrieval subsystems (RAG V1–V3) directly into the **Agent Core**. It provides intelligent context need resolution, multi-source bounded assembly, strict deterministic budgeting, and grounded response formatting while preserving complete provenance and strict project isolation.

---

## 1. Architecture & Pipeline Flow

```
User Message
    │
    ▼
ContextResolver.resolve(message, project_id)
    │
    ├── Determines Source Needs:
    │     ├── Project RAG (local files, code, docs, sheets, slides)
    │     ├── Memory (user preferences, persistent facts)
    │     ├── Web Research (real-time data, external web)
    │     └── None (conversational / trivial math)
    │
    ▼
Planner.plan(request, context)
    │
    ├── Generates PlanSteps:
    │     ├── Step 1 [RAG_QUERY] (if RAG needed)
    │     ├── Step 2 [WEB_RESEARCH] (if Web needed)
    │     └── Step 3 [MODEL_GENERATE] (grounded response)
    │
    ▼
ContextPackageBuilder.assemble(rag_chunks, memories, web_results)
    │
    ├── Enforces Deterministic Budgets:
    │     ├── max_rag_chunks: 8 (max 3072 tokens)
    │     ├── max_memory_items: 4 (max 512 tokens)
    │     ├── max_web_sources: 4 (max 1024 tokens)
    │     └── max_total_tokens: 6144 tokens
    │
    ▼
ContextManager.build(package)
    │
    ├── Injects Grounding Directives & Demarcated Sections
    ├── Truncates History (oldest-first)
    └── Produces Bounded ContextWindow
           │
           ▼
     ChatResponse (full_text + sources + web_sources)
```

---

## 2. Core Components

### 2.1 Context Resolver (`core/context_resolver.py`)
- **`ContextResolver`**: Analyzes the semantic intent of user requests:
  - **Project/Local**: Keywords and patterns matching codebase symbols, filenames, sheets, slides, pages, and architectural queries $\rightarrow$ `SourceType.RAG`.
  - **Memory/Preferences**: Phrases referring to personal preferences, remembered settings, and user facts $\rightarrow$ `SourceType.MEMORY`.
  - **Web Research**: Queries requesting real-time information, online docs, news, or URLs $\rightarrow$ `SourceType.WEB`.
  - **Mixed Queries**: Questions combining local project context with external best practices $\rightarrow$ `RAG + WEB`.
  - **Conversational**: Greetings, conversational remarks, or simple calculations $\rightarrow$ `set()` (Zero unnecessary retrieval).

### 2.2 Multi-Source Context Package Builder (`core/context_package.py`)
- **`ContextPackageBuilder`**: Assembles heterogeneous context sources into a unified `AgentContextPackage`:
  - Enforces deterministic token and item counts per source type.
  - Generates clear, demarcated prompt sections:
    - `=== [RAG] Verified Project Knowledge (High Confidence) ===`
    - `=== [MEMORY] User Preferences & Persistent Context ===`
    - `=== [WEB] External Web Research (Unverified / Live Data) ===`
  - Populates structured `Source` and `WebSource` citation lists.

### 2.3 Grounded Context Manager (`core/context.py`)
- **`ContextManager`**:
  - Manages active conversation history in Redis.
  - Injects strict grounding directives to instruct the reasoning model to distinguish verified project facts from external or unverified sources.
  - Dynamically calculates remaining token budget and truncates oldest history turns first.

### 2.4 Context-Aware Planner (`core/planner.py`)
- Produces targeted execution plans:
  - Generates `ActionType.RAG_QUERY` for project requests.
  - Generates `ActionType.WEB_RESEARCH` for external requests.
  - Generates single `ActionType.MODEL_GENERATE` for direct/simple questions.

---

## 3. Grounding & Provenance Guarantees

1. **Source Distinction**: The agent receives distinct section headers separating verified local knowledge from external web snippets.
2. **Provenance Survival**: Every RAG chunk preserves `file_path`, `start_line`, `end_line`, `symbol`, `page`, `sheet`, `slide`, and relevance `score` from retrieval through to `ChatResponse.sources`.
3. **No Hallucination**: Grounding directives explicitly forbid fabricating project facts when context is missing.
4. **Project Isolation**: Every query remains strictly scoped to `project_id`.
