-- Migration: 005_multiagent_schema.sql
-- Description: Schema for Kora Multi-Agent Orchestration (V16)
-- Tables: agent_coordination_runs, subagent_task_records

CREATE TABLE IF NOT EXISTS agent_coordination_runs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id UUID,
    project_id UUID REFERENCES projects(id) ON DELETE CASCADE,
    goal TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    graph_data JSONB NOT NULL DEFAULT '{}'::jsonb,
    synthesis_result JSONB NOT NULL DEFAULT '{}'::jsonb,
    error TEXT,
    duration_ms INT DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_coord_runs_project ON agent_coordination_runs(project_id);
CREATE INDEX IF NOT EXISTS idx_coord_runs_status ON agent_coordination_runs(status);
CREATE INDEX IF NOT EXISTS idx_coord_runs_created ON agent_coordination_runs(created_at DESC);

CREATE TABLE IF NOT EXISTS subagent_task_records (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id UUID REFERENCES agent_coordination_runs(id) ON DELETE CASCADE,
    agent_type TEXT NOT NULL,
    objective TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    dependencies JSONB NOT NULL DEFAULT '[]'::jsonb,
    input_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    output_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    sources JSONB NOT NULL DEFAULT '[]'::jsonb,
    error TEXT,
    duration_ms INT DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_subagent_tasks_run ON subagent_task_records(run_id);
CREATE INDEX IF NOT EXISTS idx_subagent_tasks_type ON subagent_task_records(agent_type);
CREATE INDEX IF NOT EXISTS idx_subagent_tasks_status ON subagent_task_records(status);
