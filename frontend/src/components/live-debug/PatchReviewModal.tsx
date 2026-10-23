import React, { useState } from 'react';
import { PatchProposal } from '../../types/liveDebug';
import { GitCommit, ShieldCheck, XCircle, CheckCircle2, Lock } from 'lucide-react';

interface Props {
  proposal: PatchProposal;
  onApprove: (token: string) => Promise<void>;
  onReject: () => Promise<void>;
  isApplying: boolean;
}

const DEFAULT_PASSWORDS: Record<string, string> = {
  'lead_sre@company.com': 'LeadSRE-Prod-Auth-2026!',
  'incident_commander@company.com': 'Commander-SecOps-2026!',
  'oncall_sre@company.com': 'OnCall-Incident-2026!',
  'intern_observer@company.com': 'Intern-Guest-2026!'
};

export const PatchReviewModal: React.FC<Props> = ({
  proposal,
  onApprove,
  onReject,
  isApplying
}) => {
  const [selectedEmail, setSelectedEmail] = useState('lead_sre@company.com');
  const [password, setPassword] = useState(DEFAULT_PASSWORDS['lead_sre@company.com']);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const handleApprove = async () => {
    setErrorMessage(null);
    try {
      // 1. Authenticate to obtain ephemeral session token
      const sessionRes = await fetch('/api/auth/session', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: selectedEmail, password })
      });
      if (!sessionRes.ok) {
        const err = await sessionRes.json().catch(() => ({}));
        throw new Error(err.detail || 'Authentication failed: Invalid credentials.');
      }
      const data = await sessionRes.json();
      await onApprove(data.session_token);
    } catch (e: any) {
      setErrorMessage(e.message || 'Approval failed');
    }
  };

  return (
    <div style={{
      background: 'rgba(15, 23, 42, 0.95)',
      border: '1px solid rgba(99, 102, 241, 0.3)',
      borderRadius: '8px',
      padding: '20px',
      display: 'flex',
      flexDirection: 'column',
      gap: '14px',
      boxShadow: '0 8px 32px rgba(0, 0, 0, 0.5)'
    }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <GitCommit size={18} color="#6366f1" />
          <span style={{ fontSize: '14px', fontWeight: 600, color: '#f8fafc' }}>
            Candidate Patch Proposal: {proposal.title}
          </span>
        </div>
        <span style={{
          fontSize: '11px',
          fontFamily: 'var(--font-mono)',
          color: '#38bdf8',
          background: 'rgba(56, 189, 248, 0.1)',
          padding: '2px 8px',
          borderRadius: '4px'
        }}>
          SHA-256: {proposal.patch_hash.substring(0, 16)}...
        </span>
      </div>

      <p style={{ fontSize: '12px', color: '#cbd5e1', margin: 0 }}>
        {proposal.explanation}
      </p>

      {/* Unified Diff View */}
      <div style={{
        background: '#090d16',
        borderRadius: '6px',
        border: '1px solid rgba(255, 255, 255, 0.1)',
        padding: '12px',
        fontFamily: 'var(--font-mono)',
        fontSize: '11px',
        maxHeight: '220px',
        overflowY: 'auto'
      }}>
        {proposal.diff.split('\n').map((line, idx) => {
          let color = '#94a3b8';
          let bg = 'transparent';
          if (line.startsWith('+')) {
            color = '#34d399';
            bg = 'rgba(16, 185, 129, 0.1)';
          } else if (line.startsWith('-')) {
            color = '#f87171';
            bg = 'rgba(239, 68, 68, 0.1)';
          } else if (line.startsWith('@@')) {
            color = '#38bdf8';
          }
          return (
            <div key={idx} style={{ color, background: bg, padding: '1px 4px' }}>
              {line}
            </div>
          );
        })}
      </div>

      <div style={{ fontSize: '11px', color: '#94a3b8' }}>
        Target Workspace: <code style={{ color: '#f8fafc' }}>{proposal.target_workspace}</code> (Isolated sandbox)
      </div>

      {/* Operator Credential Verification */}
      <div style={{
        display: 'flex',
        gap: '8px',
        alignItems: 'center',
        background: 'rgba(0, 0, 0, 0.25)',
        padding: '10px',
        borderRadius: '6px'
      }}>
        <div style={{ flex: 2, display: 'flex', alignItems: 'center', gap: '6px', fontSize: '11px' }}>
          <span style={{ color: '#cbd5e1', fontWeight: 600 }}>Operator:</span>
          <select
            value={selectedEmail}
            onChange={(e) => {
              const email = e.target.value;
              setSelectedEmail(email);
              setPassword(DEFAULT_PASSWORDS[email] || '');
              setErrorMessage(null);
            }}
            style={{
              flex: 1,
              background: '#090d16',
              border: '1px solid rgba(255, 255, 255, 0.2)',
              color: '#fff',
              padding: '5px 8px',
              borderRadius: '4px',
              fontSize: '11px'
            }}
          >
            <option value="lead_sre@company.com">lead_sre@company.com [Role: lead_sre]</option>
            <option value="incident_commander@company.com">incident_commander@company.com [Role: incident_commander]</option>
            <option value="oncall_sre@company.com">oncall_sre@company.com [Role: oncall_sre]</option>
            <option value="intern_observer@company.com">intern_observer@company.com [Role: intern — Forbidden]</option>
          </select>
        </div>

        <div style={{ flex: 1, display: 'flex', alignItems: 'center', gap: '6px', fontSize: '11px' }}>
          <span style={{ color: '#cbd5e1', fontWeight: 600 }}>Password:</span>
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            style={{
              flex: 1,
              background: '#090d16',
              border: '1px solid rgba(255, 255, 255, 0.2)',
              color: '#fff',
              padding: '5px 8px',
              borderRadius: '4px',
              fontSize: '11px',
              fontFamily: 'var(--font-mono)'
            }}
          />
        </div>
      </div>

      {errorMessage && (
        <div style={{
          background: 'rgba(239, 68, 68, 0.15)',
          border: '1px solid rgba(239, 68, 68, 0.3)',
          color: '#f87171',
          padding: '8px',
          borderRadius: '4px',
          fontSize: '11px'
        }}>
          {errorMessage}
        </div>
      )}

      <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '10px' }}>
        <button
          onClick={onReject}
          disabled={isApplying}
          style={{
            background: 'transparent',
            border: '1px solid rgba(255, 255, 255, 0.2)',
            color: '#cbd5e1',
            borderRadius: '4px',
            padding: '6px 14px',
            fontSize: '12px',
            cursor: 'pointer'
          }}
        >
          Reject Proposal
        </button>

        <button
          onClick={handleApprove}
          disabled={isApplying}
          style={{
            background: '#10b981',
            border: 'none',
            color: '#fff',
            borderRadius: '4px',
            padding: '6px 16px',
            fontSize: '12px',
            fontWeight: 600,
            cursor: isApplying ? 'wait' : 'pointer',
            display: 'flex',
            alignItems: 'center',
            gap: '6px'
          }}
        >
          <CheckCircle2 size={14} />
          {isApplying ? 'Applying to Workspace...' : 'Approve & Apply to Workspace'}
        </button>
      </div>
    </div>
  );
};
