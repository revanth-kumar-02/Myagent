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
  AgentRunResponse,
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

  async respondPermission(requestId: string, granted: boolean): Promise<{ status: string; request_id: string; granted: boolean }> {
    const res = await fetch(`${API_BASE_URL}/filesystem/permissions/respond`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ request_id: requestId, granted })
    });
    if (!res.ok) throw new Error('Failed to respond to permission request');
    return res.json();
  }

  async browseDirectory(path: string = '.'): Promise<any> {
    const res = await fetch(`${API_BASE_URL}/filesystem/browse?path=${encodeURIComponent(path)}`);
    if (!res.ok) throw new Error(`Failed to browse directory: ${path}`);
    return res.json();
  }
}

export const api = new CocoaApiClient();
