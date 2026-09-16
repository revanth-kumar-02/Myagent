// Cocoa API Client (HTTP REST + WebSockets)
import type {
  Task,
  TaskStep,
  ActivityLog,
  Project,
  Workspace,
  ScanWorkspaceResponse,
  ResearchSession,
  ResearchSource,
  ResearchFinding,
  Automation,
  AutomationRun,
  AgentRunResponse,
  UserProfile,
  SystemHealth,
  DiagnosticsInfo,
  MemoryItem,
  RagStatus,
  RagChunkResult,
  RagContextResponse,
} from './types';

const API_BASE_URL = 'http://localhost:8000/api/v1';
const WS_BASE_URL = 'ws://localhost:8000/ws';

export class CocoaApiClient {
  private ws: WebSocket | null = null;

  async checkHealth(): Promise<boolean> {
    try {
      const res = await fetch(`${API_BASE_URL}/health`);
      return res.ok;
    } catch {
      return false;
    }
  }

  async runAgent(goal: string, projectId?: string): Promise<AgentRunResponse> {
    const res = await fetch(`${API_BASE_URL}/agent/run`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ goal, project_id: projectId }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ message: 'Failed to run agent' }));
      throw new Error(err.detail || err.message || 'Failed to start agent goal');
    }
    return res.json();
  }

  async getTasks(): Promise<Task[]> {
    const res = await fetch(`${API_BASE_URL}/tasks`);
    if (!res.ok) throw new Error('Failed to fetch tasks');
    return res.json();
  }

  async getTask(id: string): Promise<Task> {
    const res = await fetch(`${API_BASE_URL}/tasks/${id}`);
    if (!res.ok) throw new Error(`Task ${id} not found`);
    return res.json();
  }

  async getTaskSteps(taskId: string): Promise<TaskStep[]> {
    const res = await fetch(`${API_BASE_URL}/tasks/${taskId}/steps`);
    if (!res.ok) throw new Error(`Failed to fetch steps for task ${taskId}`);
    return res.json();
  }

  async getTaskActivity(taskId: string): Promise<ActivityLog[]> {
    const res = await fetch(`${API_BASE_URL}/tasks/${taskId}/activity`);
    if (!res.ok) throw new Error(`Failed to fetch activity for task ${taskId}`);
    return res.json();
  }

  async getWorkspace(): Promise<Workspace> {
    let res: Response;
    try {
      res = await fetch(`${API_BASE_URL}/projects/workspace`);
    } catch {
      throw new Error('Could not connect to Cocoa Agent.');
    }
    if (!res.ok) throw new Error('Failed to fetch workspace');
    return res.json();
  }

  async setWorkspace(path: string): Promise<ScanWorkspaceResponse> {
    let res: Response;
    try {
      res = await fetch(`${API_BASE_URL}/projects/workspace`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ path }),
      });
    } catch {
      throw new Error('Could not connect to Cocoa Agent.');
    }
    if (!res.ok) {
      const err = await res.json().catch(() => ({ message: 'Failed to set workspace' }));
      throw new Error(err.detail || err.message || 'Failed to set workspace directory');
    }
    return res.json();
  }

  async scanWorkspace(): Promise<ScanWorkspaceResponse> {
    let res: Response;
    try {
      res = await fetch(`${API_BASE_URL}/projects/scan`, { method: 'POST' });
    } catch {
      throw new Error('Could not connect to Cocoa Agent.');
    }
    if (!res.ok) {
      const err = await res.json().catch(() => ({ message: 'Failed to scan workspace' }));
      throw new Error(err.detail || err.message || 'Failed to scan workspace');
    }
    return res.json();
  }

  async getProjects(): Promise<Project[]> {
    let res: Response;
    try {
      res = await fetch(`${API_BASE_URL}/projects`);
    } catch {
      throw new Error('Could not connect to Cocoa Agent.');
    }
    if (!res.ok) throw new Error('Failed to fetch projects');
    return res.json();
  }

  async getProject(id: string): Promise<Project> {
    let res: Response;
    try {
      res = await fetch(`${API_BASE_URL}/projects/${id}`);
    } catch {
      throw new Error('Could not connect to Cocoa Agent.');
    }
    if (!res.ok) throw new Error(`Project ${id} not found`);
    return res.json();
  }

  // ─── Research Engine API ────────────────────────────────────
  async runResearch(query: string, projectId?: string): Promise<ResearchSession> {
    const res = await fetch(`${API_BASE_URL}/research/run`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ query, project_id: projectId }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ message: 'Failed to start research' }));
      throw new Error(err.detail || err.message || 'Failed to start research task');
    }
    return res.json();
  }

  async getResearchSessions(): Promise<ResearchSession[]> {
    const res = await fetch(`${API_BASE_URL}/research`);
    if (!res.ok) throw new Error('Failed to fetch research sessions');
    return res.json();
  }

  async getResearchSession(id: string): Promise<ResearchSession> {
    const res = await fetch(`${API_BASE_URL}/research/${id}`);
    if (!res.ok) throw new Error(`Research session ${id} not found`);
    return res.json();
  }

  async getResearchSources(sessionId: string): Promise<ResearchSource[]> {
    const res = await fetch(`${API_BASE_URL}/research/${sessionId}/sources`);
    if (!res.ok) throw new Error(`Failed to fetch sources for session ${sessionId}`);
    return res.json();
  }

  async getResearchFindings(sessionId: string): Promise<ResearchFinding[]> {
    const res = await fetch(`${API_BASE_URL}/research/${sessionId}/findings`);
    if (!res.ok) throw new Error(`Failed to fetch findings for session ${sessionId}`);
    return res.json();
  }

  async cancelResearch(sessionId: string): Promise<ResearchSession> {
    const res = await fetch(`${API_BASE_URL}/research/${sessionId}/cancel`, { method: 'POST' });
    if (!res.ok) throw new Error(`Failed to cancel research session ${sessionId}`);
    return res.json();
  }

  async getAutomations(): Promise<Automation[]> {
    const res = await fetch(`${API_BASE_URL}/automations`);
    if (!res.ok) throw new Error('Failed to fetch automations');
    return res.json();
  }

  async createAutomation(autoData: Partial<Automation>): Promise<Automation> {
    const res = await fetch(`${API_BASE_URL}/automations`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(autoData),
    });
    if (!res.ok) throw new Error('Failed to create automation');
    return res.json();
  }

  async updateAutomation(id: string, autoData: Partial<Automation>): Promise<Automation> {
    const res = await fetch(`${API_BASE_URL}/automations/${id}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(autoData),
    });
    if (!res.ok) throw new Error(`Failed to update automation ${id}`);
    return res.json();
  }

  async toggleAutomation(id: string): Promise<Automation> {
    const res = await fetch(`${API_BASE_URL}/automations/${id}/toggle`, { method: 'POST' });
    if (!res.ok) throw new Error(`Failed to toggle automation ${id}`);
    return res.json();
  }

  async triggerAutomation(id: string): Promise<{ message: string; automation_id: string }> {
    const res = await fetch(`${API_BASE_URL}/automations/${id}/trigger`, { method: 'POST' });
    if (!res.ok) throw new Error(`Failed to trigger automation ${id}`);
    return res.json();
  }

  async deleteAutomation(id: string): Promise<{ message: string; automation_id: string }> {
    const res = await fetch(`${API_BASE_URL}/automations/${id}`, { method: 'DELETE' });
    if (!res.ok) throw new Error(`Failed to delete automation ${id}`);
    return res.json();
  }

  // ─── Settings API ────────────────────────────────────────────
  async getSettings(): Promise<Array<{ key: string; value: string; updated_at: string }>> {
    const res = await fetch(`${API_BASE_URL}/settings`);
    if (!res.ok) throw new Error('Failed to fetch settings');
    return res.json();
  }

  async updateSetting(key: string, value: string): Promise<any> {
    const res = await fetch(`${API_BASE_URL}/settings`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ key, value }),
    });
    if (!res.ok) throw new Error(`Failed to update setting '${key}'`);
    return res.json();
  }

  async updateSettingsBulk(settingsMap: Record<string, string>): Promise<any> {
    const res = await fetch(`${API_BASE_URL}/settings/bulk`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ settings: settingsMap }),
    });
    if (!res.ok) throw new Error('Failed to save settings');
    return res.json();
  }

  connectWebSocket(onMessage: (msg: any) => void): () => void {
    try {
      this.ws = new WebSocket(WS_BASE_URL);
      this.ws.onmessage = (evt) => {
        try {
          const payload = JSON.parse(evt.data);
          onMessage(payload);
        } catch (e) {
          console.error('WebSocket payload parse error:', e);
        }
      };
      this.ws.onerror = (e) => {
        console.warn('WebSocket connection error:', e);
      };
    } catch (e) {
      console.warn('WebSocket setup error:', e);
    }

    return () => {
      if (this.ws) {
        this.ws.close();
        this.ws = null;
      }
    };
  }

  async getReadiness(): Promise<SystemHealth> {
    try {
      const res = await fetch(`${API_BASE_URL}/readyz`);
      if (!res.ok) throw new Error('System readiness check failed');
      return res.json();
    } catch {
      return {
        status: 'degraded',
        database: 'disconnected',
        pgvector: 'not_configured',
        groq: 'not_configured',
        tavily: 'not_configured',
        brave: 'not_configured',
        playwright: 'unavailable',
        scheduler: 'idle',
        websocket: 'disconnected',
        tool_registry: 'degraded',
        permission_manager: 'active',
        service: 'Cocoa Agent Core',
        version: '0.1.0',
      };
    }
  }

  async getDiagnostics(): Promise<DiagnosticsInfo> {
    const res = await fetch(`${API_BASE_URL}/diagnostics`);
    if (!res.ok) throw new Error('Failed to fetch diagnostics');
    return res.json();
  }

  async getMemories(projectId?: string): Promise<MemoryItem[]> {
    const url = projectId ? `${API_BASE_URL}/memories?project_id=${projectId}` : `${API_BASE_URL}/memories`;
    const res = await fetch(url);
    if (!res.ok) throw new Error('Failed to fetch memories');
    return res.json();
  }

  async searchMemories(query: string, projectId?: string): Promise<MemoryItem[]> {
    const res = await fetch(`${API_BASE_URL}/memories/search`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ query, project_id: projectId }),
    });
    if (!res.ok) throw new Error('Failed to search memories');
    return res.json();
  }

  async verifyMemory(memoryId: string): Promise<MemoryItem> {
    const res = await fetch(`${API_BASE_URL}/memories/${memoryId}/verify`, { method: 'POST' });
    if (!res.ok) throw new Error('Failed to verify memory');
    return res.json();
  }

  async supersedeMemory(memoryId: string, newContent: string, projectId?: string): Promise<MemoryItem> {
    const res = await fetch(`${API_BASE_URL}/memories/${memoryId}/supersede`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ new_content: newContent, project_id: projectId }),
    });
    if (!res.ok) throw new Error('Failed to supersede memory');
    return res.json();
  }

  async archiveMemory(memoryId: string): Promise<MemoryItem> {
    const res = await fetch(`${API_BASE_URL}/memories/${memoryId}/archive`, { method: 'POST' });
    if (!res.ok) throw new Error('Failed to archive memory');
    return res.json();
  }

  async refreshProjectKnowledge(projectId: string): Promise<any> {
    const res = await fetch(`${API_BASE_URL}/projects/${projectId}/refresh-knowledge`, { method: 'POST' });
    if (!res.ok) throw new Error('Failed to refresh project knowledge');
    return res.json();
  }

  async respondPermission(requestId: string, granted: boolean, scope: string = 'ONCE'): Promise<{ status: string; request_id: string; granted: boolean; scope: string }> {
    const res = await fetch(`${API_BASE_URL}/permissions/respond`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ request_id: requestId, granted, scope: scope.toUpperCase() })
    });
    if (!res.ok) throw new Error('Failed to respond to permission request');
    return res.json();
  }

  async getAuditLogs(limit: number = 50): Promise<ActivityLog[]> {
    const res = await fetch(`${API_BASE_URL}/permissions/audit-logs?limit=${limit}`);
    if (!res.ok) throw new Error('Failed to fetch permission audit logs');
    return res.json();
  }

  async getProfile(): Promise<UserProfile> {
    try {
      const res = await fetch(`${API_BASE_URL}/profile`);
      if (res.ok) {
        return await res.json();
      }
    } catch {
      // Ignore backend connection errors, fallback gracefully
    }
    return { username: 'User' };
  }

  async updateProfile(username: string): Promise<UserProfile> {
    const res = await fetch(`${API_BASE_URL}/profile`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username }),
    });
    if (!res.ok) throw new Error('Failed to update profile');
    return res.json();
  }

  async enableAutomation(id: string): Promise<Automation> {
    const res = await fetch(`${API_BASE_URL}/automations/${id}/enable`, { method: 'POST' });
    if (!res.ok) throw new Error('Failed to enable automation');
    return res.json();
  }

  async disableAutomation(id: string): Promise<Automation> {
    const res = await fetch(`${API_BASE_URL}/automations/${id}/disable`, { method: 'POST' });
    if (!res.ok) throw new Error('Failed to disable automation');
    return res.json();
  }

  async runAutomation(id: string): Promise<any> {
    const res = await fetch(`${API_BASE_URL}/automations/${id}/run`, { method: 'POST' });
    if (!res.ok) throw new Error('Failed to run automation');
    return res.json();
  }

  async getAutomationRuns(id: string): Promise<AutomationRun[]> {
    const res = await fetch(`${API_BASE_URL}/automations/${id}/runs`);
    if (!res.ok) throw new Error('Failed to fetch automation runs');
    return res.json();
  }

  async parseNLAutomation(prompt: string, projectId?: string): Promise<any> {
    const res = await fetch(`${API_BASE_URL}/automations/parse-nl`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ prompt, project_id: projectId }),
    });
    if (!res.ok) throw new Error('Failed to parse natural language automation');
    return res.json();
  }

  // ─── Project RAG API ─────────────────────────────────────────
  async getRagStatus(projectId: string): Promise<RagStatus> {
    const res = await fetch(`${API_BASE_URL}/rag/status?project_id=${projectId}`);
    if (!res.ok) throw new Error(`Failed to fetch RAG status for project ${projectId}`);
    return res.json();
  }

  async indexProjectRag(projectId: string, workspacePath?: string, forceFull: boolean = false): Promise<any> {
    const res = await fetch(`${API_BASE_URL}/rag/index`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        project_id: projectId,
        workspace_path: workspacePath,
        force_full: forceFull,
      }),
    });
    if (!res.ok) throw new Error(`Failed to index RAG for project ${projectId}`);
    return res.json();
  }

  async refreshProjectRag(projectId: string): Promise<any> {
    const res = await fetch(`${API_BASE_URL}/rag/refresh`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ project_id: projectId }),
    });
    if (!res.ok) throw new Error(`Failed to refresh RAG for project ${projectId}`);
    return res.json();
  }

  async searchRag(
    projectId: string,
    query: string,
    limit: number = 10,
    language?: string,
    filePathFilter?: string
  ): Promise<RagChunkResult[]> {
    const res = await fetch(`${API_BASE_URL}/rag/search`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        project_id: projectId,
        query,
        limit,
        language,
        file_path_filter: filePathFilter,
      }),
    });
    if (!res.ok) throw new Error('Failed to perform RAG search');
    return res.json();
  }

  async getRagContext(projectId: string, query: string, maxChars: number = 12000): Promise<RagContextResponse> {
    const res = await fetch(`${API_BASE_URL}/rag/context`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        project_id: projectId,
        query,
        max_chars: maxChars,
      }),
    });
    if (!res.ok) throw new Error('Failed to build RAG context');
    return res.json();
  }
}

export const api = new CocoaApiClient();
