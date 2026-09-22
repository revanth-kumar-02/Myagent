# Kora API Specification

Kora exposes a hybrid interface: **REST endpoints** for diagnostics, project configuration, and knowledge exploration, and a **WebSocket endpoint** for streaming agent execution and live events.

---

## 1. REST Endpoints

### Health & Diagnostics
- `GET /api/health` — Agent engine liveness and uptime check.
- `GET /api/health/db` — Live PostgreSQL connectivity, connection pool, schema, pgvector availability, and persistence diagnostic check.

### Model Registry
- `GET /api/models` — List all registered LLM and embedding models and active providers. All API keys and secrets are masked.

### Projects & Workspaces
- `GET /api/projects` — List active projects.
- `POST /api/projects` — Create or initialize a project workspace.

### Long-Term Memory
- `GET /api/memory` — List memories with optional filtering by project or type.
- `POST /api/memory` — Create a memory record.
- `PUT /api/memory/{id}` — Update or correct a memory record.
- `DELETE /api/memory/{id}` — Delete a memory record.
- `POST /api/memory/auto-learn` — Process interaction turns for automated candidate extraction.

### Web Research
- `POST /api/research` — Perform live DuckDuckGo web searches and extract clean text summaries with source URLs.

---

## 2. WebSocket Protocol (`/ws`)

The WebSocket interface uses JSON-RPC 2.0 formatted message frames. See `shared/protocol/messages.md` for complete schema definitions.
