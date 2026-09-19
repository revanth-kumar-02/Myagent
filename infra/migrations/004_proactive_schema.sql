-- Migration: 004_proactive_schema.sql
-- Description: Schema for Kora Proactive Intelligence Engine (V15)
-- Tables: proactive_events, proactive_notifications

CREATE TABLE IF NOT EXISTS proactive_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_type TEXT NOT NULL,
    title TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    project_id UUID REFERENCES projects(id) ON DELETE CASCADE,
    task_id UUID REFERENCES agent_tasks(id) ON DELETE SET NULL,
    content_hash TEXT NOT NULL,
    payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    relevance_score FLOAT,
    urgency TEXT DEFAULT 'normal',
    importance FLOAT DEFAULT 0.5,
    decision TEXT DEFAULT 'ignore',
    ts TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_proactive_events_source ON proactive_events(source_type);
CREATE INDEX IF NOT EXISTS idx_proactive_events_project ON proactive_events(project_id);
CREATE INDEX IF NOT EXISTS idx_proactive_events_hash ON proactive_events(content_hash);
CREATE INDEX IF NOT EXISTS idx_proactive_events_ts ON proactive_events(ts DESC);

CREATE TABLE IF NOT EXISTS proactive_notifications (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    event_id UUID REFERENCES proactive_events(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    message TEXT NOT NULL,
    priority TEXT NOT NULL DEFAULT 'normal',
    decision TEXT NOT NULL DEFAULT 'inform',
    category TEXT NOT NULL DEFAULT 'system',
    status TEXT NOT NULL DEFAULT 'pending',
    project_id UUID REFERENCES projects(id) ON DELETE CASCADE,
    related_task_id UUID REFERENCES agent_tasks(id) ON DELETE SET NULL,
    action_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    snooze_until TIMESTAMPTZ,
    delivered_at TIMESTAMPTZ,
    responded_at TIMESTAMPTZ,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_proactive_notifs_status ON proactive_notifications(status);
CREATE INDEX IF NOT EXISTS idx_proactive_notifs_priority ON proactive_notifications(priority);
CREATE INDEX IF NOT EXISTS idx_proactive_notifs_category ON proactive_notifications(category);
CREATE INDEX IF NOT EXISTS idx_proactive_notifs_project ON proactive_notifications(project_id);
CREATE INDEX IF NOT EXISTS idx_proactive_notifs_created ON proactive_notifications(created_at DESC);
