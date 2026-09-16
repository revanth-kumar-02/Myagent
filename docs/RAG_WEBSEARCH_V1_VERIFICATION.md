# Cocoa Agent — RAG + Web Research V1 Verification

## 1. Executive Summary
This document records the design, implementation, and verification of Cocoa's **Project RAG** and **Web Research** subsystems in accordance with the Phase V1 requirements. 

All core workflows have been tested and verified against real system components:
- Local file scanning, secret/binary filtering, and language-aware structural chunking.
- Incremental indexing with SHA-256 content hashing (skipping unchanged files, updating altered chunks, and pruning deleted files).
- PostgreSQL + pgvector vector storage with native distance operators when available and fallback compatibility.
- Strict project isolation ensuring Project A can never access Project B data.
- Deterministic hybrid retrieval combining semantic vectors, keyword/exact tokens, and symbol bonus.
- Bounded Context generation with deduplication.
- Locked Web Research hierarchy: **Tavily (PRIMARY) $\rightarrow$ DuckDuckGo (FALLBACK)** with real external web search and zero synthetic/mock search items.
- Unified Agent Context layer clearly preserving source provenance (`[PROJECT_CONTEXT]` vs. `[WEB_CONTEXT]`).
- Real backend RAG APIs mounted at `/rag/*` and `/api/v1/rag/*` without exposing raw embeddings.
- Frontend integration in Cocoa Desktop UI (`Projects.svelte` and `client.ts`).

---

## 2. Architecture & Data Flow

```
[Local Workspace Repository]
        │
        ▼ (Filtered: no .git, node_modules, secrets, binaries)
[Structural Chunker (AST & Regex)]
   ├── Python: Functions, Classes, Methods
   ├── JS/TS: Classes, Functions, Arrow Components, Interfaces
   ├── SQL: Table, Index, View, Function Statements
   ├── Markdown: Section Header Hierarchies
   └── HTML/CSS/JSON/YAML/Java/Kotlin/Dart
        │
        ▼ (SHA-256 Hashing)
[Incremental Indexer] ──── (Hash Match?) ────► Skip Unchanged Files
        │ (New / Modified Chunks)
        ▼
[Embedding Provider (384-dim)]
        │
        ▼
[PostgreSQL + pgvector / Fallback] (project_chunks, project_files)
        │
        ▼
[Hybrid Retriever (Project Scoped)]
   ├── Vector Similarity (pgvector `<=>` or Cosine)
   ├── Keyword & Exact Token Matching
   └── Symbol Match Bonus
        │
        ▼
[Bounded Context Builder] ──────────┐
                                     ├──► [Unified Agent Context] ──► [Cocoa Agent Planner]
[Locked Web Research Router] ────────┘    ├── [PROJECT_CONTEXT] (local://...)
   ├── 1. Tavily (Primary)                └── [WEB_CONTEXT] (https://...)
   └── 2. DuckDuckGo (Fallback)
```

---

## 3. Files Created & Modified

### Backend Core (`apps/agent/core/`)
| File | Action | Description |
|---|---|---|
| `core/rag/__init__.py` | **NEW** | Package initialization for Project RAG subsystem. |
| `core/rag/filter.py` | **NEW** | File filtering ignoring `.git`, `node_modules`, `.venv`, binaries, secrets, and large/generated bundles. |
| `core/rag/chunker.py` | **NEW** | Structural chunker supporting 12 languages (Python AST, JS/TS, Markdown, SQL, HTML, CSS, JSON, YAML, Java, Kotlin, Dart). |
| `core/rag/indexer.py` | **NEW** | Incremental indexer using SHA-256 content hashes, skip logic, chunk updates, and pruned file deletions. |
| `core/rag/retriever.py` | **NEW** | Hybrid retrieval engine combining vector distance, keyword matching, symbol bonus, and project isolation. |
| `core/rag/context_builder.py` | **NEW** | Bounded project context builder and unified agent context builder with source provenance preservation. |
| `core/planner.py` | **MODIFIED** | Injected real Project RAG bounded context into agent planner prompt. |
| `core/research/providers/duckduckgo.py` | **NEW** | Real DuckDuckGo web search provider using HTML form queries and Instant Answer API with organic links and ad filtering. |
| `core/research/providers/router.py` | **MODIFIED** | Locked provider order to Tavily (primary) $\rightarrow$ DuckDuckGo (fallback). Removed all synthetic/mock search items. |

