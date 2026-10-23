import React, { useState } from 'react';
import { RemediationProposal, PolicyDecision, InvestigationPhase } from '../types/incident';
import { ShieldAlert, CheckCircle2, XCircle, AlertTriangle } from 'lucide-react';

interface SafetyApprovalCardProps {
  proposal?: RemediationProposal;
  policyDecision?: PolicyDecision;
  currentPhase: InvestigationPhase;
  executionStatus: string;
  onApprove: (approver: string, comment: string) => Promise<void>;
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
  const [approver, setApprover] = useState('incident_lead@corp.internal');
  const [isSubmitting, setIsSubmitting] = useState(false);

  if (!proposal) return null;

  const isAwaitingApproval = currentPhase === 'AWAITING_APPROVAL';

  const handleApprove = async () => {
    setIsSubmitting(true);
    try {
      await onApprove(approver, "Operator authorized rollback and callback replay in simulator");
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
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '11px', color: '#cbd5e1' }}>
            <span>Approver:</span>
            <input
              type="text"
              value={approver}
              onChange={(e) => setApprover(e.target.value)}
              style={{
                flex: 1,
                background: '#090d16',
                border: '1px solid rgba(255, 255, 255, 0.15)',
                color: '#fff',
                padding: '4px 8px',
                borderRadius: '4px',
                fontSize: '11px',
                fontFamily: 'var(--font-mono)'
              }}
            />
          </div>

          <div style={{ display: 'flex', gap: '8px' }}>
            <button
              onClick={handleApprove}
              disabled={isSubmitting}
              style={{
                flex: 1,
                background: 'linear-gradient(135deg, #10b981, #059669)',
                color: '#fff',
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
                boxShadow: '0 0 12px rgba(16, 185, 129, 0.3)'
              }}
            >
              <CheckCircle2 size={14} />
              {isSubmitting ? 'Executing in Simulator...' : 'Approve & Execute Remediation'}
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
