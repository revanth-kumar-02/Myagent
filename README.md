# Cocoa Personal Agent

A production-ready desktop AI agent built with Tauri 2, Svelte, TypeScript, Python, and FastAPI.

## Quick Start

### Phase 1 — UI Shell (no backend required)

```bash
# Install system build dependencies (first time only)
sudo apt install -y pkg-config libwebkit2gtk-4.1-dev libayatana-appindicator3-dev \
  librsvg2-dev libssl-dev patchelf postgresql postgresql-contrib redis-server

cd apps/desktop
npm install
npm run dev          # Vite dev server on http://localhost:1420
npm run tauri dev    # Full Tauri desktop window (requires Rust build)
```

### Phase 2 — Backend (PostgreSQL + Redis required)

```bash
# Start services
sudo systemctl start postgresql redis-server

# Create venv + install
cd apps/agent
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt

# Run backend
.venv/bin/uvicorn main:app --reload --port 8000
```

## Stack

| Layer | Technology |
|---|---|
| Desktop | Tauri 2 + Rust |
| Frontend | Svelte + TypeScript + Vite |
| Styling | Tailwind CSS v3 (Stitch design tokens) |
| Backend | Python 3.14 + FastAPI + Uvicorn |
| Database | PostgreSQL + SQLAlchemy + asyncpg + pgvector |
| Cache | Redis |
| LLM | Provider-agnostic gateway (Groq / OpenAI / Gemini) |
| Browser | Playwright |
| PDF | PyMuPDF |
| Scheduler | APScheduler |
| Realtime | WebSockets |
| Testing | pytest |

## Structure

```
apps/
  desktop/     ← Tauri + Svelte frontend
  agent/       ← Python FastAPI backend
packages/
  shared/      ← Shared TypeScript types
stitch/        ← Visual design reference (do not modify)
docs/
```
