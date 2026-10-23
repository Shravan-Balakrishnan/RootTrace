import React from 'react';
import { TestExecutionResult } from '../../types/liveDebug';
import { Terminal, CheckCircle, XCircle, Clock } from 'lucide-react';

interface Props {
  results: TestExecutionResult | null;
}

export const TestResultsPanel: React.FC<Props> = ({ results }) => {
  if (!results) {
    return null;
  }

  return (
    <div style={{
      background: 'rgba(15, 23, 42, 0.75)',
      border: '1px solid rgba(255, 255, 255, 0.1)',
      borderRadius: '8px',
      padding: '16px',
      display: 'flex',
      flexDirection: 'column',
      gap: '10px'
    }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <Terminal size={16} color="#38bdf8" />
          <span style={{ fontSize: '13px', fontWeight: 600, color: '#f8fafc' }}>
            Allowlisted Test Suite Results
          </span>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '11px' }}>
          <span style={{
            background: results.all_passed ? 'rgba(16, 185, 129, 0.2)' : 'rgba(239, 68, 68, 0.2)',
            color: results.all_passed ? '#34d399' : '#f87171',
            padding: '2px 8px',
            borderRadius: '4px',
            fontWeight: 600,
            display: 'flex',
            alignItems: 'center',
            gap: '4px'
          }}>
            {results.all_passed ? <CheckCircle size={13} /> : <XCircle size={13} />}
            {results.all_passed ? 'ALL PASSED' : `${results.failed_tests} FAILED`}
          </span>
          <span style={{ color: '#94a3b8', display: 'flex', alignItems: 'center', gap: '3px' }}>
            <Clock size={12} /> {results.duration_seconds}s
          </span>
        </div>
      </div>

      <div style={{
        background: '#090d16',
        borderRadius: '6px',
        border: '1px solid rgba(255, 255, 255, 0.08)',
        padding: '10px',
        fontFamily: 'var(--font-mono)',
        fontSize: '11px',
        color: '#cbd5e1',
        maxHeight: '160px',
        overflowY: 'auto',
        whiteSpace: 'pre-wrap'
      }}>
        {results.raw_output || 'No output recorded.'}
      </div>
    </div>
  );
};
