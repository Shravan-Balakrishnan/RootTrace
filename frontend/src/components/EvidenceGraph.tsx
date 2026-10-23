import React, { useMemo } from 'react';
import {
  ReactFlow,
  Background,
  Controls,
  Node,
  Edge,
  MarkerType
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import { Incident, EvidenceRecord } from '../types/incident';

interface EvidenceGraphProps {
  incident: Incident | null;
  onSelectEvidence: (ev: EvidenceRecord) => void;
}

export const EvidenceGraph: React.FC<EvidenceGraphProps> = ({ incident, onSelectEvidence }) => {
  const { nodes, edges } = useMemo(() => {
    if (!incident) return { nodes: [], edges: [] };

    const generatedNodes: Node[] = [];
    const generatedEdges: Edge[] = [];

    // 1. Root Incident Node
    generatedNodes.push({
      id: 'root_incident',
      position: { x: 40, y: 140 },
      data: {
        label: (
          <div style={{ textAlign: 'left', padding: '4px' }}>
            <div style={{ fontSize: '10px', color: '#06b6d4', fontWeight: 700, textTransform: 'uppercase' }}>
              INCIDENT TRIGGER
            </div>
            <div style={{ fontSize: '11px', fontWeight: 600, color: '#f8fafc', whiteSpace: 'nowrap' }}>
              {incident.id} ({incident.scenario_id})
            </div>
          </div>
        )
      },
      style: {
        background: 'rgba(15, 23, 42, 0.95)',
        border: '1px solid #0284c7',
        borderRadius: '8px',
        color: '#fff',
        width: 170,
        boxShadow: '0 0 12px rgba(2, 132, 199, 0.3)'
      }
    });

    // 2. Evidence Nodes from real tools
    const evidenceList = Object.values(incident.evidence_records || {});
    evidenceList.forEach((ev, idx) => {
      const col = idx % 4;
      const row = Math.floor(idx / 4);
      const x = 270 + col * 180;
      const y = 30 + row * 85;

      let borderColor = '#38bdf8';
      let tagBg = 'rgba(56, 189, 248, 0.15)';
      let tagText = 'OBSERVED';

      const summaryLower = ev.summary.toLowerCase();
      if (summaryLower.includes('conflict') || summaryLower.includes('race') || summaryLower.includes('remove redis lock')) {
        borderColor = '#10b981';
        tagBg = 'rgba(16, 185, 129, 0.2)';
        tagText = 'SUPPORTING';
      } else if (summaryLower.includes('high cpu') || summaryLower.includes('alert')) {
        borderColor = '#f59e0b';
        tagBg = 'rgba(245, 158, 11, 0.2)';
        tagText = 'RED HERRING';
      }

      generatedNodes.push({
        id: ev.id,
        position: { x, y },
        data: {
          label: (
            <div 
              onClick={() => onSelectEvidence(ev)}
              style={{ cursor: 'pointer', textAlign: 'left', padding: '2px' }}
              title="Click to view raw evidence payload"
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '2px' }}>
                <span style={{ fontSize: '9px', fontFamily: 'var(--font-mono)', color: '#94a3b8' }}>
                  {ev.source_tool}
                </span>
                <span style={{ fontSize: '8px', background: tagBg, color: borderColor, padding: '1px 4px', borderRadius: '3px', fontWeight: 700 }}>
                  {tagText}
                </span>
              </div>
              <div style={{ fontSize: '10px', color: '#f1f5f9', fontWeight: 500, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                {ev.summary.slice(0, 32)}...
              </div>
            </div>
          )
        },
        style: {
          background: 'rgba(17, 24, 39, 0.9)',
          border: `1px solid ${borderColor}`,
          borderRadius: '6px',
          width: 160,
          boxShadow: `0 0 8px ${borderColor}22`
        }
      });

      // Connect Root to Initial Evidence
      if (idx < 4) {
        generatedEdges.push({
          id: `e_root_${ev.id}`,
          source: 'root_incident',
          target: ev.id,
          style: { stroke: '#475569', strokeWidth: 1.2 },
          animated: false
        });
      }
    });

    // 3. Hypotheses Nodes on the Right
    const hypotheses = incident.hypotheses || [];
    hypotheses.forEach((h, hIdx) => {
      const y = 50 + hIdx * 95;
      const isVerified = h.status === 'VERIFIED';
      const isFalsified = h.status === 'FALSIFIED';
      const borderColor = isVerified ? '#10b981' : isFalsified ? '#f43f5e' : '#38bdf8';

      generatedNodes.push({
        id: h.id,
        position: { x: 1040, y },
        data: {
          label: (
            <div style={{ textAlign: 'left', padding: '3px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <span style={{ fontSize: '8px', color: borderColor, fontWeight: 700 }}>
                  HYPOTHESIS
                </span>
                <span style={{
                  fontSize: '8px',
                  fontWeight: 700,
                  color: borderColor,
                  background: `${borderColor}22`,
                  padding: '1px 5px',
                  borderRadius: '3px'
                }}>
                  {h.status}
                </span>
              </div>
              <div style={{ fontSize: '10px', fontWeight: 600, color: '#fff', marginTop: '2px', lineHeight: 1.2 }}>
                {h.title.slice(0, 36)}...
              </div>
              <div style={{ fontSize: '9px', fontFamily: 'var(--font-mono)', color: '#94a3b8', marginTop: '3px' }}>
                Score: {h.score > 0 ? `+${h.score}` : h.score} | Supp: {h.supporting_evidence_ids.length}
              </div>
            </div>
          )
        },
        style: {
          background: 'rgba(15, 23, 42, 0.95)',
          border: `1.5px solid ${borderColor}`,
          borderRadius: '8px',
          width: 190,
          boxShadow: isVerified ? '0 0 16px rgba(16, 185, 129, 0.4)' : isFalsified ? '0 0 8px rgba(244, 63, 94, 0.2)' : 'none'
        }
      });

      // Connect Supporting Evidence to Hypothesis
      h.supporting_evidence_ids.forEach((evId) => {
        generatedEdges.push({
          id: `e_supp_${evId}_${h.id}`,
          source: evId,
          target: h.id,
          style: { stroke: '#10b981', strokeWidth: 1.5 },
          animated: isVerified,
          markerEnd: { type: MarkerType.ArrowClosed, color: '#10b981' }
        });
      });

      // Connect Contradicting Evidence to Hypothesis
      h.contradicting_evidence_ids.forEach((evId) => {
        generatedEdges.push({
          id: `e_contra_${evId}_${h.id}`,
          source: evId,
          target: h.id,
          style: { stroke: '#f43f5e', strokeWidth: 1.5, strokeDasharray: '4 4' },
          markerEnd: { type: MarkerType.ArrowClosed, color: '#f43f5e' }
        });
      });
    });

    return { nodes: generatedNodes, edges: generatedEdges };
  }, [incident, onSelectEvidence]);

  return (
    <div style={{ width: '100%', height: '310px', position: 'relative' }}>
      <ReactFlow
        nodes={nodes}
        edges={edges}
        fitView
        minZoom={0.4}
        maxZoom={1.5}
        proOptions={{ hideAttribution: true }}
      >
        <Background color="#1e293b" gap={16} />
        <Controls />
      </ReactFlow>
      <div style={{
        position: 'absolute',
        bottom: 8,
        left: 12,
        background: 'rgba(10, 15, 26, 0.8)',
        padding: '4px 8px',
        borderRadius: '4px',
        border: '1px solid rgba(255, 255, 255, 0.08)',
        fontSize: '10px',
        color: '#94a3b8',
        display: 'flex',
        gap: '12px'
      }}>
        <span><strong style={{ color: '#10b981' }}>━━</strong> Supporting Evidence</span>
        <span><strong style={{ color: '#f43f5e' }}>- -</strong> Contradiction / Falsification</span>
        <span><strong style={{ color: '#06b6d4' }}>●</strong> Click node to inspect</span>
      </div>
    </div>
  );
};
