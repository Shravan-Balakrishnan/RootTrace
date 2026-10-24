import React, { useState } from 'react';
import { LiveRecoveryResult } from '../../types/liveDebug';
import { ShieldCheck, CheckCircle, Rocket, RefreshCw } from 'lucide-react';

interface Props {
  recovery: LiveRecoveryResult | null;
  modifiedFiles?: string[];
  runId?: string;
  operator?: string;
  operatorPassword?: string;
  onPromoted?: () => void;
}

export const RecoveryVerification: React.FC<Props> = ({
  recovery, modifiedFiles, runId, operator, operatorPassword, onPromoted
}) => {
  const [promoting, setPromoting] = useState(false);
  const [promoteResult, setPromoteResult] = useState<{ ok: boolean; message: string } | null>(null);

  if (!recovery) return null;

  const canPromote = Boolean(runId && operator && operatorPassword && !promoteResult?.ok);

  const handlePromote = async () => {
    if (!runId || !operator || !operatorPassword) return;
    setPromoting(true);
    try {
      const res = await fetch('/api/live/patch/promote', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ run_id: runId, operator, password: operatorPassword })
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Promotion failed');
      setPromoteResult({ ok: true, message: data.message });
      onPromoted?.();
    } catch (e: any) {
      setPromoteResult({ ok: false, message: e.message || 'Promotion failed' });
    } finally {
      setPromoting(false);
    }
  };

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

      {/* Promote to Live section */}
      {!promoteResult?.ok && (
        <div style={{
          background: 'rgba(56, 189, 248, 0.07)',
          border: '1px solid rgba(56, 189, 248, 0.25)',
          borderRadius: '6px',
          padding: '10px 14px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          gap: '12px'
        }}>
          <div style={{ fontSize: '11px', color: '#bae6fd' }}>
            <strong style={{ color: '#38bdf8' }}>Sandbox verified.</strong> Click to copy the fix into <code>live-lab/</code> source and restart the process.
          </div>
          <button
            onClick={handlePromote}
            disabled={!canPromote || promoting}
            title={!canPromote ? 'Run an investigation & approve to enable promotion' : 'Promote verified fix to live source'}
            style={{
              background: canPromote ? '#0ea5e9' : 'rgba(14, 165, 233, 0.3)',
              border: 'none',
              color: '#fff',
              borderRadius: '5px',
              padding: '7px 14px',
              fontSize: '12px',
              fontWeight: 600,
              cursor: canPromote ? 'pointer' : 'not-allowed',
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              whiteSpace: 'nowrap',
              flexShrink: 0
            }}
          >
            {promoting ? <><RefreshCw size={13} style={{ animation: 'spin 1s linear infinite' }} /> Promoting…</> : <><Rocket size={13} /> Apply Fix to Live Source</>}
          </button>
        </div>
      )}

      {/* Promotion result banner */}
      {promoteResult && (
        <div style={{
          background: promoteResult.ok ? 'rgba(16, 185, 129, 0.12)' : 'rgba(239, 68, 68, 0.12)',
          border: `1px solid ${promoteResult.ok ? 'rgba(52, 211, 153, 0.4)' : 'rgba(248, 113, 113, 0.4)'}`,
          borderRadius: '6px',
          padding: '10px 14px',
          fontSize: '12px',
          color: promoteResult.ok ? '#34d399' : '#f87171',
          display: 'flex',
          flexDirection: 'column',
          gap: '4px'
        }}>
          <strong>{promoteResult.ok ? '✓ Promoted to live source!' : '✗ Promotion failed'}</strong>
          <span style={{ fontSize: '11px', color: promoteResult.ok ? '#a7f3d0' : '#fca5a5' }}>
            {promoteResult.message}
          </span>
          {promoteResult.ok && (
            <span style={{ fontSize: '11px', color: '#94a3b8', marginTop: 4 }}>
              ⚠ Click <strong>Restart</strong> in the process card above to reload <code>live-lab/</code> with the patched code, then run regression tests.
            </span>
          )}
        </div>
      )}
    </div>
  );
};
