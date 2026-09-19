-- Migration: 006_personal_knowledge_schema.sql
-- Description: Schema for Kora Personal Knowledge & Goal Intelligence (V17)
-- Tables: personal_goals, personal_milestones, personal_decisions

CREATE TABLE IF NOT EXISTS personal_goals (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    state TEXT NOT NULL DEFAULT 'active',
    priority TEXT NOT NULL DEFAULT 'normal',
    project_id UUID REFERENCES projects(id) ON DELETE SET NULL,
    target_date TIMESTAMPTZ,
    progress FLOAT NOT NULL DEFAULT 0.0,
    associated_task_ids JSONB NOT NULL DEFAULT '[]'::jsonb,
    associated_decision_ids JSONB NOT NULL DEFAULT '[]'::jsonb,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_personal_goals_state ON personal_goals(state);
CREATE INDEX IF NOT EXISTS idx_personal_goals_project ON personal_goals(project_id);
CREATE INDEX IF NOT EXISTS idx_personal_goals_target ON personal_goals(target_date);

CREATE TABLE IF NOT EXISTS personal_milestones (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    goal_id UUID REFERENCES personal_goals(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    deadline TIMESTAMPTZ,
    completed BOOLEAN NOT NULL DEFAULT FALSE,
    order_index INT NOT NULL DEFAULT 0,
    completed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_personal_milestones_goal ON personal_milestones(goal_id);
CREATE INDEX IF NOT EXISTS idx_personal_milestones_completed ON personal_milestones(completed);

CREATE TABLE IF NOT EXISTS personal_decisions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    decision_text TEXT NOT NULL,
    context TEXT NOT NULL DEFAULT '',
    alternatives_considered JSONB NOT NULL DEFAULT '[]'::jsonb,
    reasoning TEXT NOT NULL DEFAULT '',
    project_id UUID REFERENCES projects(id) ON DELETE SET NULL,
    goal_id UUID REFERENCES personal_goals(id) ON DELETE SET NULL,
    outcome TEXT,
    tags JSONB NOT NULL DEFAULT '[]'::jsonb,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_personal_decisions_project ON personal_decisions(project_id);
CREATE INDEX IF NOT EXISTS idx_personal_decisions_goal ON personal_decisions(goal_id);
CREATE INDEX IF NOT EXISTS idx_personal_decisions_created ON personal_decisions(created_at DESC);
