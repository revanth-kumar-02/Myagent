# Kora Documentation

Welcome to the canonical documentation for **Kora** — an autonomous multi-modal agent desktop application and backend engine.

---

## Canonical Guides

- **[ARCHITECTURE.md](ARCHITECTURE.md)**: System architecture, agent loop, RAG pipeline, multi-agent coordination, and model routing.
- **[IMPLEMENTATION_STATUS.md](IMPLEMENTATION_STATUS.md)**: Current system maturity, active subsystems, and test coverage metrics.
- **[DATABASE.md](DATABASE.md)**: PostgreSQL 18 + pgvector 0.8.1 architecture, schemas, migrations, connection pooling, and live data verification.
- **[MEMORY.md](MEMORY.md)**: Autonomous long-term memory lifecycle, semantic vector indexing, and Knowledge Graph extraction.
- **[API.md](API.md)**: REST endpoints (`/api/health/db`, `/api/models`, `/api/projects`, etc.) and WebSocket protocol.
- **[FRONTEND.md](FRONTEND.md)**: Flutter desktop UI architecture, Theme system (Warm Ivory Light / Warm Charcoal Dark), state management, and widgets.
- **[OBSERVABILITY.md](OBSERVABILITY.md)**: Distributed trace collection, latency logging, structured JSON logs, and runtime telemetry.
- **[TESTING.md](TESTING.md)**: Backend test suite (286 pytest unit/integration tests) and Flutter test suite (37 tests).

---

## Audit & Verification Reports

- **[DOCUMENTATION_AUDIT.md](DOCUMENTATION_AUDIT.md)**: Complete inventory and classification of repository documentation.
- **[REPOSITORY_CLEANUP_REPORT.md](REPOSITORY_CLEANUP_REPORT.md)**: Infrastructure cleanup summary.
- **[POSTGRES_VERIFICATION_REPORT.md](POSTGRES_VERIFICATION_REPORT.md)**: Live database connectivity, pool validation, and persistence verification proof.
- **[Historical Archive](archive/)**: Preserved phase 1–14 implementation notes and verification logs.
