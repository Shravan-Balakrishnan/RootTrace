import React, { useRef, useEffect } from 'react';

interface DecisionTraceProps {
  traces: string[];
}

export const DecisionTrace: React.FC<DecisionTraceProps> = ({ traces }) => {
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (containerRef.current) {
      containerRef.current.scrollTop = containerRef.current.scrollHeight;
    }
  }, [traces]);

  if (!traces || traces.length === 0) {
    return (
      <div style={{ padding: '12px', color: '#64748b', fontSize: '11px', textAlign: 'center' }}>
        No decision traces logged yet.
      </div>
    );
  }

  return (
    <div
      ref={containerRef}
      style={{
        display: 'flex',
        flexDirection: 'column',
        gap: '4px',
        maxHeight: '140px',
        overflowY: 'auto',
        fontFamily: 'var(--font-mono)',
        fontSize: '11px',
        background: '#090d16',
        padding: '8px 12px',
        borderRadius: '6px',
        border: '1px solid rgba(255, 255, 255, 0.05)'
      }}
    >
      {traces.map((trace, idx) => (
        <div key={idx} style={{ color: '#94a3b8', lineHeight: 1.4, borderBottom: '1px solid rgba(255, 255, 255, 0.03)', paddingBottom: '2px' }}>
          {trace}
        </div>
      ))}
    </div>
  );
};
