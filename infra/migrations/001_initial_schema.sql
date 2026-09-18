-- Kora — Initial Schema
-- Run via: alembic upgrade head
-- Or directly: psql -U kora -d kora -f 001_initial_schema.sql

-- ── Extensions ────────────────────────────────────────────────────────────────
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "vector";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";  -- trigram for fuzzy matching

-- ── Projects ──────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS projects (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name        TEXT NOT NULL,
    root_path   TEXT NOT NULL,
    config      JSONB NOT NULL DEFAULT '{}',
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ── Indexed Files (change detection) ──────────────────────────────────────────
CREATE TABLE IF NOT EXISTS indexed_files (
    id           UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    project_id   UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    file_path    TEXT NOT NULL,
    content_hash TEXT NOT NULL,   -- SHA-256 of file content
    file_size    BIGINT,
    last_seen    TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (project_id, file_path)
);
CREATE INDEX IF NOT EXISTS idx_indexed_files_project ON indexed_files(project_id);

-- ── Chunks ────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS chunks (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    project_id  UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    file_id     UUID NOT NULL REFERENCES indexed_files(id) ON DELETE CASCADE,
    chunk_index INT  NOT NULL,
    content     TEXT NOT NULL,
    embedding   vector(1024),     -- BAAI/bge-m3 dimension; update if model changes
    tsv         TSVECTOR,         -- populated via trigger below
    metadata    JSONB NOT NULL DEFAULT '{}',
    -- metadata shape: { type, language, start_line, end_line, headings[], symbol }
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Vector index (IVFFlat; adjust lists based on expected dataset size)
CREATE INDEX IF NOT EXISTS idx_chunks_embedding
    ON chunks USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);

-- Full-text index
CREATE INDEX IF NOT EXISTS idx_chunks_tsv
    ON chunks USING GIN (tsv);

-- Project isolation index (always filtered by project_id)
CREATE INDEX IF NOT EXISTS idx_chunks_project ON chunks(project_id);

-- Trigger: auto-populate tsvector from content
CREATE OR REPLACE FUNCTION chunks_tsv_update() RETURNS trigger AS $$
BEGIN
    NEW.tsv := to_tsvector('english', NEW.content);
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trig_chunks_tsv ON chunks;
CREATE TRIGGER trig_chunks_tsv
    BEFORE INSERT OR UPDATE OF content ON chunks
    FOR EACH ROW EXECUTE FUNCTION chunks_tsv_update();

-- ── Agent Memory ───────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS agent_memory (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_id  UUID,
    project_id  UUID,             -- null = global memory
    type        TEXT NOT NULL,    -- 'episode' | 'fact' | 'preference'
    content     TEXT NOT NULL,
    embedding   vector(1024),
    metadata    JSONB NOT NULL DEFAULT '{}',
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_agent_memory_embedding
    ON agent_memory USING ivfflat (embedding vector_cosine_ops) WITH (lists = 10);
CREATE INDEX IF NOT EXISTS idx_agent_memory_project ON agent_memory(project_id);
CREATE INDEX IF NOT EXISTS idx_agent_memory_session ON agent_memory(session_id);

-- ── Observability Traces ───────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS agent_traces (
    id            UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_id    UUID,
    trace_id      UUID NOT NULL,
    step          TEXT NOT NULL,
    model         TEXT,
    input_tokens  INT,
    output_tokens INT,
    latency_ms    INT,
    metadata      JSONB NOT NULL DEFAULT '{}',
    ts            TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_agent_traces_session ON agent_traces(session_id);
CREATE INDEX IF NOT EXISTS idx_agent_traces_trace   ON agent_traces(trace_id);
CREATE INDEX IF NOT EXISTS idx_agent_traces_ts      ON agent_traces(ts DESC);
