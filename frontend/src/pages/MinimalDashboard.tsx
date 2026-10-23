import React, { useState, useEffect, useCallback } from 'react';
import {
  Activity, AlertCircle, CheckCircle2, Clock, Cpu, ExternalLink,
  FlaskConical, GitBranch, Layers, Play, RefreshCw, Settings,
  ShieldCheck, Square, Terminal, Zap, Search, RotateCcw,
  ChevronRight, ArrowUpRight, XCircle
} from 'lucide-react';
import { LiveDebugConsole } from './LiveDebugConsole';

// ─── Types ────────────────────────────────────────────────────────────────────
interface LiveStatus {
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

interface NavItem {
  id: string;
  label: string;
  icon: React.ReactNode;
}

// ─── Utility ──────────────────────────────────────────────────────────────────
function formatUptime(seconds?: number): string {
  if (!seconds) return '—';
  if (seconds < 60) return `${Math.floor(seconds)}s`;
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m ${Math.floor(seconds % 60)}s`;
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  return `${h}h ${m}m`;
}

function timeAgo(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime();
  const s = Math.floor(diff / 1000);
  if (s < 5) return 'just now';
  if (s < 60) return `${s}s ago`;
  if (s < 3600) return `${Math.floor(s / 60)}m ago`;
  return `${Math.floor(s / 3600)}h ago`;
}

// ─── StatusDot ────────────────────────────────────────────────────────────────
const StatusDot: React.FC<{ ok: boolean; pulse?: boolean }> = ({ ok, pulse }) => (
  <span style={{ position: 'relative', display: 'inline-flex', alignItems: 'center', justifyContent: 'center', width: 10, height: 10 }}>
    {ok && pulse && (
      <span style={{
        position: 'absolute', inset: 0, borderRadius: '50%',
        background: '#16a34a', opacity: 0.35,
        animation: 'rt-ping 2s cubic-bezier(0,0,0.2,1) infinite',
      }} />
    )}
    <span style={{
      width: 8, height: 8, borderRadius: '50%',
      background: ok ? '#16a34a' : '#dc2626',
      display: 'inline-block', flexShrink: 0,
    }} />
  </span>
);

// ─── MetricCard ───────────────────────────────────────────────────────────────
const MetricCard: React.FC<{
  label: string;
  value: React.ReactNode;
  sub?: string;
  icon: React.ReactNode;
  accent?: 'green' | 'red' | 'blue' | 'amber';
  onClick?: () => void;
}> = ({ label, value, sub, icon, accent = 'blue', onClick }) => {
  const accents: Record<string, { bg: string; border: string; iconColor: string }> = {
    green: { bg: '#f0fdf4', border: '#bbf7d0', iconColor: '#16a34a' },
    red:   { bg: '#fff1f2', border: '#fecdd3', iconColor: '#dc2626' },
    blue:  { bg: '#eff6ff', border: '#bfdbfe', iconColor: '#2563eb' },
    amber: { bg: '#fffbeb', border: '#fed7aa', iconColor: '#d97706' },
  };
  const a = accents[accent];

  return (
    <div
      onClick={onClick}
      style={{
        background: '#fff', border: '1px solid #e5e7eb', borderRadius: 12,
        padding: '20px 22px', display: 'flex', flexDirection: 'column', gap: 10,
        cursor: onClick ? 'pointer' : 'default', position: 'relative', overflow: 'hidden',
        transition: 'box-shadow 0.15s, border-color 0.15s',
      }}
      onMouseEnter={e => {
        if (onClick) {
          (e.currentTarget as HTMLDivElement).style.boxShadow = '0 4px 16px rgba(0,0,0,0.07)';
          (e.currentTarget as HTMLDivElement).style.borderColor = '#d1d5db';
        }
      }}
      onMouseLeave={e => {
        (e.currentTarget as HTMLDivElement).style.boxShadow = 'none';
        (e.currentTarget as HTMLDivElement).style.borderColor = '#e5e7eb';
      }}
    >
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
        <span style={{ fontSize: 11, fontWeight: 600, color: '#6b7280', textTransform: 'uppercase', letterSpacing: '0.06em' }}>
          {label}
        </span>
        <span style={{
          background: a.bg, border: `1px solid ${a.border}`,
          borderRadius: 7, padding: '4px 7px', color: a.iconColor,
          display: 'flex', alignItems: 'center',
        }}>
          {icon}
        </span>
      </div>
      <div style={{ fontSize: 26, fontWeight: 700, color: '#111827', lineHeight: 1.2 }}>{value}</div>
      {sub && <div style={{ fontSize: 11, color: '#9ca3af' }}>{sub}</div>}
      {onClick && <ArrowUpRight size={13} style={{ position: 'absolute', top: 14, right: 14, color: '#d1d5db' }} />}
    </div>
  );
};

// ─── SectionHeader ────────────────────────────────────────────────────────────
const SectionHeader: React.FC<{ title: string; sub?: string; action?: React.ReactNode }> = ({ title, sub, action }) => (
  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-end', marginBottom: 14 }}>
    <div>
      <h2 style={{ fontSize: 15, fontWeight: 600, color: '#111827', margin: 0 }}>{title}</h2>
      {sub && <p style={{ fontSize: 12, color: '#9ca3af', marginTop: 3, marginBottom: 0 }}>{sub}</p>}
    </div>
    {action}
  </div>
);

// ─── Btn ──────────────────────────────────────────────────────────────────────
const Btn: React.FC<{
  children: React.ReactNode;
  onClick?: () => void;
  variant?: 'primary' | 'ghost' | 'danger';
  icon?: React.ReactNode;
  disabled?: boolean;
}> = ({ children, onClick, variant = 'ghost', icon, disabled }) => {
  const s = {
    primary: { bg: '#2563eb', color: '#fff', border: '#2563eb', hov: '#1d4ed8' },
    ghost:   { bg: '#fff',    color: '#374151', border: '#e5e7eb', hov: '#f9fafb' },
    danger:  { bg: '#fff',    color: '#dc2626', border: '#fecdd3', hov: '#fff1f2' },
  }[variant];

  return (
    <button
      onClick={onClick}
      disabled={disabled}
      style={{
        display: 'flex', alignItems: 'center', gap: 6, padding: '7px 14px',
        borderRadius: 8, border: `1px solid ${s.border}`, background: s.bg,
        color: s.color, fontSize: 13, fontWeight: 500, cursor: disabled ? 'not-allowed' : 'pointer',
        opacity: disabled ? 0.5 : 1, fontFamily: 'inherit', transition: 'background 0.1s',
      }}
      onMouseEnter={e => { if (!disabled) (e.currentTarget as HTMLButtonElement).style.background = s.hov; }}
      onMouseLeave={e => { if (!disabled) (e.currentTarget as HTMLButtonElement).style.background = s.bg; }}
    >
      {icon}{children}
    </button>
  );
};

// ─── HealthBanner ─────────────────────────────────────────────────────────────
const HealthBanner: React.FC<{ status: LiveStatus | null; onRefresh: () => void }> = ({ status, onRefresh }) => {
  const running = status?.process?.running ?? false;
  const healthy = status?.health?.healthy ?? false;
  const ok = running && healthy;
  return (
    <div style={{
      background: ok ? '#f0fdf4' : running ? '#fffbeb' : '#fff1f2',
      border: `1px solid ${ok ? '#bbf7d0' : running ? '#fed7aa' : '#fecdd3'}`,
      borderRadius: 12, padding: '13px 20px',
      display: 'flex', justifyContent: 'space-between', alignItems: 'center',
      marginBottom: 22,
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
        <StatusDot ok={ok} pulse={ok} />
        <div>
          <div style={{ fontSize: 13, fontWeight: 600, color: '#111827' }}>
            {ok ? 'Live-lab application is healthy' : running ? 'Process running — health check failing' : 'Live-lab process is offline'}
          </div>
          <div style={{ fontSize: 11, color: '#6b7280', marginTop: 2 }}>
            {status
              ? `Uptime ${formatUptime(status.process?.uptime_seconds)} · HTTP ${status.health?.status_code ?? '—'} · ${status.health?.latency_ms != null ? status.health.latency_ms + 'ms · ' : ''}Updated ${timeAgo(status.timestamp)}`
              : 'Connecting to backend…'}
          </div>
        </div>
      </div>
      <button
        onClick={onRefresh}
        style={{
          background: 'transparent', border: 'none', cursor: 'pointer',
          color: '#6b7280', display: 'flex', alignItems: 'center', gap: 4,
          fontSize: 12, fontWeight: 500, fontFamily: 'inherit',
        }}
      >
        <RefreshCw size={13} /> Refresh
      </button>
    </div>
  );
};

// ─── ProcessControls ──────────────────────────────────────────────────────────
const ProcessControls: React.FC<{
  status: LiveStatus | null;
  onStart: () => Promise<void>;
  onStop: () => Promise<void>;
  onRestart: () => Promise<void>;
  loading: boolean;
}> = ({ status, onStart, onStop, onRestart, loading }) => {
  const running = status?.process?.running ?? false;
  return (
    <div style={{
      background: '#fff', border: '1px solid #e5e7eb', borderRadius: 12,
      padding: '14px 20px', display: 'flex', justifyContent: 'space-between', alignItems: 'center',
      marginBottom: 22,
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
        <div style={{
          width: 34, height: 34, borderRadius: 8, background: '#f3f4f6',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
        }}>
          <Cpu size={16} color="#374151" />
        </div>
        <div>
          <div style={{ fontSize: 13, fontWeight: 600, color: '#111827' }}>live-lab process</div>
          <div style={{ fontSize: 11, color: '#6b7280' }}>
            PID: {status?.process?.pid ?? '—'} · Port 5001 · Flask checkout service
          </div>
        </div>
      </div>
      <div style={{ display: 'flex', gap: 8 }}>
        {!running ? (
          <Btn variant="primary" icon={<Play size={13} />} onClick={onStart} disabled={loading}>Start</Btn>
        ) : (
          <>
            <Btn icon={<RotateCcw size={13} />} onClick={onRestart} disabled={loading}>Restart</Btn>
            <Btn variant="danger" icon={<Square size={13} />} onClick={onStop} disabled={loading}>Stop</Btn>
          </>
        )}
      </div>
    </div>
  );
};

// ─── ApprovalQueueBanner ──────────────────────────────────────────────────────
const ApprovalQueueBanner: React.FC<{ count: number; onClick: () => void }> = ({ count, onClick }) => {
  if (count === 0) return null;
  return (
    <div
      onClick={onClick}
      style={{
        background: '#fffbeb', border: '1px solid #fde68a', borderRadius: 12,
        padding: '12px 20px', display: 'flex', justifyContent: 'space-between', alignItems: 'center',
        cursor: 'pointer', marginBottom: 22, transition: 'box-shadow 0.15s',
      }}
      onMouseEnter={e => { (e.currentTarget as HTMLDivElement).style.boxShadow = '0 2px 8px rgba(0,0,0,0.05)'; }}
      onMouseLeave={e => { (e.currentTarget as HTMLDivElement).style.boxShadow = 'none'; }}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
        <ShieldCheck size={16} color="#d97706" />
        <div>
          <div style={{ fontSize: 13, fontWeight: 600, color: '#111827' }}>
            {count} patch proposal{count > 1 ? 's' : ''} awaiting approval
          </div>
          <div style={{ fontSize: 11, color: '#6b7280' }}>Human review required before any changes are applied</div>
        </div>
      </div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 4, fontSize: 12, color: '#d97706', fontWeight: 500 }}>
        Review <ChevronRight size={14} />
      </div>
    </div>
  );
};

// ─── IncidentHistoryPanel ─────────────────────────────────────────────────────
const IncidentHistoryPanel: React.FC = () => {
  const [postmortems, setPostmortems] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch('/api/memory/postmortems')
      .then(r => r.json())
      .then(data => setPostmortems(Array.isArray(data) ? data.slice(0, 20) : []))
      .catch(() => setPostmortems([]))
      .finally(() => setLoading(false));
  }, []);

  if (loading) return (
    <div style={{ textAlign: 'center', padding: 60, color: '#9ca3af', fontSize: 13 }}>Loading…</div>
  );
  if (postmortems.length === 0) return (
    <div style={{ textAlign: 'center', padding: 60 }}>
      <CheckCircle2 size={38} color="#16a34a" style={{ display: 'block', margin: '0 auto 12px' }} />
      <div style={{ fontSize: 14, fontWeight: 600, color: '#374151' }}>No incidents on record</div>
      <div style={{ fontSize: 12, color: '#9ca3af', marginTop: 4 }}>Run an investigation to generate a postmortem</div>
    </div>
  );

  return (
    <div>
      <SectionHeader title="Incident History" sub={`${postmortems.length} records`} />
      <div style={{ background: '#fff', border: '1px solid #e5e7eb', borderRadius: 12, overflow: 'hidden' }}>
        {postmortems.map((pm, i) => (
          <div key={i} style={{
            padding: '14px 20px',
            borderBottom: i < postmortems.length - 1 ? '1px solid #f3f4f6' : 'none',
            display: 'flex', justifyContent: 'space-between', alignItems: 'center',
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
              <div style={{
                width: 8, height: 8, borderRadius: '50%', flexShrink: 0,
                background: pm.severity === 'HIGH' ? '#dc2626' : pm.severity === 'MEDIUM' ? '#f59e0b' : '#10b981',
              }} />
              <div>
                <div style={{ fontSize: 13, fontWeight: 500, color: '#111827' }}>
                  {pm.title || pm.incident_id || 'Untitled incident'}
                </div>
                <div style={{ fontSize: 11, color: '#9ca3af', marginTop: 2 }}>
                  {pm.affected_services?.join(', ') || '—'} · {pm.severity || '—'}
                </div>
              </div>
            </div>
            <span style={{
              fontSize: 10, fontWeight: 600, letterSpacing: '0.04em',
              background: '#f0fdf4', color: '#15803d', border: '1px solid #bbf7d0',
              borderRadius: 4, padding: '2px 7px', whiteSpace: 'nowrap',
            }}>RESOLVED</span>
          </div>
        ))}
      </div>
    </div>
  );
};

// ─── AuditLogPanel ────────────────────────────────────────────────────────────
const AuditLogPanel: React.FC = () => {
  const [records, setRecords] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch('/api/live/audit')
      .then(r => r.json())
      .then(data => {
        const list = Array.isArray(data) ? data : (data.records ?? []);
        setRecords(list.slice(0, 25));
      })
      .catch(() => setRecords([]))
      .finally(() => setLoading(false));
  }, []);

  if (loading) return (
    <div style={{ textAlign: 'center', padding: 60, color: '#9ca3af', fontSize: 13 }}>Loading…</div>
  );
  if (records.length === 0) return (
    <div style={{ textAlign: 'center', padding: 60 }}>
      <ShieldCheck size={38} color="#2563eb" style={{ display: 'block', margin: '0 auto 12px' }} />
      <div style={{ fontSize: 14, fontWeight: 600, color: '#374151' }}>No audit records yet</div>
      <div style={{ fontSize: 12, color: '#9ca3af', marginTop: 4 }}>Patch approvals and rejections will appear here</div>
    </div>
  );

  return (
    <div>
      <SectionHeader title="Operator Audit Log" sub={`${records.length} records`} />
      <div style={{ background: '#fff', border: '1px solid #e5e7eb', borderRadius: 12, overflow: 'hidden' }}>
        {records.map((rec, i) => (
          <div key={i} style={{
            padding: '14px 20px',
            borderBottom: i < records.length - 1 ? '1px solid #f3f4f6' : 'none',
            display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start',
          }}>
            <div>
              <div style={{ fontSize: 13, fontWeight: 500, color: '#111827' }}>
                {rec.action ?? rec.event_type ?? 'Patch review'}
              </div>
              <div style={{ fontSize: 11, color: '#9ca3af', marginTop: 2 }}>
                {rec.approver ?? rec.operator ?? '—'} · {rec.timestamp ? timeAgo(rec.timestamp) : '—'}
              </div>
              {rec.comment && (
                <div style={{ fontSize: 11, color: '#6b7280', marginTop: 3, fontStyle: 'italic' }}>"{rec.comment}"</div>
              )}
            </div>
            <span style={{
              fontSize: 10, fontWeight: 600, letterSpacing: '0.04em',
              background: rec.approved ? '#f0fdf4' : '#fff1f2',
              color: rec.approved ? '#15803d' : '#b91c1c',
              border: `1px solid ${rec.approved ? '#bbf7d0' : '#fecdd3'}`,
              borderRadius: 4, padding: '2px 7px', flexShrink: 0, marginTop: 2,
            }}>
              {rec.approved ? 'APPROVED' : 'REJECTED'}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
};

// ─── OverviewPanel ────────────────────────────────────────────────────────────
const OverviewPanel: React.FC<{
  status: LiveStatus | null;
  onRefresh: () => void;
  onStart: () => Promise<void>;
  onStop: () => Promise<void>;
  onRestart: () => Promise<void>;
  processLoading: boolean;
  pendingApprovals: number;
  onGoLive: () => void;
}> = ({ status, onRefresh, onStart, onStop, onRestart, processLoading, pendingApprovals, onGoLive }) => {
  const running = status?.process?.running ?? false;
  const healthy = status?.health?.healthy ?? false;

  return (
    <div>
      <HealthBanner status={status} onRefresh={onRefresh} />
      <ApprovalQueueBanner count={pendingApprovals} onClick={onGoLive} />

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(190px, 1fr))', gap: 14, marginBottom: 28 }}>
        <MetricCard
          label="Process Status" icon={<Activity size={14} />}
          value={<span style={{ color: running ? '#16a34a' : '#dc2626' }}>{running ? 'Running' : 'Stopped'}</span>}
          sub={`PID ${status?.process?.pid ?? '—'} · Port 5001`}
          accent={running ? 'green' : 'red'} onClick={onGoLive}
        />
        <MetricCard
          label="Uptime" icon={<Clock size={14} />}
          value={formatUptime(status?.process?.uptime_seconds)}
          sub="Since last start" accent="blue"
        />
        <MetricCard
          label="Health Check" icon={<ShieldCheck size={14} />}
          value={
            healthy
              ? <CheckCircle2 size={26} color="#16a34a" />
              : <XCircle size={26} color="#dc2626" />
          }
          sub={`HTTP ${status?.health?.status_code ?? '—'} · ${status?.health?.latency_ms ?? '—'}ms`}
          accent={healthy ? 'green' : 'red'}
        />
        <MetricCard
          label="AI Agents" icon={<Cpu size={14} />}
          value="4 Agents"
          sub="Investigator · Critic · Verifier · Auditor"
          accent="blue" onClick={onGoLive}
        />
      </div>

      <SectionHeader title="Process Control" sub="Manage the live-lab sample application lifecycle" />
      <ProcessControls status={status} onStart={onStart} onStop={onStop} onRestart={onRestart} loading={processLoading} />

      <SectionHeader title="Quick Actions" sub="Jump into common debugging workflows" />
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(210px, 1fr))', gap: 12, marginBottom: 28 }}>
        {[
          { title: 'Run Tests',   desc: 'Execute regression suite against live-lab', icon: <FlaskConical size={17} />, accent: '#2563eb', bg: '#eff6ff', border: '#bfdbfe' },
          { title: 'Investigate', desc: 'Launch 4-agent AI investigation pipeline',   icon: <Search size={17} />,       accent: '#7c3aed', bg: '#f5f3ff', border: '#ddd6fe' },
          { title: 'Process Logs', desc: 'Stream stdout/stderr from live-lab',        icon: <Terminal size={17} />,     accent: '#374151', bg: '#f9fafb', border: '#e5e7eb' },
          { title: 'Audit Log',   desc: 'View operator approval records',             icon: <ShieldCheck size={17} />,  accent: '#059669', bg: '#f0fdf4', border: '#bbf7d0' },
        ].map(item => (
          <button
            key={item.title}
            onClick={onGoLive}
            style={{
              background: item.bg, border: `1px solid ${item.border}`,
              borderRadius: 12, padding: '15px 17px',
              display: 'flex', alignItems: 'flex-start', gap: 11,
              cursor: 'pointer', textAlign: 'left', fontFamily: 'inherit',
              transition: 'box-shadow 0.15s',
            }}
            onMouseEnter={e => { (e.currentTarget as HTMLButtonElement).style.boxShadow = '0 4px 12px rgba(0,0,0,0.07)'; }}
            onMouseLeave={e => { (e.currentTarget as HTMLButtonElement).style.boxShadow = 'none'; }}
          >
            <span style={{ color: item.accent, marginTop: 1 }}>{item.icon}</span>
            <div>
              <div style={{ fontSize: 13, fontWeight: 600, color: '#111827' }}>{item.title}</div>
              <div style={{ fontSize: 11, color: '#6b7280', marginTop: 2 }}>{item.desc}</div>
            </div>
          </button>
        ))}
      </div>
    </div>
  );
};

// ─── MinimalDashboard Root ────────────────────────────────────────────────────
interface MinimalDashboardProps {
  onOpenLegacy: () => void;
}

export const MinimalDashboard: React.FC<MinimalDashboardProps> = ({ onOpenLegacy }) => {
  const [activeNav, setActiveNav] = useState<string>('overview');
  const [status, setStatus] = useState<LiveStatus | null>(null);
  const [processLoading, setProcessLoading] = useState(false);
  const [pendingApprovals] = useState(0);
  const [lastUpdated, setLastUpdated] = useState<Date>(new Date());

  const navItems: NavItem[] = [
    { id: 'overview',  label: 'Overview',    icon: <Layers size={15} /> },
    { id: 'live',      label: 'Live Debug',  icon: <Zap size={15} /> },
    { id: 'incidents', label: 'Incidents',   icon: <AlertCircle size={15} /> },
    { id: 'audit',     label: 'Audit Log',   icon: <ShieldCheck size={15} /> },
  ];

  const fetchStatus = useCallback(async () => {
    try {
      const res = await fetch('/api/live/status');
      if (res.ok) { setStatus(await res.json()); setLastUpdated(new Date()); }
    } catch { /* backend offline */ }
  }, []);

  useEffect(() => {
    fetchStatus();
    const iv = setInterval(fetchStatus, 5000);
    return () => clearInterval(iv);
  }, [fetchStatus]);

  const handleStart   = async () => { setProcessLoading(true); try { await fetch('/api/live/process/start',   { method: 'POST' }); await fetchStatus(); } finally { setProcessLoading(false); } };
  const handleStop    = async () => { setProcessLoading(true); try { await fetch('/api/live/process/stop',    { method: 'POST' }); await fetchStatus(); } finally { setProcessLoading(false); } };
  const handleRestart = async () => { setProcessLoading(true); try { await fetch('/api/live/process/restart', { method: 'POST' }); await fetchStatus(); } finally { setProcessLoading(false); } };

  const running = status?.process?.running ?? false;
  const healthy = status?.health?.healthy ?? false;
  const overall = running && healthy;

  const pageTitles: Record<string, string> = {
    overview: 'System Overview', live: 'Live Debug Console',
    incidents: 'Incident History', audit: 'Audit Log',
  };

  return (
    <>
      <style>{`
        @keyframes rt-ping {
          75%, 100% { transform: scale(2); opacity: 0; }
        }
        .rt-sidebar-btn:hover { background: #f3f4f6 !important; color: #374151 !important; }
      `}</style>

      <div style={{ display: 'flex', height: '100vh', background: '#f9fafb', fontFamily: 'Inter, -apple-system, BlinkMacSystemFont, sans-serif' }}>
        {/* ── Sidebar ── */}
        <aside style={{
          width: 216, flexShrink: 0, background: '#fff',
          borderRight: '1px solid #e5e7eb', display: 'flex', flexDirection: 'column',
          padding: '18px 0', overflowY: 'auto',
        }}>
          {/* Logo */}
          <div style={{ padding: '0 18px 20px', borderBottom: '1px solid #f3f4f6' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
              <div style={{
                width: 30, height: 30, borderRadius: 7, background: '#2563eb',
                display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0,
              }}>
                <GitBranch size={15} color="#fff" />
              </div>
              <div>
                <div style={{ fontSize: 14, fontWeight: 700, color: '#111827', letterSpacing: '-0.01em' }}>RootTrace</div>
                <div style={{ fontSize: 10, color: '#9ca3af', fontWeight: 500 }}>Live Debug Platform</div>
              </div>
            </div>
          </div>

          {/* Nav */}
          <nav style={{ flex: 1, padding: '10px 10px 0' }}>
            {navItems.map(item => (
              <button
                key={item.id}
                onClick={() => setActiveNav(item.id)}
                style={{
                  display: 'flex', alignItems: 'center', gap: 9, width: '100%',
                  padding: '8px 11px', borderRadius: 8, border: 'none',
                  cursor: 'pointer', marginBottom: 2,
                  background: activeNav === item.id ? '#eff6ff' : 'transparent',
                  color: activeNav === item.id ? '#2563eb' : '#6b7280',
                  fontWeight: activeNav === item.id ? 600 : 400,
                  fontSize: 13, textAlign: 'left', fontFamily: 'inherit',
                  transition: 'background 0.1s, color 0.1s',
                }}
                onMouseEnter={e => { if (activeNav !== item.id) { (e.currentTarget as HTMLButtonElement).style.background = '#f9fafb'; } }}
                onMouseLeave={e => { if (activeNav !== item.id) { (e.currentTarget as HTMLButtonElement).style.background = 'transparent'; } }}
              >
                <span style={{ opacity: activeNav === item.id ? 1 : 0.55, flexShrink: 0 }}>{item.icon}</span>
                {item.label}
              </button>
            ))}
          </nav>

          {/* Legacy toggle */}
          <div style={{ padding: '10px 10px 2px', borderTop: '1px solid #f3f4f6' }}>
            <button
              onClick={onOpenLegacy}
              title="Open legacy full-featured dashboard"
              className="rt-sidebar-btn"
              style={{
                display: 'flex', alignItems: 'center', gap: 7, width: '100%',
                padding: '7px 11px', borderRadius: 8, border: '1px solid #e5e7eb',
                background: 'transparent', color: '#9ca3af', fontSize: 11,
                fontWeight: 500, cursor: 'pointer', fontFamily: 'inherit',
                transition: 'background 0.1s, color 0.1s',
              }}
            >
              <ExternalLink size={11} />
              Open legacy dashboard
            </button>
          </div>
        </aside>

        {/* ── Content ── */}
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', minWidth: 0 }}>
          {/* Topbar */}
          <header style={{
            background: '#fff', borderBottom: '1px solid #e5e7eb',
            padding: '11px 26px', display: 'flex', justifyContent: 'space-between', alignItems: 'center',
            flexShrink: 0,
          }}>
            <div>
              <div style={{ fontSize: 15, fontWeight: 600, color: '#111827' }}>{pageTitles[activeNav]}</div>
              <div style={{ fontSize: 11, color: '#9ca3af', marginTop: 1 }}>Updated {timeAgo(lastUpdated.toISOString())}</div>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
              <div style={{
                display: 'flex', alignItems: 'center', gap: 6,
                background: overall ? '#f0fdf4' : '#fff1f2',
                border: `1px solid ${overall ? '#bbf7d0' : '#fecdd3'}`,
                borderRadius: 20, padding: '4px 11px',
                fontSize: 11, fontWeight: 600,
                color: overall ? '#15803d' : '#b91c1c',
              }}>
                <StatusDot ok={overall} pulse={overall} />
                {overall ? 'System Healthy' : running ? 'Degraded' : 'Offline'}
              </div>
              <button style={{ background: 'transparent', border: '1px solid #e5e7eb', borderRadius: 7, padding: 6, cursor: 'pointer', color: '#6b7280', display: 'flex' }}>
                <Settings size={14} />
              </button>
            </div>
          </header>

          {/* Page */}
          <main style={{ flex: 1, overflowY: 'auto', padding: '22px 26px' }}>
            {activeNav === 'overview' && (
              <OverviewPanel
                status={status} onRefresh={fetchStatus}
                onStart={handleStart} onStop={handleStop} onRestart={handleRestart}
                processLoading={processLoading}
                pendingApprovals={pendingApprovals}
                onGoLive={() => setActiveNav('live')}
              />
            )}
            {activeNav === 'live' && (
              <div>
                <HealthBanner status={status} onRefresh={fetchStatus} />
                <ProcessControls status={status} onStart={handleStart} onStop={handleStop} onRestart={handleRestart} loading={processLoading} />
                <LiveDebugConsole />
              </div>
            )}
            {activeNav === 'incidents' && <IncidentHistoryPanel />}
            {activeNav === 'audit' && <AuditLogPanel />}
          </main>
        </div>
      </div>
    </>
  );
};
