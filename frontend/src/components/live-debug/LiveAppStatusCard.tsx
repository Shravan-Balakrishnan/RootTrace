import React from 'react';
import { LiveSystemStatus } from '../../types/liveDebug';
import { Play, Square, RotateCw, Activity, Terminal, ShieldAlert } from 'lucide-react';

interface Props {
  status: LiveSystemStatus | null;
  onStart: () => void;
  onStop: () => void;
  onRestart: () => void;
  onRunTests: () => void;
  onInvestigate: () => void;
  isInvestigating: boolean;
  isTesting: boolean;
}

export const LiveAppStatusCard: React.FC<Props> = ({
  status,
  onStart,
  onStop,
  onRestart,
  onRunTests,
  onInvestigate,
  isInvestigating,
  isTesting
}) => {
  const isRunning = status?.process?.is_running ?? false;
  const healthLabel = status?.health?.status_label ?? 'UNKNOWN';
  const isHealthy = status?.health?.is_healthy ?? false;

  const getHealthBadge = () => {
    if (isHealthy) {
      return <span style={{ background: 'rgba(16, 185, 129, 0.2)', color: '#34d399', padding: '2px 8px', borderRadius: '4px', fontWeight: 600 }}>HEALTHY (HTTP 200)</span>;
    }
    if (isRunning) {
      return <span style={{ background: 'rgba(239, 68, 68, 0.2)', color: '#f87171', padding: '2px 8px', borderRadius: '4px', fontWeight: 600 }}>DEGRADED / FAILING</span>;
    }
    return <span style={{ background: 'rgba(148, 163, 184, 0.2)', color: '#94a3b8', padding: '2px 8px', borderRadius: '4px', fontWeight: 600 }}>STOPPED</span>;
  };

  return (
    <div style={{
      background: 'rgba(15, 23, 42, 0.75)',
      backdropFilter: 'blur(12px)',
      border: '1px solid rgba(255, 255, 255, 0.1)',
      borderRadius: '8px',
      padding: '16px',
      display: 'flex',
      flexDirection: 'column',
      gap: '12px'
    }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <Activity size={18} color="#38bdf8" />
          <span style={{ fontSize: '14px', fontWeight: 600, color: '#f8fafc' }}>
            Managed Testbed: <code style={{ color: '#38bdf8' }}>live-lab (FastAPI)</code>
          </span>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '12px' }}>
          {getHealthBadge()}
        </div>
      </div>

      <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(4, 1fr)',
        gap: '8px',
        background: 'rgba(0, 0, 0, 0.3)',
        padding: '10px',
        borderRadius: '6px',
        fontSize: '11px',
        fontFamily: 'var(--font-mono)'
      }}>
        <div>
          <span style={{ color: '#94a3b8' }}>State: </span>
          <span style={{ color: isRunning ? '#34d399' : '#f87171', fontWeight: 600 }}>
            {isRunning ? 'RUNNING' : 'STOPPED'}
          </span>
        </div>
        <div>
          <span style={{ color: '#94a3b8' }}>PID: </span>
          <span style={{ color: '#f8fafc' }}>{status?.process?.pid ?? '—'}</span>
        </div>
        <div>
          <span style={{ color: '#94a3b8' }}>Endpoint: </span>
          <span style={{ color: '#38bdf8' }}>http://127.0.0.1:{status?.process?.port ?? 8001}</span>
        </div>
        <div>
          <span style={{ color: '#94a3b8' }}>Probe Latency: </span>
          <span style={{ color: '#f8fafc' }}>
            {status?.health?.latency_ms !== null && status?.health?.latency_ms !== undefined ? `${status.health.latency_ms} ms` : '—'}
          </span>
        </div>
      </div>

      <div style={{ display: 'flex', gap: '8px', alignItems: 'center', flexWrap: 'wrap' }}>
        {!isRunning ? (
          <button
            onClick={onStart}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              background: '#0284c7',
              color: '#fff',
              border: 'none',
              borderRadius: '4px',
              padding: '6px 12px',
              fontSize: '12px',
              fontWeight: 600,
              cursor: 'pointer'
            }}
          >
            <Play size={14} /> Start Service
          </button>
        ) : (
          <button
            onClick={onStop}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              background: '#dc2626',
              color: '#fff',
              border: 'none',
              borderRadius: '4px',
              padding: '6px 12px',
              fontSize: '12px',
              fontWeight: 600,
              cursor: 'pointer'
            }}
          >
            <Square size={14} /> Stop Service
          </button>
        )}

        <button
          onClick={onRestart}
          disabled={!isRunning}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '6px',
            background: 'rgba(255, 255, 255, 0.08)',
            color: '#f8fafc',
            border: '1px solid rgba(255, 255, 255, 0.15)',
            borderRadius: '4px',
            padding: '6px 12px',
            fontSize: '12px',
            cursor: isRunning ? 'pointer' : 'not-allowed',
            opacity: isRunning ? 1 : 0.5
          }}
        >
          <RotateCw size={14} /> Restart
        </button>

        <button
          onClick={onRunTests}
          disabled={isTesting}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '6px',
            background: 'rgba(56, 189, 248, 0.1)',
            color: '#38bdf8',
            border: '1px solid rgba(56, 189, 248, 0.3)',
            borderRadius: '4px',
            padding: '6px 12px',
            fontSize: '12px',
            fontWeight: 600,
            cursor: isTesting ? 'wait' : 'pointer'
          }}
        >
          <Terminal size={14} /> {isTesting ? 'Running Pytest...' : 'Run Regression Tests'}
        </button>

        <div style={{ flex: 1 }} />

        <button
          onClick={onInvestigate}
          disabled={isInvestigating}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '6px',
            background: 'linear-gradient(135deg, #4f46e5 0%, #7c3aed 100%)',
            color: '#fff',
            border: 'none',
            borderRadius: '4px',
            padding: '7px 16px',
            fontSize: '12px',
            fontWeight: 600,
            cursor: isInvestigating ? 'wait' : 'pointer',
            boxShadow: '0 2px 8px rgba(99, 102, 241, 0.3)'
          }}
        >
          <ShieldAlert size={15} /> {isInvestigating ? 'Investigating Live Evidence...' : 'Investigate Failure'}
        </button>
      </div>
    </div>
  );
};
