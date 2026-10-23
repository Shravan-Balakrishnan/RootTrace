import React from 'react';
import { 
  ShieldAlert, 
  Play, 
  RotateCcw, 
  Pause, 
  Cpu, 
  Zap, 
  Terminal, 
  ChevronRight,
  Server
} from 'lucide-react';
import { ScenarioMeta, SystemStatus, Incident } from '../types/incident';

interface HeaderProps {
  scenarios: ScenarioMeta[];
  currentScenario: string;
  onSelectScenario: (id: string) => void;
  systemStatus: SystemStatus | null;
  incident: Incident | null;
  isStreaming: boolean;
  onAutoInvestigate: () => void;
  onStepPhase: () => void;
  onResetInvestigation: () => void;
  onTogglePause: () => void;
}

export const Header: React.FC<HeaderProps> = ({
  scenarios,
  currentScenario,
  onSelectScenario,
  systemStatus,
  incident,
  isStreaming,
  onAutoInvestigate,
  onStepPhase,
  onResetInvestigation,
  onTogglePause,
}) => {
  const isPaused = incident?.is_autonomous_paused;
  const isAwaitingApproval = incident?.current_phase === 'AWAITING_APPROVAL';
  const isResolved = incident?.current_phase === 'RESOLVED';

  return (
    <header style={{
      display: 'flex',
      justifyContent: 'space-between',
      alignItems: 'center',
      padding: '12px 24px',
      background: 'rgba(9, 13, 22, 0.95)',
      backdropFilter: 'blur(16px)',
      borderBottom: '1px solid rgba(255, 255, 255, 0.08)',
      position: 'sticky',
      top: 0,
      zIndex: 50,
      height: '64px'
    }}>
      {/* Brand & Incident Identifier */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
        <div style={{
          width: '36px',
          height: '36px',
          background: 'linear-gradient(135deg, #06b6d4, #3b82f6)',
          borderRadius: '8px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          color: '#fff',
          fontWeight: 800,
          boxShadow: '0 0 16px rgba(6, 182, 212, 0.4)'
        }}>
          RT
        </div>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <span style={{ fontSize: '16px', fontWeight: 800, letterSpacing: '-0.3px', color: '#f8fafc' }}>
              ROOTTRACE
            </span>
            <span style={{
              fontSize: '10px',
              fontFamily: 'var(--font-mono)',
              background: 'rgba(6, 182, 212, 0.15)',
              color: '#38bdf8',
              padding: '2px 6px',
              borderRadius: '4px',
              border: '1px solid rgba(6, 182, 212, 0.3)'
            }}>
              v1.0.0
            </span>
          </div>
          <div style={{ fontSize: '11px', color: '#64748b' }}>
            Autonomous Incident Investigation & Verified Recovery
          </div>
        </div>

        {incident?.run_id && (
          <div style={{
            display: 'flex',
            alignItems: 'center',
            gap: '6px',
            background: 'rgba(255, 255, 255, 0.04)',
            padding: '4px 10px',
            borderRadius: '6px',
            border: '1px solid rgba(255, 255, 255, 0.06)',
            fontSize: '11px',
            fontFamily: 'var(--font-mono)',
            color: '#94a3b8'
          }}>
            <Terminal size={12} color="#06b6d4" />
            <span>RUN: {incident.run_id}</span>
          </div>
        )}
      </div>

      {/* Middle & Right Controls */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
        {/* Scenario Selection */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
          <Server size={14} color="#94a3b8" />
          <select
            value={currentScenario}
            onChange={(e) => onSelectScenario(e.target.value)}
            disabled={isStreaming}
            style={{
              background: '#0f172a',
              color: '#f8fafc',
              border: '1px solid rgba(255, 255, 255, 0.15)',
              padding: '6px 12px',
              borderRadius: '6px',
              fontSize: '12px',
              fontWeight: 500,
              cursor: isStreaming ? 'not-allowed' : 'pointer',
              outline: 'none',
              maxWidth: '280px'
            }}
          >
            {scenarios.map((s) => (
              <option key={s.id} value={s.id}>
                {s.title}
              </option>
            ))}
          </select>
        </div>

        {/* AI Mode Indicator */}
        <div style={{
          display: 'flex',
          alignItems: 'center',
          gap: '6px',
          padding: '4px 10px',
          borderRadius: '6px',
          fontSize: '11px',
          fontFamily: 'var(--font-mono)',
          background: systemStatus?.llm.api_key_configured ? 'rgba(16, 185, 129, 0.12)' : 'rgba(245, 158, 11, 0.12)',
          border: `1px solid ${systemStatus?.llm.api_key_configured ? 'rgba(16, 185, 129, 0.3)' : 'rgba(245, 158, 11, 0.3)'}`,
          color: systemStatus?.llm.api_key_configured ? '#34d399' : '#fbbf24'
        }}>
          <Cpu size={12} />
          <span>{systemStatus?.llm.mode || 'REASONING_ENGINE'}</span>
        </div>

        {/* Action Buttons */}
        <button
          onClick={onStepPhase}
          disabled={isStreaming || isAwaitingApproval || isResolved}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '6px',
            background: '#1e293b',
            color: '#e2e8f0',
            border: '1px solid rgba(255, 255, 255, 0.1)',
            padding: '6px 12px',
            borderRadius: '6px',
            fontSize: '12px',
            fontWeight: 600,
            cursor: (isStreaming || isAwaitingApproval || isResolved) ? 'not-allowed' : 'pointer',
            opacity: (isStreaming || isAwaitingApproval || isResolved) ? 0.5 : 1
          }}
          title="Advance single investigation phase"
        >
          <ChevronRight size={14} />
          Step Phase
        </button>

        <button
          onClick={onAutoInvestigate}
          disabled={isStreaming || isAwaitingApproval || isResolved}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '6px',
            background: isStreaming ? '#0284c7' : 'linear-gradient(135deg, #0ea5e9, #0284c7)',
            color: '#fff',
            border: 'none',
            padding: '6px 14px',
            borderRadius: '6px',
            fontSize: '12px',
            fontWeight: 600,
            cursor: (isStreaming || isAwaitingApproval || isResolved) ? 'not-allowed' : 'pointer',
            boxShadow: '0 0 14px rgba(14, 165, 233, 0.35)',
            opacity: (isAwaitingApproval || isResolved) ? 0.5 : 1
          }}
          title="Stream autonomous end-to-end investigation"
        >
          <Zap size={14} />
          {isStreaming ? 'Streaming Discovery...' : 'Auto-Investigate'}
        </button>

        <button
          onClick={onResetInvestigation}
          disabled={isStreaming}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '6px',
            background: 'rgba(239, 68, 68, 0.1)',
            color: '#f87171',
            border: '1px solid rgba(239, 68, 68, 0.25)',
            padding: '6px 10px',
            borderRadius: '6px',
            fontSize: '12px',
            fontWeight: 600,
            cursor: isStreaming ? 'not-allowed' : 'pointer'
          }}
          title="Reset current scenario with clean simulator state and new run ID"
        >
          <RotateCcw size={13} />
          Reset Run
        </button>

        <button
          onClick={onTogglePause}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '6px',
            background: isPaused ? 'rgba(16, 185, 129, 0.15)' : '#1e293b',
            color: isPaused ? '#34d399' : '#94a3b8',
            border: `1px solid ${isPaused ? 'rgba(16, 185, 129, 0.3)' : 'rgba(255, 255, 255, 0.1)'}`,
            padding: '6px 10px',
            borderRadius: '6px',
            fontSize: '12px',
            fontWeight: 600,
            cursor: 'pointer'
          }}
        >
          {isPaused ? <Play size={13} /> : <Pause size={13} />}
          {isPaused ? 'Resume Autonomy' : 'Pause'}
        </button>
      </div>
    </header>
  );
};
