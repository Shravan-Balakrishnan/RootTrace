import React, { useState } from 'react';
import { RemediationProposal, PolicyDecision, InvestigationPhase } from '../types/incident';
import { ShieldAlert, CheckCircle2, XCircle, AlertTriangle } from 'lucide-react';

interface SafetyApprovalCardProps {
  proposal?: RemediationProposal;
  policyDecision?: PolicyDecision;
  currentPhase: InvestigationPhase;
  executionStatus: string;
  onApprove: (authToken: string, comment: string) => Promise<void>;
  onReject: () => Promise<void>;
}

export const SafetyApprovalCard: React.FC<SafetyApprovalCardProps> = ({
  proposal,
  policyDecision,
  currentPhase,
  executionStatus,
  onApprove,
  onReject
}) => {
  const [selectedEmail, setSelectedEmail] = useState('lead_sre@company.com');
  const [password, setPassword] = useState('');
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  if (!proposal) return null;

  const isAwaitingApproval = currentPhase === 'AWAITING_APPROVAL';

  const handleApprove = async () => {
    setIsSubmitting(true);
    setErrorMessage(null);
    try {
      // Authenticate with verified credentials against server directory
      const sessionRes = await fetch('/api/auth/session', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: selectedEmail, password })
      });
      if (!sessionRes.ok) {
        const errData = await sessionRes.json();
        throw new Error(errData.detail || 'Authentication failed: Invalid credentials.');
      }
      const sessionData = await sessionRes.json();
      await onApprove(sessionData.session_token, "Operator authorized rollback and callback replay in simulator");
    } catch (err: any) {
      setErrorMessage(err?.message || "Approval authorization failed.");
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div style={{
      background: 'rgba(245, 158, 11, 0.05)',
      border: '1px solid rgba(245, 158, 11, 0.35)',
      borderRadius: '8px',
      padding: '14px',
      display: 'flex',
      flexDirection: 'column',
      gap: '8px'
    }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
          <ShieldAlert size={16} color="#f59e0b" />
          <strong style={{ fontSize: '12px', color: '#fbbf24', textTransform: 'uppercase', letterSpacing: '0.5px' }}>
            Safety Policy Enforcement: {policyDecision?.decision || 'HUMAN_APPROVAL_REQUIRED'}
          </strong>
        </div>
        <span style={{
          fontSize: '10px',
          fontWeight: 700,
          background: 'rgba(245, 158, 11, 0.2)',
          color: '#fbbf24',
          padding: '2px 6px',
          borderRadius: '4px'
        }}>
          {proposal.risk}
        </span>
      </div>

      <div style={{ fontSize: '13px', fontWeight: 600, color: '#f8fafc' }}>
        {proposal.description}
      </div>

      <div style={{
        display: 'grid',
        gridTemplateColumns: '1fr 1fr',
        gap: '8px',
        background: 'rgba(0, 0, 0, 0.25)',
        padding: '8px 10px',
        borderRadius: '6px',
        fontSize: '11px',
        color: '#94a3b8'
      }}>
        <div><strong>Reversibility:</strong> {proposal.reversibility}</div>
        <div><strong>Blast Radius:</strong> {proposal.blast_radius}</div>
        <div><strong>Target:</strong> {proposal.target_service}</div>
        <div><strong>Parameters:</strong> {JSON.stringify(proposal.parameters)}</div>
      </div>

      {isAwaitingApproval ? (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', marginTop: '4px' }}>
          <div style={{ display: 'flex', gap: '8px', fontSize: '11px', color: '#cbd5e1' }}>
            <div style={{ flex: 2, display: 'flex', alignItems: 'center', gap: '6px' }}>
              <span style={{ fontWeight: 600 }}>Operator:</span>
              <select
                value={selectedEmail}
                onChange={(e) => {
                  const newEmail = e.target.value;
                  setSelectedEmail(newEmail);
                  setPassword('');
                  setErrorMessage(null);
                }}
                style={{
                  flex: 1,
                  background: '#090d16',
                  border: '1px solid rgba(255, 255, 255, 0.2)',
                  color: selectedEmail === 'intern_observer@company.com' ? '#f87171' : '#34d399',
                  padding: '6px 8px',
                  borderRadius: '4px',
                  fontSize: '11px',
                  fontWeight: 600,
                  fontFamily: 'var(--font-mono)'
                }}
              >
                <option value="lead_sre@company.com">lead_sre@company.com [Verified Role: lead_sre — Authorized]</option>
                <option value="incident_commander@company.com">incident_commander@company.com [Verified Role: incident_commander — Authorized]</option>
                <option value="oncall_sre@company.com">oncall_sre@company.com [Verified Role: oncall_sre — Authorized]</option>
                <option value="intern_observer@company.com">intern_observer@company.com [Verified Role: intern — 403 Forbidden]</option>
              </select>
            </div>
            <div style={{ flex: 1, display: 'flex', alignItems: 'center', gap: '6px' }}>
              <span style={{ fontWeight: 600 }}>Credential:</span>
              <input
                type="password"
                value={password}
                onChange={(e) => {
                  setPassword(e.target.value);
                  setErrorMessage(null);
                }}
                placeholder="Password"
                style={{
                  flex: 1,
                  background: '#090d16',
                  border: '1px solid rgba(255, 255, 255, 0.2)',
                  color: '#fff',
                  padding: '6px 8px',
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
              border: '1px solid rgba(239, 68, 68, 0.4)',
              color: '#f87171',
              padding: '6px 10px',
              borderRadius: '4px',
              fontSize: '11px',
              display: 'flex',
              alignItems: 'center',
              gap: '6px'
            }}>
              <AlertTriangle size={14} />
              <span>{errorMessage}</span>
            </div>
          )}

          <div style={{ display: 'flex', gap: '8px' }}>
            <button
              onClick={handleApprove}
              disabled={isSubmitting}
              style={{
                flex: 1,
                background: isSubmitting ? '#334155' : (selectedEmail === 'intern_observer@company.com' ? '#7f1d1d' : 'linear-gradient(135deg, #10b981, #059669)'),
                color: isSubmitting ? '#94a3b8' : '#fff',
                border: 'none',
                padding: '8px 14px',
                borderRadius: '6px',
                fontSize: '12px',
                fontWeight: 600,
                cursor: isSubmitting ? 'not-allowed' : 'pointer',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                gap: '6px',
                boxShadow: isSubmitting ? 'none' : (selectedEmail === 'intern_observer@company.com' ? '0 0 10px rgba(239, 68, 68, 0.3)' : '0 0 12px rgba(16, 185, 129, 0.3)')
              }}
            >
              <CheckCircle2 size={14} />
              {isSubmitting ? 'Authenticating Session & Executing...' : (selectedEmail === 'intern_observer@company.com' ? 'Test Unauthorized Operator (Expect 403 Block)' : 'Authorize & Execute Verified Remediation')}
            </button>

            <button
              onClick={onReject}
              disabled={isSubmitting}
              style={{
                background: 'rgba(239, 68, 68, 0.15)',
                color: '#f87171',
                border: '1px solid rgba(239, 68, 68, 0.3)',
                padding: '8px 12px',
                borderRadius: '6px',
                fontSize: '12px',
                fontWeight: 600,
                cursor: isSubmitting ? 'not-allowed' : 'pointer',
                display: 'flex',
                alignItems: 'center',
                gap: '4px'
              }}
            >
              <XCircle size={14} />
              Reject Action
            </button>
          </div>
        </div>
      ) : (
        <div style={{ fontSize: '11px', color: '#34d399', display: 'flex', alignItems: 'center', gap: '6px' }}>
          <CheckCircle2 size={13} />
          <span>Status: Remediation Authorized ({executionStatus})</span>
        </div>
      )}
    </div>
  );
};
