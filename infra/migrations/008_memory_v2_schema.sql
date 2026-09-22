-- Kora — Migration 008: Memory V2 Schema Upgrade
-- Adds enhanced metadata, lifecycle, and indexing fields for Long-Term Memory (V2)

ALTER TABLE agent_memory
    ADD COLUMN IF NOT EXISTS source TEXT NOT NULL DEFAULT 'user_explicit',
    ADD COLUMN IF NOT EXISTS confidence FLOAT NOT NULL DEFAULT 1.0,
    ADD COLUMN IF NOT EXISTS importance FLOAT NOT NULL DEFAULT 0.5,
    ADD COLUMN IF NOT EXISTS content_hash TEXT,
    ADD COLUMN IF NOT EXISTS status TEXT NOT NULL DEFAULT 'active',
    ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    ADD COLUMN IF NOT EXISTS last_accessed_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    ADD COLUMN IF NOT EXISTS expiration_at TIMESTAMPTZ;

CREATE INDEX IF NOT EXISTS idx_agent_memory_status ON agent_memory(status);
CREATE INDEX IF NOT EXISTS idx_agent_memory_type ON agent_memory(type);
CREATE INDEX IF NOT EXISTS idx_agent_memory_content_hash ON agent_memory(content_hash);
CREATE INDEX IF NOT EXISTS idx_agent_memory_importance ON agent_memory(importance);
