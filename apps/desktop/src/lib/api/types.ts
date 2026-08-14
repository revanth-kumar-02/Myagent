// Cocoa API Types

export type TaskStatus = 'idle' | 'planning' | 'executing' | 'observing' | 'verifying' | 'completed' | 'failed' | 'cancelled';
export type ResearchStatus = 'idle' | 'planning' | 'researching' | 'verifying' | 'synthesizing' | 'completed' | 'failed' | 'cancelled';

export interface Workspace {
  id: string;
  name: string;
  path: string;
  is_active: boolean;
  created_at?: string;
  updated_at?: string;
}

export interface Project {
  id: string;
  workspace_id?: string;
  title: string;
  path?: string;
  description?: string;
  icon?: string;
  languages?: string[];
  frameworks?: string[];
  git_repository?: boolean;
  detection_confidence?: string;
  last_scanned?: string;
  last_modified?: string;
  metadata_info?: Record<string, any>;
  created_at?: string;
  updated_at?: string;
}

export interface ScanWorkspaceResponse {
  workspace: Workspace;
  projects: Project[];
}

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

export interface ResearchSource {
  id: string;
  research_session_id: string;
  title: string;
  url: string;
  domain: string;
  provider: string;
  retrieved_at?: string;
  content_excerpt?: string;
  relevance?: number;
}

export interface ResearchEvidence {
  id: string;
  research_session_id: string;
  source_id?: string;
  claim: string;
  supporting_text: string;
  confidence: string;
}

export interface ResearchFinding {
  id: string;
  research_session_id: string;
  finding_text: string;
  is_verified: boolean;
  verification_confidence: string;
  supporting_sources?: string[];
}

export interface ResearchSession {
  id: string;
  session_code: string;
  title: string;
  query: string;
  brief: string;
  status: ResearchStatus;
  confidence: number;
  synthesis_markdown?: string;
  project_id?: string;
  created_at: string;
  updated_at?: string;
  sources: ResearchSource[];
  evidence: ResearchEvidence[];
  findings: ResearchFinding[];
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

export interface BrowserSessionDomain {
  domain: string;
  first_visited: string;
  last_visited: string;
  visit_count: number;
}

export interface BrowserSessionData {
  session_id: string;
  task_id?: string;
  created_at: string;
  active_page_id?: string;
  pages_count: number;
  domains: BrowserSessionDomain[];
}

export interface UserProfile {
  username: string;
}

