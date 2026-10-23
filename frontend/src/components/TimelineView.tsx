import React from 'react';
import { TimelineEvent } from '../types/incident';
import { AlertTriangle, Flame, Clock } from 'lucide-react';

interface TimelineViewProps {
  timeline: TimelineEvent[];
}

export const TimelineView: React.FC<TimelineViewProps> = ({ timeline }) => {
  if (!timeline || timeline.length === 0) {
    return (
      <div style={{ padding: '16px', color: '#64748b', fontSize: '12px', textAlign: 'center' }}>
        Timeline is empty. Initial telemetry collection will populate chronological events.
      </div>
    );
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', paddingLeft: '8px' }}>
      {timeline.map((event) => {
        const isCausal = event.is_causal_candidate;
        const isHerring = event.is_misleading_red_herring;

        let markerColor = '#38bdf8';
        let cardBg = 'rgba(15, 23, 42, 0.6)';
        let borderColor = 'rgba(255, 255, 255, 0.06)';

        if (isCausal) {
          markerColor = '#f43f5e';
          cardBg = 'rgba(244, 63, 94, 0.08)';
          borderColor = 'rgba(244, 63, 94, 0.3)';
        } else if (isHerring) {
          markerColor = '#f59e0b';
          cardBg = 'rgba(245, 158, 11, 0.08)';
          borderColor = 'rgba(245, 158, 11, 0.3)';
        }

        return (
          <div
            key={event.id}
            style={{
              position: 'relative',
              background: cardBg,
              border: `1px solid ${borderColor}`,
              borderRadius: '8px',
              padding: '10px 12px',
              display: 'flex',
              flexDirection: 'column',
              gap: '4px'
            }}
          >
            {/* Header: timestamp and source */}
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                <span style={{
                  width: '8px',
                  height: '8px',
                  borderRadius: '50%',
                  background: markerColor,
                  display: 'inline-block',
                  boxShadow: `0 0 8px ${markerColor}`
                }} />
                <span style={{
                  fontSize: '11px',
                  fontFamily: 'var(--font-mono)',
                  color: '#94a3b8'
                }}>
                  {event.timestamp.slice(11, 19)} UTC
                </span>
                <span style={{
                  fontSize: '10px',
                  background: 'rgba(255, 255, 255, 0.06)',
                  color: '#cbd5e1',
                  padding: '1px 5px',
                  borderRadius: '4px'
                }}>
                  {event.source}
                </span>
              </div>

              {isCausal && (
                <span style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '4px',
                  fontSize: '10px',
                  fontWeight: 700,
                  color: '#f87171',
                  background: 'rgba(239, 68, 68, 0.15)',
                  padding: '2px 6px',
                  borderRadius: '4px'
                }}>
                  <Flame size={11} />
                  CAUSAL CANDIDATE
                </span>
              )}

              {isHerring && (
                <span style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '4px',
                  fontSize: '10px',
                  fontWeight: 700,
                  color: '#fbbf24',
                  background: 'rgba(245, 158, 11, 0.15)',
                  padding: '2px 6px',
                  borderRadius: '4px'
                }}>
                  <AlertTriangle size={11} />
                  MISLEADING RED HERRING
                </span>
              )}
            </div>

            {/* Description */}
            <div style={{ fontSize: '12px', color: '#f1f5f9', lineHeight: 1.35 }}>
              {event.description}
            </div>
          </div>
        );
      })}
    </div>
  );
};
