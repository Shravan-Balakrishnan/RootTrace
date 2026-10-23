import React from 'react';
import { ToolCallRecord } from '../types/incident';
import { Terminal, Check, X, Clock } from 'lucide-react';

interface ToolActivityFeedProps {
  toolCalls: ToolCallRecord[];
}

export const ToolActivityFeed: React.FC<ToolActivityFeedProps> = ({ toolCalls }) => {
  if (!toolCalls || toolCalls.length === 0) {
    return (
      <div style={{ padding: '16px', color: '#64748b', fontSize: '12px', textAlign: 'center' }}>
        No tools invoked yet. Investigation agent will call tools dynamically.
      </div>
    );
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
      {toolCalls.map((tc) => {
        const isSuccess = tc.status === 'COMPLETED';

        return (
          <div
            key={tc.id}
            style={{
              background: '#0b111e',
              border: `1px solid ${isSuccess ? 'rgba(255, 255, 255, 0.06)' : 'rgba(239, 68, 68, 0.3)'}`,
              borderRadius: '6px',
              padding: '8px 10px',
              fontFamily: 'var(--font-mono)',
              fontSize: '11px',
              display: 'flex',
              flexDirection: 'column',
              gap: '4px'
            }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                <Terminal size={12} color="#06b6d4" />
                <span style={{ color: '#38bdf8', fontWeight: 600 }}>{tc.tool_name}()</span>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: '#64748b', fontSize: '10px' }}>
                <span style={{ display: 'flex', alignItems: 'center', gap: '2px' }}>
                  <Clock size={10} />
                  {tc.duration_ms}ms
                </span>
                <span style={{
                  padding: '1px 5px',
                  borderRadius: '3px',
                  background: isSuccess ? 'rgba(16, 185, 129, 0.15)' : 'rgba(239, 68, 68, 0.15)',
                  color: isSuccess ? '#34d399' : '#f87171',
                  fontWeight: 600
                }}>
                  {tc.status}
                </span>
              </div>
            </div>

            <div style={{ color: '#94a3b8', fontSize: '10px', wordBreak: 'break-all' }}>
              args: {JSON.stringify(tc.arguments)}
            </div>

            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '10px', color: '#64748b' }}>
              <span>Produced {tc.returned_evidence_ids.length} evidence records</span>
              <span>{tc.timestamp.slice(11, 19)} UTC</span>
            </div>
          </div>
        );
      })}
    </div>
  );
};
