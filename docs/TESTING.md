# Kora Testing Guide

This document outlines the test strategy and command suite for validating Kora backend and frontend components.

---

## 1. Backend Test Suite

The Python backend is tested using `pytest` and `pytest-asyncio`.

```bash
# Run all backend tests
PYTHONPATH=apps/agent pytest tests/agent

# Run specific subsystem tests
PYTHONPATH=apps/agent pytest tests/agent/test_rag_pipeline.py
PYTHONPATH=apps/agent pytest tests/agent/test_memory_auto_learning.py
PYTHONPATH=apps/agent pytest tests/agent/test_knowledge_graph_v11.py
```

### Current Test Coverage
- **Total Tests**: 286
- **Status**: 100% Passing (286 passed in ~5.6 seconds)

---

## 2. Frontend Test Suite

The Flutter desktop app is tested with widget, integration, and state tests.

```bash
# Run all Flutter desktop tests
cd apps/desktop && flutter test
```

### Current Test Coverage
- **Total Tests**: 37
- **Status**: 100% Passing (Theme switching, Memory Screen, Chat Composer, Slash Commands, API Client)

---

## 3. Live Database Verification

To verify live PostgreSQL connectivity, pgvector indexing, and Memory/Knowledge Graph persistence:

```bash
# Trigger backend DB diagnostics endpoint
curl -s http://localhost:8000/api/health/db | jq .
```
