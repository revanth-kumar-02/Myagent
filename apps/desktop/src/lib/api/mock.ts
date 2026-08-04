// ─── Mock Data for Phase 1 (UI Shell) ─────────────────────────────────────

export interface ActiveTask {
  id: string;
  title: string;
  description: string;
  status: 'running' | 'idle' | 'error' | 'done';
  icon: string;
}

export interface RecentProject {
  id: string;
  title: string;
  icon: string;
  ago: string;
}

export interface PlanStep {
  id: string;
  label: string;
  status: 'done' | 'active' | 'pending';
}

export interface ActivityEntry {
  time: string;
  message: string;
  status: 'done' | 'active' | 'info';
  details?: string[];
}

export interface ResearchSource {
  title: string;
  publication: string;
  matchPct: number;
  icon: string;
}

export interface AutomationNode {
  type: 'trigger' | 'agent' | 'notify';
  label: string;
  sublabel: string;
  detail: string;
  steps?: string[];
}

// ─── Home ──────────────────────────────────────────────────────────────────
export const mockActiveTask: ActiveTask = {
  id: '1',
  title: 'Market Research: sustainable materials',
  description: 'Synthesizing recent publications from selected databases...',
  status: 'running',
  icon: 'travel_explore',
};

export const mockRecentProjects: RecentProject[] = [
  { id: '1', title: 'Q4 Roadmap',     icon: 'timeline',     ago: '2h ago'   },
  { id: '2', title: 'Personal CRM',   icon: 'contact_page', ago: 'Yesterday' },
  { id: '3', title: 'Internal Audit', icon: 'fact_check',   ago: 'Oct 12'   },
];

// ─── Tasks ─────────────────────────────────────────────────────────────────
export const mockPlan: PlanStep[] = [
  { id: '1', label: 'Understand project context',  status: 'done'    },
  { id: '2', label: 'Research available options',  status: 'done'    },
  { id: '3', label: 'Compare findings',            status: 'active'  },
  { id: '4', label: 'Form recommendation',         status: 'pending' },
  { id: '5', label: 'Verify',                      status: 'pending' },
];

export const mockActivity: ActivityEntry[] = [
  { time: '10:42:01', message: 'Loaded project context',                              status: 'done'   },
  { time: '10:42:15', message: 'Searched 8 sources (PostgreSQL, MongoDB, DynamoDB…)', status: 'done'   },
  { time: '10:44:30', message: 'Read 5 relevant documents',                           status: 'done'   },
  {
    time: '10:45:12',
    message: 'Comparing findings across read documents...',
    status: 'active',
    details: [
      '→ Evaluating PostgreSQL vs MongoDB for high-write loads...',
      '→ Cross-referencing latency benchmarks...',
    ],
  },
];

// ─── Research ──────────────────────────────────────────────────────────────
export const mockSources: ResearchSource[] = [
  { title: 'Structural Properties of Mycelium Composites in Urban Contexts',   publication: 'Journal of Bio-Architecture, 2023',  matchPct: 98, icon: 'description' },
  { title: 'Passive Cooling Strategies for High-Rise Buildings in the Tropics', publication: 'Global Sustainability Index, 2022',  matchPct: 92, icon: 'public'      },
  { title: 'Embodied Carbon Analysis of Modern Construction Materials',         publication: 'MIT Open Research, 2024',            matchPct: 85, icon: 'science'     },
  { title: 'Case Study: The Oasia Hotel Downtown',                             publication: 'WOHA Architects Brief, 2021',        matchPct: 76, icon: 'architecture' },
];

// ─── Automations ───────────────────────────────────────────────────────────
export const mockAutomationNodes: AutomationNode[] = [
  {
    type: 'trigger',
    label: 'Every Sunday · 6:00 PM',
    sublabel: 'System Scheduler',
    detail: 'TRIGGER',
  },
  {
    type: 'agent',
    label: 'Project Review & Synthesis',
    sublabel: 'Cocoa Primary Core',
    detail: 'AGENT ACTION',
    steps: [
      'Review recent project commits and documentation',
      'Check outstanding high-priority tasks',
      'Identify potential blockers or looming deadlines',
    ],
  },
  {
    type: 'notify',
    label: 'Desktop Notification',
    sublabel: 'Deliver summary if attention is needed',
    detail: 'NOTIFY',
  },
];

export const mockLastRun = {
  date: 'Sunday, Oct 22 · 6:00 PM',
  result: 'Success (No attention needed)',
};
