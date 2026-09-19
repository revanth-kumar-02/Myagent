-- Kora — Migration 002: Knowledge Graph Schema (V11)
-- Run via: psql -U kora -d kora -f 002_knowledge_graph_schema.sql

-- ── Graph Entities Table ───────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS graph_entities (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    entity_type     TEXT NOT NULL,    -- 'person' | 'project' | 'organization' | 'file' | 'document' | 'code_symbol' | 'task' | 'technology' | 'concept' | 'web_source'
    name            TEXT NOT NULL,
    canonical_name  TEXT NOT NULL,    -- normalized/lowercased for indexing & lookups
    project_id      UUID REFERENCES projects(id) ON DELETE CASCADE, -- NULL = global/shared entity
    source          TEXT NOT NULL,    -- 'file:path', 'chunk:uuid', 'memory:uuid', 'web:url', 'task:uuid'
    confidence      FLOAT NOT NULL DEFAULT 1.0,
    metadata        JSONB NOT NULL DEFAULT '{}',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_graph_entities_project   ON graph_entities(project_id);
CREATE INDEX IF NOT EXISTS idx_graph_entities_type      ON graph_entities(entity_type);
CREATE INDEX IF NOT EXISTS idx_graph_entities_canonical ON graph_entities(canonical_name);
CREATE INDEX IF NOT EXISTS idx_graph_entities_source    ON graph_entities(source);

-- ── Graph Relationships Table ──────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS graph_relationships (
    id                UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    source_entity_id  UUID NOT NULL REFERENCES graph_entities(id) ON DELETE CASCADE,
    relationship_type TEXT NOT NULL,  -- 'belongs_to' | 'references' | 'depends_on' | 'created_by' | 'related_to' | 'contains' | 'implements' | 'uses' | 'derived_from' | 'contradicts'
    target_entity_id  UUID NOT NULL REFERENCES graph_entities(id) ON DELETE CASCADE,
    project_id        UUID REFERENCES projects(id) ON DELETE CASCADE, -- NULL = global/shared relation
    confidence        FLOAT NOT NULL DEFAULT 1.0,
    provenance        JSONB NOT NULL DEFAULT '{}', -- { source_type, file_path, chunk_id, evidence, is_inferred }
    is_inferred       BOOLEAN NOT NULL DEFAULT FALSE,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_graph_rel_source  ON graph_relationships(source_entity_id);
CREATE INDEX IF NOT EXISTS idx_graph_rel_target  ON graph_relationships(target_entity_id);
CREATE INDEX IF NOT EXISTS idx_graph_rel_type    ON graph_relationships(relationship_type);
CREATE INDEX IF NOT EXISTS idx_graph_rel_project ON graph_relationships(project_id);
