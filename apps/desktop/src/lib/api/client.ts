// Cocoa API Client (HTTP REST + WebSockets)
// Seamlessly connects Svelte UI to FastAPI backend with graceful fallback to mock data

import {
  mockActiveTask,
  mockRecentProjects,
  mockPlan,
  mockActivity,
  mockSources,
  mockAutomationNodes,
  mockLastRun,
  type ActiveTask,
  type RecentProject,
  type PlanStep,
  type ActivityEntry,
  type ResearchSource,
  type AutomationNode
} from './mock';

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

  async getTasks(): Promise<ActiveTask[]> {
    try {
      const res = await fetch(`${API_BASE_URL}/tasks`);
      if (!res.ok) throw new Error('Failed to fetch tasks');
      const data = await res.json();
      if (data.length === 0) return [mockActiveTask];
      return data.map((t: any) => ({
        id: t.id,
        title: t.title,
        description: t.description || '',
        status: t.status || 'idle',
        icon: t.icon || 'checklist',
      }));
    } catch {
      return [mockActiveTask];
    }
  }

  async getProjects(): Promise<RecentProject[]> {
    try {
      const res = await fetch(`${API_BASE_URL}/projects`);
      if (!res.ok) throw new Error('Failed to fetch projects');
      const data = await res.json();
      if (data.length === 0) return mockRecentProjects;
      return data.map((p: any) => ({
        id: p.id,
        title: p.title,
        icon: p.icon || 'folder_open',
        ago: 'Just now',
      }));
    } catch {
      return mockRecentProjects;
    }
  }

  connectWebSocket(onMessage: (msg: any) => void): () => void {
    try {
      this.ws = new WebSocket(WS_BASE_URL);
      this.ws.onmessage = (evt) => {
        try {
          const payload = JSON.parse(evt.data);
          onMessage(payload);
        } catch (e) {
          console.error('WS parse error:', e);
        }
      };
      this.ws.onerror = () => {
        console.log('WS connection offline — using local state.');
      };
    } catch {
      console.log('WS offline');
    }

    return () => {
      if (this.ws) {
        this.ws.close();
        this.ws = null;
      }
    };
  }
}

export const api = new CocoaApiClient();
