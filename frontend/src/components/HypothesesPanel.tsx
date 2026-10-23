import React from 'react';
import { Hypothesis, CriticEvaluation } from '../types/incident';
import { CheckCircle, XCircle, AlertTriangle, HelpCircle, ShieldCheck } from 'lucide-react';

interface HypothesesPanelProps {
  hypotheses: Hypothesis[];
  criticEvaluations: CriticEvaluation[];
}

export const HypothesesPanel: React.FC<HypothesesPanelProps> = ({
  hypotheses,
  criticEvaluations
}) => {
  if (!hypotheses || hypotheses.length === 0) {
    return (
      <div style={{ padding: '16px', color: '#64748b', fontSize: '12px', textAlign: 'center' }}>
        No hypotheses formulated yet. Advance to phase 5 (HYPOTHESIS_GENERATION).
      </div>
    );
  }

  // Find critic eval by hypothesis id
  const getCriticEval = (id: string) => criticEvaluations.find((c) => c.hypothesis_id === id);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
      {hypotheses.map((h) => {
        const critic = getCriticEval(h.id);
        const isVerified = h.status === 'VERIFIED';
        const isFalsified = h.status === 'FALSIFIED';
        const isSupported = h.status === 'SUPPORTED';

        let borderColor = 'rgba(255, 255, 255, 0.08)';
        let badgeBg = 'rgba(100, 116, 139, 0.2)';
        let badgeColor = '#94a3b8';

        if (isVerified) {
          borderColor = '#10b981';
          badgeBg = 'rgba(16, 185, 129, 0.15)';
          badgeColor = '#34d399';
        } else if (isFalsified) {
          borderColor = '#f43f5e';
          badgeBg = 'rgba(244, 63, 94, 0.15)';
          badgeColor = '#fda4af';
        } else if (isSupported) {
          borderColor = '#0ea5e9';
          badgeBg = 'rgba(14, 165, 233, 0.15)';
          badgeColor = '#38bdf8';
        }

        return (
          <div
            key={h.id}
            style={{
              background: 'rgba(17, 24, 39, 0.75)',
              border: `1px solid ${borderColor}`,
              borderLeft: `4px solid ${borderColor}`,
              borderRadius: '8px',
              padding: '12px',
              display: 'flex',
              flexDirection: 'column',
              gap: '6px',
              transition: 'all 0.2s ease'
            }}
          >
            {/* Header */}
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                {isVerified ? (
                  <ShieldCheck size={16} color="#10b981" />
                ) : isFalsified ? (
                  <XCircle size={16} color="#f43f5e" />
                ) : (
                  <HelpCircle size={16} color="#38bdf8" />
                )}
                <span style={{ fontSize: '13px', fontWeight: 600, color: '#f8fafc' }}>
                  {h.title}
                </span>
              </div>
              <span style={{
                fontSize: '10px',
                fontWeight: 700,
                fontFamily: 'var(--font-mono)',
                background: badgeBg,
                color: badgeColor,
                padding: '2px 6px',
                borderRadius: '4px'
              }}>
                {h.status}
              </span>
            </div>

            {/* Description */}
            <p style={{ fontSize: '11px', color: '#94a3b8', lineHeight: 1.4 }}>
              {h.description}
            </p>

            {/* Metrics & Evidence Counts */}
            <div style={{
              display: 'flex',
              alignItems: 'center',
              gap: '12px',
              fontSize: '11px',
              fontFamily: 'var(--font-mono)',
              marginTop: '2px'
            }}>
              <span style={{ color: h.score >= 0.5 ? '#34d399' : h.score < 0 ? '#fda4af' : '#cbd5e1' }}>
                Support Score: {h.score > 0 ? `+${h.score}` : h.score}
              </span>
              <span style={{ color: '#34d399' }}>
                Supporting: {h.supporting_evidence_ids.length}
              </span>
              <span style={{ color: '#fda4af' }}>
                Contradictions: {h.contradicting_evidence_ids.length}
              </span>
            </div>

            {/* Critic Falsification or Counterargument */}
            {critic && (
              <div style={{
                background: critic.is_valid_candidate ? 'rgba(16, 185, 129, 0.06)' : 'rgba(244, 63, 94, 0.08)',
                border: `1px solid ${critic.is_valid_candidate ? 'rgba(16, 185, 129, 0.2)' : 'rgba(244, 63, 94, 0.25)'}`,
                padding: '8px 10px',
                borderRadius: '6px',
                fontSize: '11px',
                marginTop: '4px'
              }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '2px' }}>
                  <AlertTriangle size={12} color={critic.is_valid_candidate ? '#10b981' : '#f43f5e'} />
                  <strong style={{ color: critic.is_valid_candidate ? '#34d399' : '#f87171' }}>
                    {critic.is_valid_candidate ? 'Critic Check Passed:' : 'Critic Red-Team Counterargument:'}
                  </strong>
                </div>
                <div style={{ color: '#cbd5e1', lineHeight: 1.3 }}>
                  {critic.critique_summary}
                </div>
                {critic.missing_evidence_found.length > 0 && (
                  <div style={{ color: '#f59e0b', marginTop: '4px', fontSize: '10px' }}>
                    Evidence Requested: {critic.missing_evidence_found.join('; ')}
                  </div>
                )}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
};
