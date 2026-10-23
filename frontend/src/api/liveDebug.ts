import {
  LiveSystemStatus,
  TestExecutionResult,
  LiveInvestigationResult,
  PatchApprovalResponse
} from '../types/liveDebug';

export const liveDebugApi = {
  async getStatus(): Promise<LiveSystemStatus> {
    const res = await fetch('/api/live/status');
    if (!res.ok) throw new Error('Failed to fetch live system status');
    return res.json();
  },

  async startProcess(): Promise<any> {
    const res = await fetch('/api/live/process/start', { method: 'POST' });
    if (!res.ok) throw new Error('Failed to start live-lab process');
    return res.json();
  },

  async stopProcess(): Promise<any> {
    const res = await fetch('/api/live/process/stop', { method: 'POST' });
    if (!res.ok) throw new Error('Failed to stop live-lab process');
    return res.json();
  },

  async restartProcess(): Promise<any> {
    const res = await fetch('/api/live/process/restart', { method: 'POST' });
    if (!res.ok) throw new Error('Failed to restart live-lab process');
    return res.json();
  },

  async getLogs(limit: number = 80): Promise<{ logs: string[] }> {
    const res = await fetch(`/api/live/logs?limit=${limit}`);
    if (!res.ok) throw new Error('Failed to fetch process logs');
    return res.json();
  },

  async runTests(): Promise<TestExecutionResult> {
    const res = await fetch('/api/live/tests/run', { method: 'POST' });
    if (!res.ok) throw new Error('Failed to execute regression tests');
    return res.json();
  },

  async investigate(): Promise<LiveInvestigationResult> {
    const res = await fetch('/api/live/investigate', { method: 'POST' });
    if (!res.ok) throw new Error('Failed to run live investigation');
    return res.json();
  },

  async approvePatch(params: {
    run_id: string;
    patch_hash: string;
    auth_token: string;
    comment?: string;
  }): Promise<PatchApprovalResponse> {
    const res = await fetch('/api/live/patch/approve', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(params)
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || 'Failed to approve patch');
    }
    return res.json();
  },

  async rejectPatch(run_id: string, reason?: string): Promise<any> {
    const res = await fetch('/api/live/patch/reject', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ run_id, reason })
    });
    return res.json();
  }
};
