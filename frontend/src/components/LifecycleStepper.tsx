import React from 'react';
import { InvestigationPhase } from '../types/incident';
import { CheckCircle2, Clock, AlertCircle } from 'lucide-react';

interface LifecycleStepperProps {
  currentPhase: InvestigationPhase;
}

const PHASES: Array<{ id: InvestigationPhase; label: string }> = [
  { id: 'TRIGGERED', label: '1. Incident Trigger' },
  { id: 'OBSERVING', label: '2. Observe' },
  { id: 'COLLECTING_INITIAL_EVIDENCE', label: '3. Collect Evidence' },
  { id: 'BUILDING_TIMELINE', label: '4. Build Timeline' },
  { id: 'HYPOTHESIS_GENERATION', label: '5. Hypotheses' },
  { id: 'INVESTIGATING', label: '6. Investigate' },
  { id: 'CRITIQUE', label: '7. Critic / Falsify' },
  { id: 'VERIFYING', label: '8. Verify' },
  { id: 'AWAITING_APPROVAL', label: '9. Human Approval' },
  { id: 'REMEDIATING', label: '10. Remediate' },
  { id: 'VERIFYING_RECOVERY', label: '11. Verify Recovery' },
  { id: 'RESOLVED', label: '12. Resolved' },
];

export const LifecycleStepper: React.FC<LifecycleStepperProps> = ({ currentPhase }) => {
  const currentIndex = PHASES.findIndex((p) => p.id === currentPhase);

  return (
    <div style={{
      display: 'flex',
      alignItems: 'center',
      gap: '4px',
      overflowX: 'auto',
      padding: '8px 16px',
      background: 'rgba(15, 23, 42, 0.6)',
      borderBottom: '1px solid rgba(255, 255, 255, 0.06)',
      fontSize: '11px',
      fontFamily: 'var(--font-mono)'
    }}>
      {PHASES.map((phase, idx) => {
        const isCompleted = currentIndex > idx || currentPhase === 'RESOLVED';
        const isActive = phase.id === currentPhase;

        let badgeBg = 'rgba(255, 255, 255, 0.03)';
        let textColor = '#64748b';
        let borderColor = 'rgba(255, 255, 255, 0.05)';

        if (isCompleted) {
          badgeBg = 'rgba(16, 185, 129, 0.08)';
          textColor = '#34d399';
          borderColor = 'rgba(16, 185, 129, 0.25)';
        } else if (isActive) {
          badgeBg = 'rgba(14, 165, 233, 0.15)';
          textColor = '#38bdf8';
          borderColor = 'rgba(14, 165, 233, 0.4)';
        }

        return (
          <div
            key={phase.id}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              padding: '4px 10px',
              borderRadius: '6px',
              background: badgeBg,
              color: textColor,
              border: `1px solid ${borderColor}`,
              whiteSpace: 'nowrap',
              transition: 'all 0.2s ease',
              boxShadow: isActive ? '0 0 10px rgba(14, 165, 233, 0.25)' : 'none',
              fontWeight: isActive ? 600 : 400
            }}
          >
            {isCompleted ? (
              <CheckCircle2 size={12} color="#10b981" />
            ) : isActive ? (
              <Clock size={12} color="#06b6d4" className="animate-spin" />
            ) : (
              <span style={{ width: '12px', height: '12px', borderRadius: '50%', background: '#334155', display: 'inline-block' }} />
            )}
            <span>{phase.label}</span>
          </div>
        );
      })}
    </div>
  );
};
