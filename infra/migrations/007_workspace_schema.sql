-- Migration: 007_workspace_schema.sql
-- Description: Schema for Kora Workspace & Project Intelligence (V18)
-- Tables: workspace_activity_events

CREATE TABLE IF NOT EXISTS workspace_activity_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID REFERENCES projects(id) ON DELETE CASCADE,
    activity_type TEXT NOT NULL,
    title TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_workspace_activity_project ON workspace_activity_events(project_id);
CREATE INDEX IF NOT EXISTS idx_workspace_activity_type ON workspace_activity_events(activity_type);
CREATE INDEX IF NOT EXISTS idx_workspace_activity_created ON workspace_activity_events(created_at DESC);