### Backend API & Database (`apps/agent/api/` & `apps/agent/db/`)
| File | Action | Description |
|---|---|---|
| `db/models.py` | **MODIFIED** | Added `ProjectChunk` model, added `content_hash` to `ProjectFile`, and linked `Project.chunks` relationship. |
| `db/session.py` | **MODIFIED** | Added database migration columns for `content_hash` across PostgreSQL and SQLite fallback. |
| `api/rag.py` | **NEW** | Real endpoints for `/rag/index`, `/rag/status`, `/rag/search`, `/rag/context`, and `/rag/refresh`. Embeddings strictly omitted from responses. |
| `main.py` | **MODIFIED** | Registered and mounted `rag_router` at root and `/api/v1` prefixes. |

### Frontend UI (`apps/desktop/`)
| File | Action | Description |
|---|---|---|
| `src/lib/api/types.ts` | **MODIFIED** | Added TypeScript interfaces: `RagStatus`, `RagChunkResult`, `RagContextResponse`. |
| `src/lib/api/client.ts` | **MODIFIED** | Added client methods: `getRagStatus()`, `indexProjectRag()`, `refreshProjectRag()`, `searchRag()`, `getRagContext()`. |
| `src/views/Projects.svelte` | **MODIFIED** | Connected project context tab to real RAG data: indexing status badges, file/chunk counts, active vector backend, code search, and indexing buttons. |

### Test Suites (`apps/agent/tests/`)
| File | Action | Description |
|---|---|---|
| `tests/test_project_rag.py` | **NEW** | Complete RAG automated test suite (filtering, chunking, incremental hashing, isolation, context builder, APIs). |
| `tests/test_web_research_v1.py` | **NEW** | Complete Web Research test suite (locked hierarchy, real DDG search, fallback execution, zero mocks, unified context). |

---

## 4. Database & Schema Changes

### `project_chunks` Table
```sql
CREATE TABLE project_chunks (
    id VARCHAR(36) PRIMARY KEY,
    project_id VARCHAR(36) NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    file_path TEXT NOT NULL,
    language VARCHAR(50) NOT NULL,
    chunk_index INTEGER NOT NULL,
    symbol VARCHAR(255),
    content TEXT NOT NULL,
    content_hash VARCHAR(64) NOT NULL,
    file_hash VARCHAR(64),
    embedding JSON, -- or Vector(384) when pgvector extension is enabled
    created_at TIMESTAMP,
    updated_at TIMESTAMP
);
CREATE INDEX idx_project_chunks_project_id ON project_chunks(project_id);
```

### `project_files` Table Alteration
```sql
ALTER TABLE project_files ADD COLUMN content_hash VARCHAR(64);
```

---

## 5. RAG API Specifications

| Method | Path | Request Body / Query | Description |
|---|---|---|---|
| `POST` | `/rag/index` | `{"project_id": str, "workspace_path": Optional[str], "force_full": bool}` | Triggers incremental structural indexing for project. |
| `GET` | `/rag/status` | `?project_id=<id>` | Returns indexing status (`INDEXED` / `IDLE`), file count, chunk count, last indexed time, and active vector backend. |
| `POST` | `/rag/search` | `{"project_id": str, "query": str, "limit": 10, "language": Optional[str]}` | Returns ranked chunks with file, symbol, language, relevance, and content. Raw embeddings are never exposed. |
| `POST` | `/rag/context` | `{"project_id": str, "query": str, "max_chars": 12000, "max_chunks": 8}` | Generates bounded, deduplicated Markdown context formatted for model ingestion. |
| `POST` | `/rag/refresh` | `{"project_id": str}` | Performs incremental refresh skipping unchanged file hashes. |

---

## 6. Web Search Architecture & Provider Order

The search provider order is strictly locked:
1. **Primary Provider: Tavily**
   - Live endpoint: `https://api.tavily.com/search`
   - Configured via server environment `TAVILY_API_KEY`.
   - Returns real external search results with live documentation URLs.
2. **Fallback Provider: DuckDuckGo**
   - Live endpoint: `https://html.duckduckgo.com/html/` with fallback to `https://api.duckduckgo.com/`.
   - Activated automatically if Tavily key is missing, expired, rate-limited, or network error occurs.
   - Filters out promotional/ad URLs (`/y.js`, `ad_provider`) and unwraps organic redirects (`uddg=`).
