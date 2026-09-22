# KORA — V6: DUCKDUCKGO WEB RESEARCH SPECIFICATION

**Status**: Implemented & Verified  
**Version**: 1.0  
**Provider**: DuckDuckGo (Exclusive)

---

## 1. Overview & Architecture

Kora's Web Research subsystem provides real-time external information retrieval for questions regarding current events, live documentation, external APIs, and topics not present in the local codebase or long-term memory.

```mermaid
flowchart TD
    UserRequest[User Request] --> Planner[Research Planner]
    Planner -->|Queries & Depth| DDG[DuckDuckGo Provider (HTML/Lite Endpoints)]
    DDG --> Normalizer[Result Normalizer & URL Sanitizer]
    Normalizer --> Fetcher[Source Page Fetcher (Deep Mode)]
    Fetcher --> Dedup[Research Deduplicator (URL + Domain + Content)]
    Dedup --> Ranker[Relevance Ranker (Lexical + Authority + Position)]
    Ranker --> Evidence[Evidence Extractor]
    Evidence --> SourceMgr[Source Manager]
    Evidence --> ResCtx[Bounded Research Context]
    ResCtx --> CtxResolver[Context Resolver]
    CtxResolver --> Agent[Agent Core & Context Package]
```

---

## 2. Core Architectural Guarantees

1. **DuckDuckGo Exclusivity**: DuckDuckGo is the sole web search provider. No Tavily, no external third-party search APIs, and zero hardcoded fallback providers.
2. **Strict RAG/Memory DB Isolation**: Web search results and fetched page contents are transient in-memory context artifacts. They are **never written** to PostgreSQL `chunks` (RAG) or `agent_memory` tables.
3. **Deterministic Token Budgeting**: Research context packages are strictly bounded by `tiktoken` limits (`DEFAULT_MAX_RESEARCH_TOKENS = 2048`), preventing context blowout in agent prompts.
4. **Source Provenance & Grounding**: Every extracted piece of evidence tracks its `source_url`, `source_title`, `domain`, `relevance_score`, and `retrieved_at` timestamp.

---

## 3. Subsystem Components

### A. DuckDuckGo Provider (`research.providers.duckduckgo`)
- Connects via asynchronous `httpx.AsyncClient` with browser-compatible headers and exponential backoff retry handling.
- Queries `https://html.duckduckgo.com/html/` and `https://lite.duckduckgo.com/lite/`.
- Unwraps DuckDuckGo redirect URLs (`//duckduckgo.com/l/?uddg=...` $\rightarrow$ canonical destination).
- Parses result titles, URLs, and snippets via `BeautifulSoup`.

### B. Research Planner (`research.planner`)
- Evaluates query intent:
  - `QUICK` (default): 4 results, snippet-only evidence, low latency.
  - `DEEP`: Triggered by queries requesting in-depth documentation, full specs, benchmarks, comparisons, or architecture guides. Sets `fetch_pages = True` and retrieves 6 results.
- Decomposes comparative queries (e.g. *"FastAPI vs Litestar"*) into targeted sub-queries.

### C. Result Normalizer & URL Sanitizer (`research.normalizer`)
- Strips tracking query parameters (`utm_source`, `utm_medium`, `gclid`, `fbclid`, etc.) and anchor fragments.
- Unescapes HTML entities, strips tags, and cleans whitespace.
- Computes SHA-256 normalized text hash.

### D. Research Deduplicator (`research.dedup`)
- Canonical URL deduplication.
- Domain diversity enforcement: Limits results per domain (default max 2) to avoid single-domain domination.
- Near-duplicate content filtering using Jaccard token overlap threshold ($\ge 0.75$).

### E. Source Page Fetcher (`research.fetcher`)
- Asynchronously fetches full web pages in parallel using `httpx.AsyncClient`.
- Strips script, style, nav, footer, header, aside, iframe, noscript tags.
- Extracts clean body paragraphs up to 4,000 characters per page.

### F. Relevance Ranker & Evidence Extractor (`research.ranker`, `research.evidence`)
- Multi-signal ranking:
  $$\text{Score} = 0.45 \cdot \text{LexicalOverlap} + 0.30 \cdot \text{SearchRankDecay} + 0.15 \cdot \text{DomainAuthority} + 0.10 \cdot \text{Completeness}$$
- Formats structured `EvidenceItem` objects with provenance citations.

---

## 4. Routing Decision Table

`ContextResolver` routes user messages according to query intent:

| User Query Type | Resolved Context Source | Handled Subsystem |
| :--- | :--- | :--- |
| Live external doc, current stock, weather, 2026 news | `SourceType.WEB` | DuckDuckGo Web Research |
| Local codebase, project architecture, indexed files | `SourceType.RAG` | PostgreSQL + pgvector RAG |
| Indentation, personal preferences, profile, past decisions | `SourceType.MEMORY` | PostgreSQL Long-Term Memory |
| Compare local project indexer vs online pgvector 0.8 specs | `SourceType.RAG, SourceType.WEB` | Mixed Context Assembly |
| Greetings, chit-chat, simple math (`hi`, `what is 2+2`) | `None` | Direct Conversational Bypass |

---

## 5. Public APIs

### `WebResearchEngine` (`research.engine`)
- `research(query, depth, max_results)` $\rightarrow$ `ResearchContext`
- `search_raw(query, max_results)` $\rightarrow$ `ResearchResponse`

### `ResearchRouter` (`research.router`)
- `search(query, max_results, depth)` $\rightarrow$ `ResearchResponse`
