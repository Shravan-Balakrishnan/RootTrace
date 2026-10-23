import React from 'react';
import { EvidenceRecord } from '../types/incident';
import { X, Database, Terminal, Shield } from 'lucide-react';

interface EvidenceModalProps {
  evidence: EvidenceRecord | null;
  onClose: () => void;
}

export const EvidenceModal: React.FC<EvidenceModalProps> = ({ evidence, onClose }) => {
  if (!evidence) return null;

  return (
    <div style={{
      position: 'fixed',
      inset: 0,
      background: 'rgba(0, 0, 0, 0.75)',
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
        maxWidth: '680px',
        maxHeight: '85vh',
        display: 'flex',
        flexDirection: 'column',
        boxShadow: '0 25px 50px -12px rgba(0, 0, 0, 0.8)'
      }}>
        {/* Header */}
        <div style={{
          padding: '14px 20px',
          borderBottom: '1px solid rgba(255, 255, 255, 0.08)',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center'
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <Database size={16} color="#06b6d4" />
            <span style={{ fontSize: '13px', fontWeight: 700, color: '#f8fafc' }}>
              Evidence Record: {evidence.id}
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
        <div style={{ padding: '20px', overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: '12px' }}>
          <div style={{
            display: 'grid',
            gridTemplateColumns: '1fr 1fr',
            gap: '8px',
            background: 'rgba(255, 255, 255, 0.03)',
            padding: '10px',
            borderRadius: '6px',
            fontSize: '11px',
            fontFamily: 'var(--font-mono)',
            color: '#94a3b8'
          }}>
            <div><strong>Source Tool:</strong> {evidence.source_tool}</div>
            <div><strong>Timestamp:</strong> {evidence.timestamp}</div>
            <div><strong>Reference:</strong> {evidence.source_ref}</div>
            <div><strong>Reliability:</strong> {evidence.reliability * 100}%</div>
          </div>

          <div>
            <div style={{ fontSize: '11px', color: '#64748b', textTransform: 'uppercase', marginBottom: '4px' }}>
              Summary
            </div>
            <div style={{ fontSize: '13px', color: '#f8fafc', fontWeight: 500 }}>
              {evidence.summary}
            </div>
          </div>

          <div>
            <div style={{ fontSize: '11px', color: '#64748b', textTransform: 'uppercase', marginBottom: '4px' }}>
              Structured Data Payload
            </div>
            <pre style={{
              background: '#060911',
              border: '1px solid rgba(255, 255, 255, 0.06)',
              borderRadius: '8px',
              padding: '12px',
              fontSize: '11px',
              fontFamily: 'var(--font-mono)',
              color: '#38bdf8',
              overflowX: 'auto',
              maxHeight: '300px'
            }}>
              {JSON.stringify(evidence.data, null, 2)}
            </pre>
          </div>
        </div>
      </div>
    </div>
  );
};
