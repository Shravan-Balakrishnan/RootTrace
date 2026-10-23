import React from 'react';
import { AgentExecutionRecord, HistoricalIncidentCase, LogIntelligenceReport } from '../../types/liveDebug';
import { Bot, CheckCircle2, XCircle, Clock, Search, ShieldCheck, Wrench, Sparkles, BookOpen } from 'lucide-react';

interface Props {
  agentTraces?: AgentExecutionRecord[];
  logIntelligence?: LogIntelligenceReport | null;
  historicalCases?: HistoricalIncidentCase[];
}

export const FourAgentTraceCard: React.FC<Props> = ({
  agentTraces,
  logIntelligence,
  historicalCases
}) => {
  if (!agentTraces || agentTraces.length === 0) {
    return null;
  }

  const getAgentIcon = (roleName: string) => {
    if (roleName.includes('Agent 1')) return <Search size={15} color="#38bdf8" />;
    if (roleName.includes('Agent 2')) return <Bot size={15} color="#818cf8" />;
    if (roleName.includes('Agent 3')) return <ShieldCheck size={15} color="#f59e0b" />;
    return <Wrench size={15} color="#10b981" />;
  };

  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'COMPLETED':
      case 'APPROVED':
      case 'VERIFIED':
        return (
          <span style={{
            fontSize: '10px',
            padding: '2px 6px',
            borderRadius: '4px',
            fontWeight: 600,
            background: 'rgba(16, 185, 129, 0.15)',
            color: '#34d399',
            display: 'flex',
            alignItems: 'center',
            gap: '3px'
          }}>
            <CheckCircle2 size={11} /> {status}
          </span>
        );
      case 'VETOED':
      case 'FAILED':
        return (
          <span style={{
            fontSize: '10px',
            padding: '2px 6px',
            borderRadius: '4px',
            fontWeight: 600,
            background: 'rgba(239, 68, 68, 0.15)',
            color: '#f87171',
            display: 'flex',
            alignItems: 'center',
            gap: '3px'
          }}>
            <XCircle size={11} /> {status}
          </span>
        );
      case 'AWAITING_APPROVAL':
        return (
          <span style={{
            fontSize: '10px',
            padding: '2px 6px',
            borderRadius: '4px',
            fontWeight: 600,
            background: 'rgba(56, 189, 248, 0.15)',
            color: '#38bdf8',
            display: 'flex',
            alignItems: 'center',
            gap: '3px'
          }}>
            <Clock size={11} /> AWAITING APPROVAL
          </span>
        );
      default:
        return (
          <span style={{
            fontSize: '10px',
            padding: '2px 6px',
            borderRadius: '4px',
            fontWeight: 600,
            background: 'rgba(148, 163, 184, 0.15)',
            color: '#94a3b8'
          }}>
            {status}
          </span>
        );
    }
  };

  return (
    <div style={{
      background: 'rgba(15, 23, 42, 0.85)',
      border: '1px solid rgba(255, 255, 255, 0.1)',
      borderRadius: '8px',
      padding: '16px',
      display: 'flex',
      flexDirection: 'column',
      gap: '12px'
    }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <Sparkles size={16} color="#818cf8" />
          <span style={{ fontSize: '13px', fontWeight: 600, color: '#f8fafc' }}>
            Four-Agent Orchestration & Log Intelligence Trace
          </span>
        </div>
        {logIntelligence && (
          <span style={{
            fontSize: '10px',
            padding: '2px 8px',
            borderRadius: '4px',
            fontWeight: 600,
            fontFamily: 'var(--font-mono)',
            background: logIntelligence.implementation_used === 'drain3' ? 'rgba(56, 189, 248, 0.2)' : 'rgba(245, 158, 11, 0.2)',
            color: logIntelligence.implementation_used === 'drain3' ? '#38bdf8' : '#fbbf24',
            border: '1px solid currentColor'
          }}>
            Log Intelligence: {logIntelligence.implementation_used.toUpperCase()}
          </span>
        )}
      </div>

      {/* Grid of the 4 Agents */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '10px' }}>
        {agentTraces.map((agent) => (
          <div
            key={agent.agent_id}
            style={{
              background: 'rgba(0, 0, 0, 0.25)',
              border: '1px solid rgba(255, 255, 255, 0.08)',
              borderRadius: '6px',
              padding: '12px',
              display: 'flex',
              flexDirection: 'column',
              gap: '6px'
            }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '12px', fontWeight: 600, color: '#f1f5f9' }}>
                {getAgentIcon(agent.role_name)}
                <span>{agent.role_name}</span>
              </div>
              {getStatusBadge(agent.status)}
            </div>

            <p style={{ fontSize: '11px', color: '#94a3b8', margin: 0, lineHeight: 1.4 }}>
              {agent.summary}
            </p>

            {agent.tool_calls && agent.tool_calls.length > 0 && (
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: '4px', marginTop: '4px' }}>
                {agent.tool_calls.map((t, idx) => (
                  <span
                    key={idx}
                    style={{
                      fontFamily: 'var(--font-mono)',
                      fontSize: '9px',
                      background: 'rgba(255, 255, 255, 0.06)',
                      padding: '1px 5px',
                      borderRadius: '3px',
                      color: '#cbd5e1'
                    }}
                  >
                    {t}
                  </span>
                ))}
              </div>
            )}

            <div style={{ fontSize: '10px', color: '#64748b', marginTop: '2px', display: 'flex', justifyContent: 'space-between' }}>
              <span>Duration: {agent.execution_time_ms}ms</span>
            </div>
          </div>
        ))}
      </div>

      {/* Continual Learning / Historical Incidents Retrieved */}
      {historicalCases && historicalCases.length > 0 && (
        <div style={{
          marginTop: '6px',
          background: 'rgba(99, 102, 241, 0.08)',
          border: '1px solid rgba(99, 102, 241, 0.2)',
          borderRadius: '6px',
          padding: '10px 12px',
          display: 'flex',
          flexDirection: 'column',
          gap: '6px'
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '11px', fontWeight: 600, color: '#a5b4fc' }}>
            <BookOpen size={13} />
            <span>Continual Learning: Retrieved Verified Historical Cases ({historicalCases.length})</span>
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
            {historicalCases.map((c) => (
              <div key={c.case_id} style={{ fontSize: '11px', color: '#cbd5e1' }}>
                <strong style={{ color: '#818cf8', fontFamily: 'var(--font-mono)' }}>[{c.case_id}]</strong> {c.signature}: {c.patch_summary}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};
