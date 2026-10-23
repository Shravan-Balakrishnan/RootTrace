import React, { useState } from 'react';
import { SanitizedEvidenceRecord } from '../../types/liveDebug';
import { ShieldCheck, AlertTriangle, Eye, Database, FileCode, Activity } from 'lucide-react';

interface Props {
  evidence: SanitizedEvidenceRecord[];
}

export const EvidenceTimeline: React.FC<Props> = ({ evidence }) => {
  const [expandedId, setExpandedId] = useState<string | null>(null);

  if (!evidence || evidence.length === 0) {
    return (
      <div style={{
        background: 'rgba(15, 23, 42, 0.5)',
        border: '1px dashed rgba(255, 255, 255, 0.15)',
        borderRadius: '8px',
        padding: '24px',
        textAlign: 'center',
        color: '#94a3b8',
        fontSize: '12px'
      }}>
        No live evidence collected yet. Launch an investigation or run diagnostics to capture runtime telemetry.
      </div>
    );
  }

  const getSourceIcon = (tool: string) => {
    switch (tool) {
      case 'process_logs': return <FileCode size={14} color="#38bdf8" />;
      case 'regression_test_runner': return <Activity size={14} color="#f59e0b" />;
      case 'git_inspector': return <FileCode size={14} color="#a855f7" />;
      default: return <Database size={14} color="#10b981" />;
    }
  };

  return (
    <div style={{
      background: 'rgba(15, 23, 42, 0.75)',
      border: '1px solid rgba(255, 255, 255, 0.1)',
      borderRadius: '8px',
      padding: '16px',
      display: 'flex',
      flexDirection: 'column',
      gap: '12px'
    }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <span style={{ fontSize: '13px', fontWeight: 600, color: '#f8fafc' }}>
          Captured Evidence Timeline ({evidence.length} Records)
        </span>
        <span style={{ fontSize: '11px', color: '#10b981', display: 'flex', alignItems: 'center', gap: '4px' }}>
          <ShieldCheck size={13} /> Sanitized & Secret-Scanned
        </span>
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
        {evidence.map((item) => {
          const isExpanded = expandedId === item.id;
          return (
            <div
              key={item.id}
              style={{
                background: 'rgba(0, 0, 0, 0.25)',
                border: '1px solid rgba(255, 255, 255, 0.08)',
                borderRadius: '6px',
                padding: '10px 12px',
                display: 'flex',
                flexDirection: 'column',
                gap: '6px'
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  {getSourceIcon(item.source_tool)}
                  <span style={{
                    fontFamily: 'var(--font-mono)',
                    fontSize: '11px',
                    fontWeight: 600,
                    color: '#38bdf8'
                  }}>
                    {item.id}
                  </span>
                  <span style={{ fontSize: '11px', color: '#cbd5e1' }}>
                    [{item.source_tool}] {item.summary}
                  </span>
                </div>

                <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                  {item.redaction_count > 0 && (
                    <span style={{
                      background: 'rgba(245, 158, 11, 0.15)',
                      color: '#fbbf24',
                      fontSize: '10px',
                      padding: '1px 6px',
                      borderRadius: '3px',
                      fontWeight: 600
                    }}>
                      {item.redaction_count} secret(s) redacted
                    </span>
                  )}
                  {item.flagged_for_injection && (
                    <span style={{
                      background: 'rgba(239, 68, 68, 0.2)',
                      color: '#f87171',
                      fontSize: '10px',
                      padding: '1px 6px',
                      borderRadius: '3px',
                      fontWeight: 600,
                      display: 'flex',
                      alignItems: 'center',
                      gap: '3px'
                    }}>
                      <AlertTriangle size={11} /> Injection Guard Triggered
                    </span>
                  )}
                  <button
                    onClick={() => setExpandedId(isExpanded ? null : item.id)}
                    style={{
                      background: 'transparent',
                      border: 'none',
                      color: '#94a3b8',
                      cursor: 'pointer',
                      display: 'flex',
                      alignItems: 'center',
                      gap: '3px',
                      fontSize: '11px'
                    }}
                  >
                    <Eye size={12} /> {isExpanded ? 'Hide' : 'Inspect'}
                  </button>
                </div>
              </div>

              {isExpanded && (
                <div style={{
                  background: 'rgba(0, 0, 0, 0.45)',
                  padding: '8px',
                  borderRadius: '4px',
                  fontFamily: 'var(--font-mono)',
                  fontSize: '10px',
                  color: '#e2e8f0',
                  maxHeight: '200px',
                  overflowY: 'auto',
                  whiteSpace: 'pre-wrap',
                  border: '1px solid rgba(255, 255, 255, 0.05)'
                }}>
                  {JSON.stringify(item.data, null, 2)}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
};
