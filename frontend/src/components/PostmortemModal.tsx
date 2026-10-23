import React from 'react';
import { IncidentReport } from '../types/incident';
import { X, FileText, CheckCircle2, ShieldAlert } from 'lucide-react';

interface PostmortemModalProps {
  postmortem?: IncidentReport;
  onClose: () => void;
}

export const PostmortemModal: React.FC<PostmortemModalProps> = ({ postmortem, onClose }) => {
  if (!postmortem) return null;

  return (
    <div style={{
      position: 'fixed',
      inset: 0,
      background: 'rgba(0, 0, 0, 0.8)',
      backdropFilter: 'blur(8px)',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      zIndex: 1000
    }}>
      <div style={{
        background: '#0d131f',
        border: '1px solid rgba(255, 255, 255, 0.15)',
        borderRadius: '12px',
        width: '90%',
        maxWidth: '740px',
        maxHeight: '85vh',
        display: 'flex',
        flexDirection: 'column',
        boxShadow: '0 25px 50px -12px rgba(0, 0, 0, 0.8)'
      }}>
        {/* Header */}
        <div style={{
          padding: '16px 20px',
          borderBottom: '1px solid rgba(255, 255, 255, 0.08)',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center'
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <FileText size={18} color="#06b6d4" />
            <span style={{ fontSize: '14px', fontWeight: 700, color: '#f8fafc' }}>
              Verified Postmortem: {postmortem.incident_id}
            </span>
          </div>
          <button
            onClick={onClose}
            style={{
              background: 'transparent',
              border: 'none',
              color: '#94a3b8',
              cursor: 'pointer'
            }}
          >
            <X size={18} />
          </button>
        </div>

        {/* Content */}
        <div style={{ padding: '24px', overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: '16px' }}>
          <div>
            <h2 style={{ fontSize: '18px', fontWeight: 800, color: '#f8fafc', marginBottom: '4px' }}>
              {postmortem.title}
            </h2>
            <div style={{ fontSize: '11px', color: '#64748b', fontFamily: 'var(--font-mono)' }}>
              Scenario: {postmortem.scenario_id} | Severity: {postmortem.severity} | Started: {postmortem.started_at} | Resolved: {postmortem.resolved_at}
            </div>
          </div>

          <div style={{
            background: 'rgba(16, 185, 129, 0.06)',
            border: '1px solid rgba(16, 185, 129, 0.25)',
            borderRadius: '8px',
            padding: '12px 14px'
          }}>
            <h3 style={{ fontSize: '12px', color: '#34d399', textTransform: 'uppercase', marginBottom: '4px' }}>
              Verified Root Cause
            </h3>
            <p style={{ fontSize: '13px', color: '#f8fafc', lineHeight: 1.4 }}>
              {postmortem.root_cause}
            </p>
          </div>

          <div>
            <h3 style={{ fontSize: '12px', color: '#94a3b8', textTransform: 'uppercase', marginBottom: '6px' }}>
              Remediation Action & Simulator Invariants
            </h3>
            <p style={{ fontSize: '12px', color: '#cbd5e1', lineHeight: 1.4 }}>
              {postmortem.remediation_summary}
            </p>
          </div>

          {postmortem.rejected_hypotheses.length > 0 && (
            <div>
              <h3 style={{ fontSize: '12px', color: '#f43f5e', textTransform: 'uppercase', marginBottom: '6px' }}>
                Falsified Red Herrings & Competing Hypotheses
              </h3>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                {postmortem.rejected_hypotheses.map((h, i) => (
                  <div key={i} style={{ background: 'rgba(255, 255, 255, 0.03)', padding: '8px 10px', borderRadius: '6px', fontSize: '11px' }}>
                    <strong style={{ color: '#fda4af' }}>{h.title}: </strong>
                    <span style={{ color: '#94a3b8' }}>{h.rejection}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          <div>
            <h3 style={{ fontSize: '12px', color: '#38bdf8', textTransform: 'uppercase', marginBottom: '6px' }}>
              Preventive Recommendations
            </h3>
            <ul style={{ paddingLeft: '18px', fontSize: '12px', color: '#cbd5e1', display: 'flex', flexDirection: 'column', gap: '4px' }}>
              {postmortem.preventive_recommendations.map((rec, i) => (
                <li key={i}>{rec}</li>
              ))}
            </ul>
          </div>
        </div>
      </div>
    </div>
  );
};
