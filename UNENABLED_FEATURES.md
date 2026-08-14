# Cocoa — Unenabled & Pending Features Audit Report

**Audit Date**: August 14, 2026  
**Auditor**: Antigravity Autonomous Agentic AI System  
**Target Application**: Cocoa Desktop AI Agent Workspace (`apps/desktop` + `apps/agent`)  

---

## 📋 Executive Summary of Unenabled Features

While Cocoa's core architecture—including goal planning, filesystem sandboxing, real-time Tavily web search, and WebSocket task execution—is fully active, a subset of secondary capabilities remain **unenabled**, **partially configured**, or **pending host-level dependencies**.

---

## 🚫 Detailed Unenabled & Pending Features Matrix

| Feature | Feature Category | Current Status | Cause / Dependency | Impact | Remediation Plan |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Automations Background Cron Loop** | Background Engine | 🔴 **UNENABLED** | Missing `APScheduler` background service loop in `apps/agent/main.py`. | Scheduled automations persist in SQLite but do not trigger automatically on timer. | Attach `AsyncIOScheduler` in `main.py` startup event. |
| **Playwright Chromium Host Binaries** | Browser Automation | 🟡 **PENDING SETUP** | Requires host-level `playwright install chromium` binary installation. | Browser agent tools fall back to HTTP extraction if Chromium is missing. | Run `playwright install chromium` or auto-trigger setup on agent boot. |
| **Settings UI REST Persistence Binding** | UI / Settings | 🟡 **PARTIALLY BOUND** | `Settings.svelte` holds form state but lacks `POST /api/v1/settings` fetch call. | Settings updated in UI do not survive backend server restarts. | Connect `Settings.svelte` submit button to `api.updateSettings()`. |
| **LLM Key for Generative Reasoning** | Agent Intelligence | 🟡 **FALLBACK MODE** | `LLM_API_KEY` (Groq / OpenAI) not set in `.env`. | Uses deterministic `RuleBasedLLMProvider` for planning instead of dynamic LLM. | Add `LLM_API_KEY` (e.g. Groq `gsk_...` or OpenAI `sk-...`) to `.env`. |
| **Semantic Vector Search (RAG)** | Filesystem Intelligence | ⚪ **NOT IMPLEMENTED** | `SearchFilesTool` uses ripgrep/string matching instead of vector embeddings. | Search is exact-match and regex-based rather than semantic/embedding-based. | Integrate ChromaDB or FAISS local embedding pipeline. |
| **Voice / Speech Engine (STT/TTS)** | Input / Interaction | ⚪ **NOT IMPLEMENTED** | Application input is strictly text & file based. | No Whisper voice-to-text or synthesized audio output. | Add Web Speech API or Whisper audio backend service. |
| **Multi-Tenant User Auth & RBAC** | Security / User Access | ⚪ **BY DESIGN (LOCAL)** | Built as a single-user local desktop app. | No multi-user login, OAuth authentication, or remote RBAC. | N/A (Designed for local desktop privacy). |

---

## 🔍 Feature Deep Dive & Enablement Roadmap

### 1. Automations Cron Engine (P1)
* **Description**: Allows users to save recurring workflows (e.g., "Summarize repo every morning at 9 AM").
* **Current State**: Database models (`Automation`) and REST endpoints (`/api/v1/automations`) are active.
* **To Enable**:
  ```python
  from apscheduler.schedulers.asyncio import AsyncIOScheduler

  scheduler = AsyncIOScheduler()
  scheduler.start()
  ```

### 2. Playwright Host Chromium Installation (P2)
* **Description**: Powers interactive web browsing (clicking buttons, filling forms, scrolling).
* **Current State**: Full Python browser toolset is ready. Requires binary download.
* **To Enable**:
  ```bash
  apps/agent/.venv/bin/python -m playwright install chromium
  ```

### 3. Groq / OpenAI LLM Key Setup (P2)
* **Description**: Replaces rule-based deterministic goal planner with high-reasoning LLMs.
* **Current State**: Web search key (Tavily) is active; LLM gateway currently falls back to rule engine.
* **To Enable**:
  Add your Groq or OpenAI key to `apps/agent/.env`:
  ```env
  LLM_PROVIDER=groq
  LLM_MODEL=llama-3.3-70b-versatile
  LLM_API_KEY=gsk_your_groq_api_key_here
  ```

### 4. Settings Form Submission Handler (P3)
* **Description**: Persists user settings changes directly from the desktop Settings tab.
* **Current State**: API route `/api/v1/settings` is ready on backend.
* **To Enable**: Add `api.updateSettings(formData)` to `Settings.svelte`.

---

## 🟢 Currently Active & Fully Enabled Features
For context, the following core features are **100% Active & Operational**:
* ✅ **Tavily Live Web Search & Multi-Stage Deep Research**
* ✅ **Agent Goal Planning, Execution, Verification Loop**
* ✅ **Sandboxed Filesystem Tools (Read, Write, Edit, Search, List)**
* ✅ **Home Composer with File Attachments (`+ File`)**
* ✅ **Dynamic Time-of-Day User Greetings (`Good morning, Rev`)**
* ✅ **Real-Time WebSocket Task Observability Stream**
* ✅ **SQLite Persistence & Workspace Scanner**
