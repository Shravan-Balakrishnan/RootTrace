/**
 * RootTrace Live — Mobile API client
 *
 * Reads the backend host from the EXPO_PUBLIC_API_BASE_URL environment variable.
 * For physical-device LAN testing, set EXPO_PUBLIC_API_BASE_URL in a .env.local file:
 *
 *   EXPO_PUBLIC_API_BASE_URL=http://192.168.x.x:8000
 *
 * Never hardcode localhost here.
 */

let customApiBase: string | null = null;

export function getApiBase(): string {
  if (customApiBase !== null && customApiBase.trim().length > 0) {
    return customApiBase.trim().replace(/\/$/, '');
  }
  const envUrl = process.env.EXPO_PUBLIC_API_BASE_URL;
  if (envUrl && envUrl.trim().length > 0) {
    return envUrl.trim().replace(/\/$/, '');
  }
  return 'http://192.168.2.19:8000';
}

export function setApiBase(url: string) {
  customApiBase = url.trim().replace(/\/$/, '');
}

async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const base = getApiBase();
  const url = `${base}${path}`;
  try {
    const res = await fetch(url, {
      ...init,
      headers: {
        'Content-Type': 'application/json',
        ...(init?.headers ?? {}),
      },
    });
    if (!res.ok) {
      const body = await res.text().catch(() => '');
      throw new Error(`${res.status} ${res.statusText}: ${body}`);
    }
    return res.json() as Promise<T>;
  } catch (err: any) {
    throw new Error(`${err.message ?? 'Network error'} (Target: ${url})`);
  }
}

// ─── Types ────────────────────────────────────────────────────────────────────

export interface LiveStatus {
  process: {
    running: boolean;
    pid?: number;
    uptime_seconds?: number;
  };
  health: {
    healthy: boolean;
    status_code?: number;
    latency_ms?: number;
  };
  application: string;
  timestamp: string;
}

export interface TestExecutionResult {
  passed: number;
  failed: number;
  errors: number;
  duration_seconds: number;
  output?: string;
}

export interface InvestigationResult {
  run_id: string;
  diagnosis?: string;
  hypotheses: Array<{ id: string; text: string; confidence: number }>;
  proposed_patch?: {
    patch_hash: string;
    summary: string;
    diff: string;
  };
  agent_traces: Array<{ agent: string; step: string; output: string }>;
  abstained?: boolean;
  abstention_reason?: string;
  evidence_collected: Array<{ type: string; summary: string }>;
}

export interface AuditRecord {
  timestamp: string;
  action?: string;
  event_type?: string;
  approver?: string;
  operator?: string;
  approved?: boolean;
  comment?: string;
}

export interface PostmortemRecord {
  incident_id?: string;
  title?: string;
  severity?: string;
  affected_services?: string[];
}

// ─── API Client ───────────────────────────────────────────────────────────────

export const api = {
  /** Live-lab process, health, and metadata */
  async getStatus(): Promise<LiveStatus> {
    return apiFetch<LiveStatus>('/api/live/status');
  },

  async startProcess(): Promise<void> {
    await apiFetch('/api/live/process/start', { method: 'POST' });
  },

  async stopProcess(): Promise<void> {
    await apiFetch('/api/live/process/stop', { method: 'POST' });
  },

  async restartProcess(): Promise<void> {
    await apiFetch('/api/live/process/restart', { method: 'POST' });
  },

  async getLogs(limit = 60): Promise<{ logs: string[] }> {
    return apiFetch<{ logs: string[] }>(`/api/live/logs?limit=${limit}`);
  },

  /** Test execution */
  async runTests(): Promise<TestExecutionResult> {
    return apiFetch<TestExecutionResult>('/api/live/tests/run', { method: 'POST' });
  },

  /** Investigation */
  async investigate(): Promise<InvestigationResult> {
    return apiFetch<InvestigationResult>('/api/live/investigate', { method: 'POST' });
  },

  /** Patch approval */
  async approvePatch(params: {
    run_id: string;
    patch_hash: string;
    auth_token: string;
    comment?: string;
  }): Promise<any> {
    return apiFetch('/api/live/patch/approve', {
      method: 'POST',
      body: JSON.stringify(params),
    });
  },

  async rejectPatch(run_id: string, reason?: string): Promise<any> {
    return apiFetch('/api/live/patch/reject', {
      method: 'POST',
      body: JSON.stringify({ run_id, reason }),
    });
  },

  /** Audit log */
  async getAuditRecords(): Promise<AuditRecord[]> {
    const data = await apiFetch<any>('/api/live/audit');
    return Array.isArray(data) ? data : (data.records ?? []);
  },

  /** Historical postmortems */
  async getPostmortems(): Promise<PostmortemRecord[]> {
    const data = await apiFetch<any>('/api/memory/postmortems');
    return Array.isArray(data) ? data : [];
  },

  /** Auth */
  async login(email: string, password: string): Promise<{
    session_token: string;
    name: string;
    role: string;
    expires_at: string;
  }> {
    return apiFetch('/api/auth/session', {
      method: 'POST',
      body: JSON.stringify({ email, password }),
    });
  },
};
