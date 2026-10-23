import React from 'react';
import { Hypothesis, CriticEvaluation } from '../../types/liveDebug';
import { HelpCircle, CheckCircle2, XCircle, ShieldAlert } from 'lucide-react';

interface Props {
  hypotheses: Hypothesis[];
  critic?: CriticEvaluation | null;
  diagnosis?: string;
  abstained?: boolean;
  abstentionReason?: string | null;
}

export const HypothesisCriticCard: React.FC<Props> = ({
  hypotheses,
  critic,
  diagnosis,
  abstained,
  abstentionReason
}) => {
  if (abstained) {
    return (
      <div style={{
        background: 'rgba(30, 41, 59, 0.7)',
        border: '1px solid rgba(245, 158, 11, 0.3)',
        borderRadius: '8px',
        padding: '16px',
        display: 'flex',
        flexDirection: 'column',
        gap: '8px'
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: '#fbbf24', fontWeight: 600, fontSize: '13px' }}>
          <ShieldAlert size={16} /> Investigation Abstained
        </div>
        <p style={{ fontSize: '12px', color: '#cbd5e1', margin: 0 }}>
          {abstentionReason || 'The system abstained from proposing a patch because evidence is insufficient or contradictory.'}
        </p>
      </div>
    );
  }

  if (!hypotheses || hypotheses.length === 0) {
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
      gap: '12px'
    }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <span style={{ fontSize: '13px', fontWeight: 600, color: '#f8fafc' }}>
          Competing Hypotheses & Critic Falsification
        </span>
        {critic && (
          <span style={{
            fontSize: '11px',
            padding: '2px 8px',
            borderRadius: '4px',
            fontWeight: 600,
            background: critic.has_falsified_leading_hypothesis ? 'rgba(239, 68, 68, 0.2)' : 'rgba(16, 185, 129, 0.2)',
            color: critic.has_falsified_leading_hypothesis ? '#f87171' : '#34d399'
          }}>
            Critic: {critic.has_falsified_leading_hypothesis ? 'VETO TRIGGERED' : 'APPROVED'}
          </span>
        )}
      </div>

      {diagnosis && (
        <div style={{
          background: 'rgba(99, 102, 241, 0.12)',
          borderLeft: '3px solid #6366f1',
          padding: '8px 12px',
          borderRadius: '4px',
          fontSize: '12px',
          color: '#e0e7ff'
        }}>
          <strong>Diagnosis:</strong> {diagnosis}
        </div>
      )}

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '10px' }}>
        {hypotheses.map((h, i) => {
          const isLeading = i === 0;
          return (
            <div
              key={h.id}
              style={{
                background: isLeading ? 'rgba(56, 189, 248, 0.05)' : 'rgba(0, 0, 0, 0.2)',
                border: isLeading ? '1px solid rgba(56, 189, 248, 0.3)' : '1px solid rgba(255, 255, 255, 0.08)',
                borderRadius: '6px',
                padding: '12px',
                display: 'flex',
                flexDirection: 'column',
                gap: '6px'
              }}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                <span style={{ fontSize: '12px', fontWeight: 600, color: isLeading ? '#38bdf8' : '#e2e8f0' }}>
                  {h.title}
                </span>
                <span style={{
                  fontSize: '10px',
                  fontFamily: 'var(--font-mono)',
                  padding: '1px 6px',
                  borderRadius: '3px',
                  background: 'rgba(255, 255, 255, 0.1)',
                  color: '#f8fafc'
                }}>
                  {Math.round(h.score * 100)}% Match
                </span>
              </div>

              <p style={{ fontSize: '11px', color: '#94a3b8', margin: 0 }}>
                {h.description}
              </p>

              <div style={{ fontSize: '10px', color: '#64748b', marginTop: '4px' }}>
                <span>Supporting evidence: </span>
                <span style={{ color: '#38bdf8' }}>{h.supporting_evidence_ids.join(', ') || 'None'}</span>
              </div>
            </div>
          );
        })}
      </div>

      {critic && (
        <div style={{
          background: 'rgba(0, 0, 0, 0.3)',
          border: '1px solid rgba(255, 255, 255, 0.08)',
          borderRadius: '6px',
          padding: '10px',
          fontSize: '11px',
          color: '#cbd5e1'
        }}>
          <span style={{ fontWeight: 600, color: '#f8fafc' }}>Critic Findings: </span>
          {critic.critique_summary}
        </div>
      )}
    </div>
  );
};
