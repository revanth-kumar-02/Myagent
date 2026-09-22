# Kora Architecture

Kora is an autonomous agent system pairing an asynchronous Python backend engine with a cross-platform Flutter desktop client.

---

## 1. System Topology

```
┌──────────────────────────────────────────────────────────────┐
│                    Flutter Desktop App                       │
│  (Chat, Composer, Knowledge/Memory, Tools, Theme Provider)   │
└──────────────────────────────┬───────────────────────────────┘
                               │ WebSocket (JSON RPC) & REST
┌──────────────────────────────▼───────────────────────────────┐
│                      FastAPI Gateway                         │
│  (Session Management, Model Routing, Health & Diagnostics)   │
└──────────────────────────────┬───────────────────────────────┘
                               │
       ┌───────────────────────┼───────────────────────┐
       ▼                       ▼                       ▼
┌──────────────┐       ┌──────────────┐       ┌────────────────┐
│  Agent Core  │       │ RAG Pipeline │       │ Knowledge      │
│  & Reasoning │       │  (Hybrid /   │       │ Graph Engine   │
│  Orchestrator│       │  pgvector)   │       │ (Entities/Rels)│
└──────┬───────┘       └──────┬───────┘       └────────┬───────┘
       │                      │                        │
       └──────────────────────┼────────────────────────┘
                              ▼
┌──────────────────────────────────────────────────────────────┐
│                   PostgreSQL 18 + pgvector                   │
│   (agent_memory, chunks, graph_entities, graph_relationships)│
└──────────────────────────────────────────────────────────────┘
```

---

## 2. Core Subsystems

### A. Agent Core & Reasoning Engine
- **Autonomous Step Loop**: Dynamic intent detection, multi-step decomposition, and tool execution.
- **Model Router**: Intelligently routes queries to LLM providers (Anthropic, Gemini, OpenAI, Groq, Ollama) based on capability, context window, and latency profile.
- **Security & Secret Masking**: Outbound queries and memory candidates are filtered to prevent credentials and private keys from leaking to external models or persistence.

### B. Long-Term Memory (V2)
- **Automatic Learning**: Extracts meaningful user preferences, project conventions, decisions, and lessons without requiring manual input.
- **Semantic Vector Storage**: 1024-dimensional normalized embeddings stored in PostgreSQL via `pgvector` with cosine similarity (`<=>`).
- **Conflict Resolution**: Identifies contradictions and supersedes obsolete memories while preserving audit trails.

### C. Unified Knowledge Graph (V11)
- **Entity & Relation Extraction**: Discovers domain concepts, code symbols, files, and relationships from multi-modal inputs.
- **Graph Traversal**: Subgraph BFS/DFS and bidirectional edge navigation for augmented contextual retrieval.

### D. Multi-Modal RAG Pipeline (V2–V4)
- **Hybrid Retrieval**: Combines pgvector dense semantic search with PostgreSQL full-text search (`tsvector` + GIN indexes).
- **Chunk Intelligence**: Document parsing and context-aware boundary chunking.
