# Kora — RAG-First Autonomous Personal AI Agent

<p align="center">
  <strong>An intelligent, privacy-first personal AI assistant that connects your local codebase, documents, knowledge graph, and external tools into a unified reasoning and execution environment.</strong>
</p>

---

## 🌟 Key Capabilities

- 🔍 **Hybrid Multi-Stage RAG**: Combines dense vector retrieval (BAAI/bge-m3 + `pgvector`), BM25 lexical search, Reciprocal Rank Fusion (RRF), and cross-encoder reranking.
- 🧠 **Context-Aware Task Planning**: Dynamic task decomposition, autonomous multi-step reasoning, execution verification, and dynamic replanning.
- ⚡ **Model Routing & LLM Gateway**: Seamless role-based model routing (Chat, Reason, Code, Vision, Audio) backed by Hugging Face / OpenRouter inference.
- 🛠️ **Dynamic Tool Execution & Slash Commands**: Interactive `/` tool launcher with 27+ built-in system, browser, file, developer, and scheduling tools governed by a 4-tier permission policy.
- 📊 **Local Knowledge Graph & Adaptive Memory**: Extracts entities and relationships across projects, maintaining persistent facts, preferences, and workflow learnings.
- 💻 **Cross-Platform Flutter UI**: Clean, light-themed desktop application with real-time streaming, syntax-highlighted Markdown rendering, floating command docks, and responsive tool feedback.

---

## 🏗️ Architecture Overview

```
                          ┌────────────────────────┐
                          │   Flutter Desktop App  │
                          │ (Windows·Linux·macOS)  │
                          └───────────┬────────────┘
                                      │ WebSocket / HTTP
                                      ▼
                          ┌────────────────────────┐
                          │  FastAPI Agent Server  │
                          │   (apps/agent @ 8765)  │
                          └───────────┬────────────┘
                                      │
         ┌────────────────────────────┼────────────────────────────┐
         ▼                            ▼                            ▼
┌──────────────────┐        ┌──────────────────┐        ┌──────────────────┐
│   Agent Core     │        │   RAG Pipeline   │        │   Tool System    │
├──────────────────┤        ├──────────────────┤        ├──────────────────┤
│ • Intent Analysis│        │ • Dense Vectors  │        │ • Tool Registry  │
│ • Task Planner   │        │ • BM25 Search    │        │ • PermissionGate │
│ • Decision Engine│        │ • AST Chunking   │        │ • OS Automations │
│ • Verifier & Eval│        │ • KnowledgeGraph │        │ • Browser Control│
└────────┬─────────┘        └────────┬─────────┘        └────────┬─────────┘
         │                           │                           │
         └───────────────────────────┼───────────────────────────┘
                                     ▼
                      ┌──────────────────────────────┐
                      │  PostgreSQL (pgvector) +     │
                      │  Redis Cache + Local Storage │
                      └──────────────────────────────┘
```

---

## 📂 Project Structure

```bash
Myagent/
├── apps/
│   ├── agent/                 # Python FastAPI agent backend
│   │   ├── api/               # REST (/api) and WebSocket (/ws) endpoints
│   │   ├── core/              # Planner, Context, Session, Executor, Verifier
│   │   ├── db/                # PostgreSQL + Redis connection clients
│   │   ├── graph/             # Knowledge graph extraction & Cypher/SQL queries
│   │   ├── models/            # Model registry, router, and LLM gateway (HF)
│   │   ├── permissions/       # 4-tier Permission Gate & approval workflows
│   │   ├── rag/               # Chunking, embeddings, hybrid retrieval & indexer
│   │   ├── research/          # DuckDuckGo & Tavily web research synthesis
│   │   ├── tools/             # 27+ system, web, dev, computer & file tools
│   │   └── voice/             # Audio processing & voice assistant gateway
│   └── desktop/               # Flutter desktop & web client
│       ├── lib/
│       │   ├── core/          # App config, theme, and networking
│       │   ├── features/      # Chat, Projects, RAG, Memory, & Dashboard
│       │   ├── models/        # Data models (Messages, Tools, Citations)
│       │   ├── services/      # WebSocket client and HTTP API services
│       │   ├── state/         # Riverpod state notifiers
│       │   └── widgets/       # Markdown renderers, Slash command picker, UI
├── docs/                      # Technical specifications & verification logs
├── infra/                     # Docker Compose (Postgres + pgvector + Redis)
├── shared/
│   └── protocol/              # Canonical WebSocket message envelopes
└── tests/                     # 275+ Pytest suites & Flutter widget/unit tests
```

