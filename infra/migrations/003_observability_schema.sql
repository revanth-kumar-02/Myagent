-- Kora — Migration 003: Observability Schema (V14)
-- Run via: psql -U kora -d kora -f 003_observability_schema.sql

-- ── Structured Agent Events Table ──────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS agent_events (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    trace_id    UUID NOT NULL REFERENCES agent_traces(trace_id) ON DELETE CASCADE,
    event_type  TEXT NOT NULL,    -- 'request_received', 'planning_started', 'context_retrieved', etc.
    component   TEXT NOT NULL,    -- 'agent_core', 'rag', 'memory', 'web', 'tools', 'models'
    status      TEXT NOT NULL DEFAULT 'info', -- 'info', 'success', 'warning', 'error'
    duration_ms INT DEFAULT 0,
    payload     JSONB NOT NULL DEFAULT '{}',
    ts          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_agent_events_trace ON agent_events(trace_id);
CREATE INDEX IF NOT EXISTS idx_agent_events_type  ON agent_events(event_type);
CREATE INDEX IF NOT EXISTS idx_agent_events_comp  ON agent_events(component);
CREATE INDEX IF NOT EXISTS idx_agent_events_ts    ON agent_events(ts DESC);

-- ── Normalized Agent Errors Table ──────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS agent_errors (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    trace_id    UUID REFERENCES agent_traces(trace_id) ON DELETE CASCADE,
    error_code  TEXT NOT NULL,    -- 'ERR_RAG_TIMEOUT', 'ERR_TOOL_PERMISSION_DENIED', etc.
    component   TEXT NOT NULL,    -- 'rag', 'memory', 'research', 'models', 'tools', 'db'
    message     TEXT NOT NULL,
    severity    TEXT NOT NULL DEFAULT 'error', -- 'info', 'warning', 'error', 'critical'
    details     JSONB NOT NULL DEFAULT '{}',
    ts          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_agent_errors_trace ON agent_errors(trace_id);
CREATE INDEX IF NOT EXISTS idx_agent_errors_code  ON agent_errors(error_code);
CREATE INDEX IF NOT EXISTS idx_agent_errors_comp  ON agent_errors(component);
CREATE INDEX IF NOT EXISTS idx_agent_errors_sev   ON agent_errors(severity);
CREATE INDEX IF NOT EXISTS idx_agent_errors_ts    ON agent_errors(ts DESC);
