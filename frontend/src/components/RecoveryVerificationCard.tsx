import React from 'react';
import { RecoveryResult } from '../types/incident';
import { CheckCircle, XCircle, FileText, Activity } from 'lucide-react';

interface RecoveryVerificationCardProps {
  recoveryResult?: RecoveryResult;
  hasPostmortem: boolean;
  onOpenPostmortem: () => void;
}

export const RecoveryVerificationCard: React.FC<RecoveryVerificationCardProps> = ({
  recoveryResult,
  hasPostmortem,
  onOpenPostmortem
}) => {
  if (!recoveryResult) return null;

  const allPassed = recoveryResult.all_checks_passed;

  return (
    <div style={{
      background: allPassed ? 'rgba(16, 185, 129, 0.05)' : 'rgba(239, 68, 68, 0.05)',
      border: `1px solid ${allPassed ? 'rgba(16, 185, 129, 0.35)' : 'rgba(239, 68, 68, 0.35)'}`,
      borderRadius: '8px',
      padding: '14px',
      display: 'flex',
      flexDirection: 'column',
      gap: '8px'
    }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
          {allPassed ? (
            <CheckCircle size={16} color="#10b981" />
          ) : (
            <XCircle size={16} color="#ef4444" />
          )}
          <strong style={{
            fontSize: '12px',
            color: allPassed ? '#34d399' : '#f87171',
            textTransform: 'uppercase',
            letterSpacing: '0.5px'
          }}>
            {allPassed ? 'Recovery Verified in Simulator' : 'Recovery Verification Failed'}
          </strong>
        </div>
        <span style={{
          fontSize: '10px',
          fontWeight: 700,
          background: allPassed ? 'rgba(16, 185, 129, 0.2)' : 'rgba(239, 68, 68, 0.2)',
          color: allPassed ? '#34d399' : '#f87171',
          padding: '2px 6px',
          borderRadius: '4px'
        }}>
          {allPassed ? 'ALL INVARIANTS SATISFIED' : 'INVARIANT VIOLATION'}
        </span>
      </div>

      <div style={{ fontSize: '13px', color: '#f8fafc', fontWeight: 500 }}>
        {recoveryResult.summary}
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: '6px', marginTop: '2px' }}>
        {recoveryResult.checks.map((c, idx) => (
          <div
            key={idx}
            style={{
              background: 'rgba(0, 0, 0, 0.25)',
              borderLeft: `3px solid ${c.passed ? '#10b981' : '#ef4444'}`,
              borderRadius: '4px',
              padding: '6px 10px',
              fontSize: '11px',
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center'
            }}
          >
            <div>
              <span style={{ fontWeight: 600, color: '#f1f5f9' }}>{c.check_name}</span>
              <span style={{ color: '#64748b', marginLeft: '6px' }}>({c.target})</span>
            </div>
            <div style={{ fontFamily: 'var(--font-mono)', color: c.passed ? '#34d399' : '#f87171', fontWeight: 700 }}>
              {c.actual_recovered_count}/{c.expected_recovered_count} recovered
            </div>
          </div>
        ))}
      </div>

      {hasPostmortem && (
        <button
          onClick={onOpenPostmortem}
          style={{
            marginTop: '6px',
            background: 'linear-gradient(135deg, #1e293b, #0f172a)',
            color: '#38bdf8',
            border: '1px solid rgba(56, 189, 248, 0.3)',
            padding: '8px 12px',
            borderRadius: '6px',
            fontSize: '12px',
            fontWeight: 600,
            cursor: 'pointer',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            gap: '6px'
          }}
        >
          <FileText size={14} />
          View Verified Incident Postmortem
        </button>
      )}
    </div>
  );
};
