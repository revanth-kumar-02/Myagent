# Kora Database Architecture

Kora relies on PostgreSQL 18 with the `pgvector` extension for vector indexing, relational persistence, and knowledge graph structures.

---

## 1. Connection & Configuration

### Canonical Configuration
All database connectivity is configured centrally in `apps/agent/config/settings.py` via `KORA_DATABASE_URL`:

```bash
KORA_DATABASE_URL=postgresql+asyncpg://kora:kora_dev_password@localhost:5433/kora
```

### Connection Pool Configuration
- **Driver**: `asyncpg` via SQLAlchemy `AsyncEngine`
- **Session Factory**: `async_sessionmaker(engine, expire_on_commit=False, autoflush=False)`
- **Pool Size**: Configurable via `KORA_DB_POOL_SIZE` (default: 10)
- **Max Overflow**: Configurable via `KORA_DB_MAX_OVERFLOW` (default: 20)
- **Worker Isolation**: Uses `NullPool` when multiple uvicorn workers are spawned to prevent connection pool deadlocks.

---

## 2. PostgreSQL Extensions

The following extensions are installed and enabled on the `kora` database:
- `vector` (version `0.8.1`): High-dimensional vector indexing and exact/approximate distance calculations (`<=>` cosine distance, `<->` L2 distance).
- `uuid-ossp`: UUID generation helpers (`uuid_generate_v4()`).
- `pg_trgm`: Trigram indexing for fuzzy text search.

---

## 3. Core Database Schemas & Tables

| Table | Description | Key Columns / Indexes |
|:---|:---|:---|
| `projects` | User workspaces and repositories | `id`, `name`, `root_path`, `config` |
| `indexed_files` | Files tracked by RAG indexer | `id`, `project_id`, `file_path`, `content_hash` |
| `chunks` | Document chunks with embeddings | `id`, `project_id`, `file_id`, `content`, `embedding` (`vector(1024)`), `tsv` (`tsvector`) |
| `agent_memory` | Autonomous long-term memory store | `id`, `project_id`, `type`, `content`, `source`, `confidence`, `importance`, `status`, `embedding` (`vector(1024)`) |
| `graph_entities` | Knowledge Graph nodes | `id`, `entity_type`, `name`, `canonical_name`, `project_id`, `source`, `confidence` |
| `graph_relationships` | Knowledge Graph directed edges | `id`, `source_entity_id`, `relationship_type`, `target_entity_id`, `project_id`, `confidence` |
| `agent_traces` | Execution step telemetry | `id`, `session_id`, `trace_id`, `step`, `duration_ms` |
| `agent_tasks` | Autonomous background tasks | `id`, `project_id`, `title`, `status`, `plan` |

---

## 4. Migration History

Migrations are located in `infra/migrations/`:
- `001_initial_schema.sql`: Initial projects, files, chunks, traces, and basic memory.
- `002_knowledge_graph_schema.sql`: Graph entities and relationships schema.
- `003_observability_schema.sql`: Structured trace spans and error telemetry.
- `004_proactive_schema.sql`: Proactive notifications and event bus schema.
- `005_multiagent_schema.sql`: Subagent coordination and shared workspace runs.
- `006_personal_knowledge_schema.sql`: User goals, milestones, decisions.
- `007_workspace_schema.sql`: Workspace activity records.
- `008_memory_v2_schema.sql`: Long-term Memory V2 lifecycle, status, and importance indexes.

---

## 5. Live Persistence Verification

Live persistence was verified via automated script executing against PostgreSQL on port 5433:
1. Connection pool initialization: **PASS**
2. Vector cosine distance `<=>` search: **PASS** (1024-dim vector match)
3. Memory creation, persistence, and retrieval: **PASS**
4. Knowledge graph entity & relationship traversal: **PASS**
