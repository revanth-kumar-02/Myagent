// Cocoa API Types

export type TaskStatus = 
  | 'pending' | 'PENDING'
  | 'ready' | 'READY'
  | 'running' | 'RUNNING' | 'idle' | 'executing' | 'observing' | 'planning'
  | 'waiting_permission' | 'WAITING_PERMISSION'
  | 'waiting_dependency' | 'WAITING_DEPENDENCY'
  | 'verifying' | 'VERIFYING'
  | 'completed' | 'COMPLETED'
  | 'failed' | 'FAILED'
  | 'replanning' | 'REPLANNING'
  | 'cancelled' | 'CANCELLED';

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

export interface TaskStep {
  id: string;
  task_id: string;
  step_number: number;
  label?: string;
  title?: string;
  description?: string;
  tool?: string;
  arguments?: Record<string, any>;
  dependencies?: string[];
  status: TaskStatus;
  result?: string;
  error?: string;
  retry_count?: number;
  created_at?: string;
}

export interface Task {
  id: string;
  title: string;
  description?: string;
  status: TaskStatus;
  result?: string;
  error?: string;
  project_id?: string;
  retry_count?: number;
  created_at: string;
  updated_at: string;
  steps?: TaskStep[];
  plan_data?: Record<string, any>;
}

export interface ActivityLog {
  id: string;
  task_id?: string;
  event_type?: string;
  message: string;
  status?: string;
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

export interface AutomationRun {
  id: string;
  automation_id: string;
  status: string;
  trigger_reason?: string;
  started_at: string;
  completed_at?: string;
  duration_seconds?: number;
  retry_count: number;
  tool_call_count: number;
  llm_call_count: number;
  result_summary?: string;
  error_message?: string;
  execution_logs?: any[];
}

export interface Automation {
  id: string;
  title: string;
  description?: string;
  trigger_type: string;
  trigger_config?: Record<string, any>;
  workflow_config?: Record<string, any>;
  nodes?: AutomationNode[];
  is_active: boolean;
  next_run_at?: string;
  last_run_at?: string;
  last_run_status?: string;
  last_run_result?: string;
  project_id?: string;
  created_at: string;
  updated_at?: string;
}

export interface AgentRunResponse {
  task: Task;
  message: string;
}

export interface UserProfile {
  username: string;
}

export interface SystemHealth {
  status: string;
  database: string;
  pgvector: string;
  groq: string;
  tavily: string;
  brave: string;
  playwright: string;
  scheduler: string;
  websocket: string;
  tool_registry: string;
  permission_manager: string;
  service: string;
  version: string;
}

export interface DiagnosticsInfo {
  cocoa_version: string;
  python_version: string;
  database_backend: string;
  postgres_version: string;
  pgvector_version: string;
  active_llm: string;
  active_research_provider: string;
  browser_runtime: string;
  scheduler_status: string;
  tool_registry: string;
  permission_manager: string;
}

export interface MemoryItem {
  id: string;
  memory_type: string;
  content: string;
  source: string;
  source_reliability?: string;
  project_id?: string;
  session_id?: string;
  importance: number;
  confidence?: number;
  verification_status?: string;
  supersedes_id?: string;
  created_at: string;
  updated_at: string;
}

export interface PendingPermission {
  request_id: string;
  tool_name: string;
  operation: string;
  target?: string;
  resource?: string;
  permission_level: string;
  risk_level?: string;
  reason?: string;
  project_id?: string;
  task_id?: string;
}

export interface RagStatus {
  project_id: string;
  title: string;
  workspace_path?: string;
  indexing_status: string;
  total_files: number;
  total_chunks: number;
  languages: string[];
  last_indexed?: string;
  vector_backend: string;
}

export interface RagChunkResult {
  id: string;
  project_id: string;
  file_path: string;
  language: string;
  chunk_index: number;
  symbol?: string;
  content: string;
  relevance: number;
  match_type: string;
}

export interface RagContextResponse {
  project_id: string;
  query: string;
  chunks: Array<{
    file: string;
    path: string;
    language: string;
    symbol?: string;
    relevance: number;
    content: string;
  }>;
  total_chars: number;
  formatted_context: string;
}
