# KORA — RAG V2: RETRIEVAL ENGINE SPECIFICATION

## Overview

Kora RAG V2 upgrades the retrieval and context generation subsystem into a modular, multi-signal retrieval engine designed for autonomous AI agents. It operates exclusively on PostgreSQL with `pgvector` and `tsvector`, preserving project isolation and incremental indexing from V1 while adding deterministic multi-signal ranking, duplicate removal, sensitive content protection, interchangeable rerankers, and rich-provenance bounded context construction.

---

## 1. Architecture & Data Flow

```
User Query
    │
    ▼
RetrievalEngine.search / retrieve_context
    │
    ├──► EmbeddingService.embed_query (1024-dim, retry with backoff, secret guard)
    │
    ├──► Parallel Search:
    │      ├── Dense Vector Similarity (pgvector cosine: 1 - (embedding <=> qvec))
    │      └── Sparse Full-Text (tsvector / ts_rank_cd)
    │
    ├──► Metadata Filtering (doc_type, file_path, custom tags)
    │
    ├──► Multi-Signal Scoring:
    │      ├── Dense Score (45%)
    │      ├── Sparse Score (35%)
    │      ├── Exact Symbol / Term Match Boost (12%)
    │      └── File Path Match Boost (8%)
    │
    ├──► Deduplication (by chunk_id and file_path + line span)
    │
    ├──► Reranker Abstraction (CrossEncoderReranker / NoOpReranker)
    │
    └──► ContextBuilder (Token budget enforcement + rich provenance formatting)
           │
           ▼
     RAGContext (Bounded context text + source citations)
```

---

## 2. Core Components

### 2.1 Embedding Pipeline (`rag/embedder.py`)
- **`BaseEmbedder`**: Abstract interface enabling drop-in replacement of embedding models.
- **`EmbeddingService`**:
  - Process-level singleton loaded lazily (`BAAI/bge-m3` default).
  - Batch embedding with thread-pool offloading.
  - Automatic retry with exponential backoff and jitter (`max_retries=3`).
  - Embedding dimension validation (uniform vectors matching `expected_dim=1024`).
  - Sensitive content & credential guard (`is_sensitive_content`), protecting RSA keys, API tokens, and secrets from entering vector storage.

### 2.2 Multi-Signal Hybrid Retriever (`rag/retriever.py`)
- **Search Modes**:
  - `SearchMode.HYBRID`: Parallel dense + sparse with RRF fusion and multi-signal scoring.
  - `SearchMode.SEMANTIC`: Dense vector similarity only.
  - `SearchMode.KEYWORD`: Sparse PostgreSQL full-text search only.
- **Multi-Signal Score Synthesis**:
  $$\text{Score} = 0.45 \cdot S_{\text{dense}} + 0.35 \cdot S_{\text{sparse}} + 0.12 \cdot B_{\text{exact}} + 0.08 \cdot B_{\text{path}}$$
- **Deduplication**: Eliminates overlapping chunks and duplicate chunk IDs before final ranking.
- **Project Isolation**: Every SQL query is parameterized with `WHERE project_id = :project_id`.

### 2.3 Reranker Abstraction (`rag/reranker.py`)
- **`BaseReranker`**: Clean abstract protocol (`async def rerank(query, candidates, top_k)`).
- **`CrossEncoderReranker`**: Deep query-candidate joint evaluation using `sentence-transformers/cross-encoder`.
- **`NoOpReranker`**: Zero-overhead pass-through for low-latency and unit testing.

### 2.4 Bounded Context Builder (`rag/context_builder.py`)
- Formats ranked chunks into structured context blocks for the agent's context window.
- **Rich Provenance Tags**:
  - `[Index] file_path:start_line-end_line`
  - `type`: Document type (`code`, `markdown`, `document`, `spreadsheet`, `plain`)
  - `symbol`: Function, class, or method name
  - `heading`: Markdown heading breadcrumb hierarchy (`H1 > H2 > H3`)
  - `page` / `sheet` / `section` / `slide`
  - `score`: Calibrated relevance score
- **Token Budget Guard**: Employs `tiktoken` (`cl100k_base`) to guarantee context never overflows the agent's token allocation.

### 2.5 Retrieval Engine Public API (`rag/engine.py`)
- `search(query, project_id, mode, limit, metadata_filter, enable_reranking)`
- `hybrid_search(query, project_id, limit, metadata_filter)`
- `semantic_search(query, project_id, limit, metadata_filter)`
- `keyword_search(query, project_id, limit, metadata_filter)`
- `retrieve_context(query, project_id, max_tokens, metadata_filter)`

---

## 3. Configuration

Configurable via environment variables and `apps/agent/config/settings.py`:

| Setting | Default | Description |
|---|---|---|
| `KORA_RAG_EMBED_MODEL` | `BAAI/bge-m3` | Embedding model identifier |
| `KORA_RAG_EMBEDDING_BATCH_SIZE` | `32` | Batch size for vector encoding |
| `KORA_RAG_RERANKER_MODEL` | `cross-encoder/ms-marco-MiniLM-L-6-v2` | Cross-encoder model identifier |
| `KORA_RAG_RETRIEVAL_TOP_K_DENSE` | `60` | Candidates from vector search |
| `KORA_RAG_RETRIEVAL_TOP_K_SPARSE` | `60` | Candidates from full-text search |
| `KORA_RAG_RRF_CANDIDATES` | `80` | Pre-reranking candidate pool size |
| `KORA_RAG_RERANKER_TOP_K` | `10` | Final top chunks after reranking |
