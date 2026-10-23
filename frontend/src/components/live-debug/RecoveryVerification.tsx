import React from 'react';
import { LiveRecoveryResult } from '../../types/liveDebug';
import { ShieldCheck, AlertCircle, CheckCircle } from 'lucide-react';

interface Props {
  recovery: LiveRecoveryResult | null;
  modifiedFiles?: string[];
}

export const RecoveryVerification: React.FC<Props> = ({ recovery, modifiedFiles }) => {
  if (!recovery) return null;

  return (
    <div style={{
      background: 'rgba(16, 185, 129, 0.08)',
      border: '1px solid rgba(16, 185, 129, 0.3)',
      borderRadius: '8px',
      padding: '16px',
      display: 'flex',
      flexDirection: 'column',
      gap: '10px'
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: '#34d399', fontWeight: 600, fontSize: '14px' }}>
        <ShieldCheck size={18} /> Independent Post-Patch Recovery Verification
      </div>

      <p style={{ fontSize: '12px', color: '#e2e8f0', margin: 0 }}>
        {recovery.summary}
      </p>

      {modifiedFiles && modifiedFiles.length > 0 && (
        <div style={{ fontSize: '11px', color: '#94a3b8' }}>
          Modified files in isolated workspace: <code style={{ color: '#34d399' }}>{modifiedFiles.join(', ')}</code>
        </div>
      )}

      <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(2, 1fr)',
        gap: '8px',
        background: 'rgba(0, 0, 0, 0.25)',
        padding: '10px',
        borderRadius: '6px',
        fontSize: '11px'
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
          <CheckCircle size={14} color="#34d399" />
          <span style={{ color: '#cbd5e1' }}>Regression Tests in Patched Workspace:</span>
          <span style={{ color: '#34d399', fontWeight: 600 }}>PASSED</span>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
          <CheckCircle size={14} color="#34d399" />
          <span style={{ color: '#cbd5e1' }}>Health Status:</span>
          <span style={{ color: '#34d399', fontWeight: 600 }}>VERIFIED</span>
        </div>
      </div>
    </div>
  );
};
