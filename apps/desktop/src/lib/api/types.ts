// Cocoa API Types

export type TaskStatus = 'idle' | 'planning' | 'executing' | 'observing' | 'verifying' | 'completed' | 'failed' | 'cancelled';

export interface Task {
  id: string;
  title: string;
  description: string;
  status: TaskStatus;
  result?: string;
  error?: string;
  project_id?: string;
  created_at: string;
  updated_at: string;
}

export interface TaskStep {
  id: string;
  task_id: string;
  step_number: number;
  title: string;
  description: string;
  tool?: string;
  status: TaskStatus;
  result?: string;
  created_at?: string;
}

export interface ActivityLog {
  id: string;
  task_id: string;
  event_type: string;
  message: string;
  details?: Record<string, any>;
  timestamp: string;
}

export interface Project {
  id: string;
  title: string;
  description?: string;
  created_at: string;
  updated_at: string;
}

export interface ResearchSource {
  id: string;
  title: string;
  url: string;
  snippet?: string;
}

export interface ResearchSession {
  id: string;
  title: string;
  query: string;
  summary?: string;
  status: string;
  sources: ResearchSource[];
  created_at: string;
}

export interface AutomationNode {
  id: string;
  name: string;
  type: string;
  status: string;
}

export interface Automation {
  id: string;
  name: string;
  description: string;
  trigger_type: string;
  nodes: AutomationNode[];
  is_active: boolean;
  last_run?: string;
}

export interface AgentRunResponse {
  task: Task;
  message: string;
}