---

## 🛠️ Technology Stack

| Layer | Technologies |
|---|---|
| **Frontend / Desktop** | Flutter 3.x, Dart, Riverpod, flutter_markdown |
| **Backend API** | Python 3.12+, FastAPI, Uvicorn, AsyncIO, Structlog |
| **Persistence** | PostgreSQL 16 + `pgvector`, SQLAlchemy (async), Alembic, Redis 7 |
| **Embeddings & LLMs** | Hugging Face Inference API, BAAI/bge-m3, Qwen 2.5 / Gemma |
| **Automations & Tools** | Playwright (Browser), APScheduler, PyAutoGUI, System Subprocess |
| **Testing** | Pytest (Asyncio, Typeguard), Flutter Test |

---

## 🚀 Quick Start Guide

### Prerequisites
- Python 3.11+
- Flutter SDK (3.22+)
- Docker & Docker Compose
- Hugging Face API Token (`HF_TOKEN`)

---

### 1. Start Infrastructure Services

Spin up PostgreSQL (with `pgvector` enabled) and Redis:

```bash
cd infra
docker compose up -d
```

---

### 2. Configure and Run Backend

```bash
cd apps/agent

# Create virtual environment & activate
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -e ".[dev]"

# Configure environment variables
cp .env.example .env   # Ensure HF_TOKEN and DB URLs are configured

# Run database migrations
alembic upgrade head

# Start the agent service
python3 main.py
```

*The backend server will run on `http://127.0.0.1:8765` with WebSockets available at `ws://127.0.0.1:8765/ws`.*

---

### 3. Launch Desktop Client

In a new terminal window:

```bash
cd apps/desktop

# Fetch Flutter packages
flutter pub get

# Run on your desktop platform (Linux, macOS, or Windows)
flutter run -d linux   # or macos / windows / web-server
```

---

## ⌨️ Slash Commands & Tools

Type `/` at the beginning of the chat composer to open the dynamic tool picker:

| Slash Command | Category | Description |
|---|---|---|
| `/search <query>` | Research | Instant web search via DuckDuckGo |
| `/research <topic>` | Research | Multi-step deep web research with source synthesis |
| `/rag <query>` | Knowledge | Semantic and lexical retrieval over active workspace |
| `/file_read <path>` | Files | Inspect file contents within project scope |
| `/terminal_exec <cmd>` | Dev | Execute workspace terminal commands (Requires approval) |
| `/git_ops <action>` | Dev | Inspect git status, diff, branches, and logs |
| `/system_info` | System | Query host CPU, memory, OS, and platform metrics |
| `/page_navigation <url>` | Web | Automated headless/visible browser navigation |

---

## 🛡️ Security & Permission Governance

Kora implements a strict **4-Tier Permission Gate**:
1. **`READ`**: Safe read-only operations (`system_info`, `file_read`, `screen_capture`) — Auto-approved.
2. **`LOW_RISK_WRITE`**: Non-destructive writes (`clipboard`, `file_write`, `git_ops`) — Session-cached approvals.
3. **`EXTERNAL_ACTION`**: Network calls & browser interaction (`page_navigation`, `download_manager`) — Policy checked.
4. **`HIGH_IMPACT_ACTION`**: Destructive or system-level actions (`terminal_exec`, `file_delete`, `database_ops`) — Requires explicit user approval via interactive WebSocket prompt.

---

## 🧪 Testing & Verification

Run the complete test suite across both frontend and backend:

```bash
# Run Backend Pytest Suite (275+ tests)
PYTHONPATH=apps/agent pytest tests/agent

# Run Flutter Unit & Widget Tests (32+ tests)
cd apps/desktop
flutter test
```

---

## 📄 License

This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for details.
