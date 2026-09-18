# Kora

**RAG-First Autonomous Personal AI Agent**

Kora understands your projects, files, documents, code, and knowledge through RAG, then reasons and acts using AI models and tools.

---

## Architecture

```
apps/desktop/    Flutter desktop app (Windows · Linux · macOS)
apps/agent/      Python FastAPI backend (Agent · RAG · Models · Tools)
shared/protocol/ WebSocket message schema (canonical, language-agnostic)
infra/           Docker Compose + Alembic migrations
tests/           Backend unit + integration tests
docs/            Architecture, data-flow, and RAG design docs
```

See [`docs/architecture.md`](docs/architecture.md) for the full design.

---

## Stack

| Layer | Technology |
|---|---|
| Desktop UI | Flutter + Dart |
| Backend API | Python + FastAPI |
| Realtime | WebSocket (typed JSON protocol) |
| Database | PostgreSQL + pgvector |
| Cache / Queue | Redis |
| AI Models | HuggingFace (Qwen + Gemma) |
| Browser automation | Playwright |
| Task scheduling | APScheduler |
| Web research | Tavily (primary) · DuckDuckGo (fallback) |

---

## Quick Start (development)

### 1. Start services

```bash
cd infra
docker compose up -d
```

### 2. Backend

```bash
cd apps/agent
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
alembic upgrade head
uvicorn main:app --reload --port 8765
```

### 3. Desktop

```bash
cd apps/desktop
flutter pub get
flutter run -d linux   # or windows / macos
```

---

## Rules

- RAG and Web Research are **completely separate** — no shared DB writes.
- Model IDs exist **only** in `apps/agent/models/registry.yaml`.
- Every RAG query is **project-scoped** — no cross-project data leakage.
- All OS-specific code lives behind **platform abstractions**.