3. **Synthetic/Mock Removal**
   - The router no longer generates fake documentation items. If both providers fail, the router returns empty results with error logging, preserving research integrity.

---

## 7. Automated Tests Executed & Results

### 1. `test_project_rag.py` (6/6 Passed)
```
tests/test_project_rag.py::test_rag_file_filtering PASSED                [ 16%]
tests/test_project_rag.py::test_structural_chunking_languages PASSED     [ 33%]
tests/test_project_rag.py::test_incremental_indexing_workflow PASSED     [ 50%]
tests/test_project_rag.py::test_strict_project_isolation PASSED          [ 66%]
tests/test_project_rag.py::test_bounded_context_builder_and_deduplication PASSED [ 83%]
tests/test_project_rag.py::test_rag_api_endpoints PASSED                 [100%]
======================== 6 passed in 3.20s ========================
```

### 2. `test_web_research_v1.py` (5/5 Passed)
```
tests/test_web_research_v1.py::test_locked_provider_hierarchy PASSED     [ 20%]
tests/test_web_research_v1.py::test_duckduckgo_provider_real_search PASSED [ 40%]
tests/test_web_research_v1.py::test_router_fallback_execution PASSED     [ 60%]
tests/test_web_research_v1.py::test_router_no_mock_results_on_failure PASSED [ 80%]
tests/test_web_research_v1.py::test_unified_agent_context_provenance PASSED [100%]
======================== 5 passed in 15.12s ========================
```

### 3. Database & Memory Regression Tests (`test_postgres_vector.py` — 7/7 Passed)
```
tests/test_postgres_vector.py::test_database_connection_and_backend_status PASSED [ 14%]
tests/test_postgres_vector.py::test_sqlalchemy_session_commit_and_rollback PASSED [ 28%]
tests/test_postgres_vector.py::test_embedding_provider_abstraction PASSED [ 42%]
tests/test_postgres_vector.py::test_semantic_search_and_hybrid_retrieval PASSED [ 57%]
tests/test_postgres_vector.py::test_strict_project_isolation PASSED      [ 71%]
tests/test_postgres_vector.py::test_memory_deduplication PASSED          [ 85%]
tests/test_postgres_vector.py::test_memory_persistence_after_restart PASSED [100%]
======================== 7 passed in 1.57s ========================
```

### 4. Desktop UI Production Build (`npm run build` — Passed)
```
✓ 125 modules transformed.
dist/index.html 0.62 kB
dist/assets/index-Do8MmgoB.css 87.57 kB
dist/assets/index-1OpXRtJb.js 172.26 kB
✓ built in 4.05s
```

---

## 8. Real End-to-End Flow Verification

Live execution verified the complete unified workflow:
1. **Workspace Ingestion**: Ingested TypeScript and SQL files into `project_chunks`.
2. **Incremental Indexing**: Immediate second run skipped 100% of unchanged files (`files_unchanged: 2`, `chunks_created: 0`).
3. **Project Retrieval**: Hybrid search for `loginUser` matched `auth.ts` symbol with 0.46 relevance.
4. **Web Research Primary**: Tavily query retrieved live FastAPI documentation (`https://betterstack.com/...`).
5. **Web Research Fallback**: Simulated Tavily failure triggered DuckDuckGo fallback, retrieving live Python `asyncio` documentation (`https://realpython.com/...`).
6. **Unified Agent Context**: Generated bounded context combining local project files (`[PROJECT_CONTEXT]`) and live web evidence (`[WEB_CONTEXT]`) with clear source provenance.

---

## 9. Limitations & Known TODOs
1. **Host PostgreSQL pgvector Package**: When host PostgreSQL lacks compiled `postgresql-18-pgvector`, the system seamlessly operates on SQLite/JSON vector fallback with cosine similarity. Users running full production PostgreSQL can install `postgresql-18-pgvector` to enable native database-side `<=>` distance indexing.
2. **Tree-Sitter Optional Acceleration**: Currently structural chunking uses Python's built-in `ast` and high-performance regex blocks. Tree-Sitter can be plugged in if native AST binaries are compiled on the host in a future iteration.
