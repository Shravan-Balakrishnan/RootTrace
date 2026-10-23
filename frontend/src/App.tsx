import React, { useState, useEffect } from 'react';
import { Header } from './components/Header';
import { LifecycleStepper } from './components/LifecycleStepper';
import { EvidenceGraph } from './components/EvidenceGraph';
import { HypothesesPanel } from './components/HypothesesPanel';
import { TimelineView } from './components/TimelineView';
import { ToolActivityFeed } from './components/ToolActivityFeed';
import { DecisionTrace } from './components/DecisionTrace';
import { SafetyApprovalCard } from './components/SafetyApprovalCard';
import { RecoveryVerificationCard } from './components/RecoveryVerificationCard';
import { EvidenceModal } from './components/EvidenceModal';
import { PostmortemModal } from './components/PostmortemModal';
import { Incident, SystemStatus, ScenarioMeta, EvidenceRecord } from './types/incident';
import { AlertCircle, Activity, ShieldCheck, Database, Clock, Layers } from 'lucide-react';

export const App: React.FC = () => {
  const [incident, setIncident] = useState<Incident | null>(null);
  const [systemStatus, setSystemStatus] = useState<SystemStatus | null>(null);
  const [scenarios, setScenarios] = useState<ScenarioMeta[]>([]);
  const [currentScenario, setCurrentScenario] = useState<string>('callback_race');
  const [isStreaming, setIsStreaming] = useState<boolean>(false);
  const [selectedEvidence, setSelectedEvidence] = useState<EvidenceRecord | null>(null);
  const [isPostmortemOpen, setIsPostmortemOpen] = useState<boolean>(false);

  // Load scenarios and system status on mount
  useEffect(() => {
    fetchScenarios();
    fetchSystemStatus();
    fetchIncident();
  }, []);

  const fetchScenarios = async () => {
    try {
      const res = await fetch('/api/scenarios');
      const data = await res.json();
      setScenarios(data);
    } catch (err) {
      console.error('Failed to load scenarios', err);
    }
  };

  const fetchSystemStatus = async () => {
    try {
      const res = await fetch('/api/system/status');
      const data = await res.json();
      setSystemStatus(data);
    } catch (err) {
      console.error('Failed to load system status', err);
    }
  };

  const fetchIncident = async () => {
    try {
      const res = await fetch('/api/incident');
      const data = await res.json();
      setIncident(data);
      if (data.scenario_id) {
        setCurrentScenario(data.scenario_id);
      }
    } catch (err) {
      console.error('Failed to load incident', err);
    }
  };

  const handleSelectScenario = async (id: string) => {
    try {
      const res = await fetch('/api/scenarios/select', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ scenario_id: id })
      });
      const data = await res.json();
      setIncident(data.incident);
      setCurrentScenario(id);
    } catch (err) {
      alert('Error switching scenario: ' + err);
    }
  };

  const handleResetInvestigation = async () => {
    try {
      const res = await fetch('/api/investigate/reset', { method: 'POST' });
      const data = await res.json();
      setIncident(data.incident);
    } catch (err) {
      alert('Reset error: ' + err);
    }
  };

  const handleStepPhase = async () => {
    try {
      const res = await fetch('/api/investigate/step', { method: 'POST' });
      const data = await res.json();
      setIncident(data.incident);
    } catch (err) {
      alert('Step error: ' + err);
    }
  };

  const handleAutoInvestigate = async () => {
    setIsStreaming(true);
    try {
      // Stream Server-Sent Events from backend
      const response = await fetch('/api/investigate/stream');
      const reader = response.body?.getReader();
      const decoder = new TextDecoder();

      if (!reader) {
        throw new Error('Unable to read stream response');
      }

      let buffer = '';
      while (true) {
        const { value, done } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n\n');
        buffer = lines.pop() || '';

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            const jsonStr = line.slice(6);
            try {
              const eventPayload = JSON.parse(jsonStr);
              if (eventPayload.incident) {
                setIncident(eventPayload.incident);
              }
            } catch (e) {
              console.error('SSE JSON parse error', e);
            }
          }
        }
      }
    } catch (err) {
      console.error('Stream investigation error', err);
      // Fallback to standard run endpoint
      const res = await fetch('/api/investigate/run', { method: 'POST' });
      const data = await res.json();
      setIncident(data.incident);
    } finally {
      setIsStreaming(false);
    }
  };

  const handleTogglePause = async () => {
    const isPaused = incident?.is_autonomous_paused;
    const endpoint = isPaused ? '/api/autonomy/resume' : '/api/autonomy/pause';
    const res = await fetch(endpoint, { method: 'POST' });
    const data = await res.json();
    setIncident(data.incident);
  };

  const handleApproveRemediation = async (approver: string, comment: string) => {
    const res = await fetch('/api/remediation/approve', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ approver, comment })
    });
    const data = await res.json();
    setIncident(data.incident);
  };

  const handleRejectRemediation = async () => {
    const res = await fetch('/api/remediation/reject', { method: 'POST' });
    const data = await res.json();
    setIncident(data.incident);
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100vh', overflow: 'hidden' }}>
      <Header
        scenarios={scenarios}
        currentScenario={currentScenario}
        onSelectScenario={handleSelectScenario}
        systemStatus={systemStatus}
        incident={incident}
        isStreaming={isStreaming}
        onAutoInvestigate={handleAutoInvestigate}
        onStepPhase={handleStepPhase}
        onResetInvestigation={handleResetInvestigation}
        onTogglePause={handleTogglePause}
      />

      <LifecycleStepper currentPhase={incident?.current_phase || 'TRIGGERED'} />

      {/* 3-Column Layout */}
      <main style={{
        display: 'grid',
        gridTemplateColumns: '380px 1fr 420px',
        gap: '16px',
        padding: '16px 20px',
        height: 'calc(100vh - 105px)',
        overflow: 'hidden'
      }}>
        {/* Left Column: Overview, Hypotheses & Decision Trace */}
        <section style={{
          background: 'rgba(15, 23, 42, 0.75)',
          backdropFilter: 'blur(16px)',
          border: '1px solid rgba(255, 255, 255, 0.08)',
          borderRadius: '12px',
          display: 'flex',
          flexDirection: 'column',
          overflow: 'hidden'
        }}>
          <div style={{
            padding: '12px 16px',
            borderBottom: '1px solid rgba(255, 255, 255, 0.08)',
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            background: 'rgba(17, 24, 39, 0.5)'
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '12px', fontWeight: 700, color: '#94a3b8' }}>
              <AlertCircle size={14} color="#f43f5e" />
              <span>INCIDENT OVERVIEW</span>
            </div>
            <div style={{ display: 'flex', gap: '6px' }}>
              <span style={{
                fontSize: '10px',
                fontWeight: 700,
                background: 'rgba(239, 68, 68, 0.15)',
                color: '#f87171',
                padding: '2px 6px',
                borderRadius: '4px'
              }}>
                {incident?.severity || 'HIGH'}
              </span>
              <span style={{
                fontSize: '10px',
                fontWeight: 700,
                background: 'rgba(6, 182, 212, 0.15)',
                color: '#38bdf8',
                padding: '2px 6px',
                borderRadius: '4px'
              }}>
                {incident?.current_phase || 'TRIGGERED'}
              </span>
            </div>
          </div>

          <div style={{ padding: '16px', overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: '14px', flex: 1 }}>
            <div>
              <h2 style={{ fontSize: '14px', fontWeight: 700, color: '#fff', marginBottom: '4px' }}>
                {incident?.title || 'Loading incident...'}
              </h2>
              <div style={{ fontSize: '11px', color: '#64748b', display: 'flex', gap: '6px' }}>
                <span>ID: {incident?.id}</span>
                <span>•</span>
                <span>Services: {incident?.affected_services.join(', ')}</span>
              </div>
            </div>

            <div>
              <div style={{ fontSize: '11px', fontWeight: 700, color: '#94a3b8', textTransform: 'uppercase', marginBottom: '8px' }}>
                Competing Hypotheses & Critic Falsifications
              </div>
              <HypothesesPanel
                hypotheses={incident?.hypotheses || []}
                criticEvaluations={incident?.critic_evaluations || []}
              />
            </div>

            <div>
              <div style={{ fontSize: '11px', fontWeight: 700, color: '#94a3b8', textTransform: 'uppercase', marginBottom: '6px' }}>
                Decision Audit Trace
              </div>
              <DecisionTrace traces={incident?.decision_trace || []} />
            </div>
          </div>
        </section>

        {/* Center Column: Evidence Graph & Chronological Timeline */}
        <section style={{
          background: 'rgba(15, 23, 42, 0.75)',
          backdropFilter: 'blur(16px)',
          border: '1px solid rgba(255, 255, 255, 0.08)',
          borderRadius: '12px',
          display: 'flex',
          flexDirection: 'column',
          overflow: 'hidden'
        }}>
          <div style={{
            padding: '12px 16px',
            borderBottom: '1px solid rgba(255, 255, 255, 0.08)',
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            background: 'rgba(17, 24, 39, 0.5)'
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '12px', fontWeight: 700, color: '#94a3b8' }}>
              <Layers size={14} color="#06b6d4" />
              <span>EVIDENCE GRAPH & CAUSAL TOPOLOGY</span>
            </div>
            <span style={{ fontSize: '11px', color: '#64748b' }}>
              {Object.keys(incident?.evidence_records || {}).length} evidence items discovered
            </span>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', height: '100%', overflow: 'hidden' }}>
            <EvidenceGraph
              incident={incident}
              onSelectEvidence={(ev) => setSelectedEvidence(ev)}
            />

            <div style={{
              padding: '10px 16px',
              borderTop: '1px solid rgba(255, 255, 255, 0.08)',
              borderBottom: '1px solid rgba(255, 255, 255, 0.08)',
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              background: 'rgba(17, 24, 39, 0.3)'
            }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '12px', fontWeight: 700, color: '#94a3b8' }}>
                <Clock size={14} color="#38bdf8" />
                <span>CHRONOLOGICAL MULTI-SOURCE TIMELINE</span>
              </div>
              <span style={{ fontSize: '11px', color: '#64748b' }}>
                Merged from logs, git, traces, and metrics
              </span>
            </div>

            <div style={{ padding: '12px 16px', overflowY: 'auto', flex: 1 }}>
              <TimelineView timeline={incident?.timeline || []} />
            </div>
          </div>
        </section>

        {/* Right Column: Safety Policy Approval, Recovery & Real Tool Activity */}
        <section style={{
          background: 'rgba(15, 23, 42, 0.75)',
          backdropFilter: 'blur(16px)',
          border: '1px solid rgba(255, 255, 255, 0.08)',
          borderRadius: '12px',
          display: 'flex',
          flexDirection: 'column',
          overflow: 'hidden'
        }}>
          <div style={{
            padding: '12px 16px',
            borderBottom: '1px solid rgba(255, 255, 255, 0.08)',
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            background: 'rgba(17, 24, 39, 0.5)'
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '12px', fontWeight: 700, color: '#94a3b8' }}>
              <ShieldCheck size={14} color="#10b981" />
              <span>SAFETY, ACTION & RECOVERY</span>
            </div>
            <span style={{ fontSize: '11px', color: '#64748b' }}>
              {incident?.tool_calls.length || 0} tool calls executed
            </span>
          </div>

          <div style={{ padding: '16px', overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: '14px', flex: 1 }}>
            {/* Safety Policy Approval Card */}
            <SafetyApprovalCard
              proposal={incident?.remediation_proposal}
              policyDecision={incident?.policy_decision}
              currentPhase={incident?.current_phase || 'TRIGGERED'}
              executionStatus={incident?.execution_status || 'PENDING'}
              onApprove={handleApproveRemediation}
              onReject={handleRejectRemediation}
            />

            {/* Recovery Verification Card */}
            <RecoveryVerificationCard
              recoveryResult={incident?.recovery_result}
              hasPostmortem={Boolean(incident?.postmortem)}
              onOpenPostmortem={() => setIsPostmortemOpen(true)}
            />

            {/* Real Tool Activity Feed */}
            <div>
              <div style={{ fontSize: '11px', fontWeight: 700, color: '#94a3b8', textTransform: 'uppercase', marginBottom: '8px' }}>
                Real Investigation Tool Invocations
              </div>
              <ToolActivityFeed toolCalls={incident?.tool_calls || []} />
            </div>
          </div>
        </section>
      </main>

      {/* Modals */}
      <EvidenceModal
        evidence={selectedEvidence}
        onClose={() => setSelectedEvidence(null)}
      />

      <PostmortemModal
        postmortem={incident?.postmortem}
        onClose={() => setIsPostmortemOpen(false)}
      />
    </div>
  );
};
