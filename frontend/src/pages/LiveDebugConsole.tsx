import React, { useState, useEffect } from 'react';
import {
  LiveSystemStatus,
  TestExecutionResult,
  LiveInvestigationResult,
  PatchApprovalResponse
} from '../types/liveDebug';
import { liveDebugApi } from '../api/liveDebug';
import { LiveAppStatusCard } from '../components/live-debug/LiveAppStatusCard';
import { EvidenceTimeline } from '../components/live-debug/EvidenceTimeline';
import { HypothesisCriticCard } from '../components/live-debug/HypothesisCriticCard';
import { FourAgentTraceCard } from '../components/live-debug/FourAgentTraceCard';
import { PatchReviewModal } from '../components/live-debug/PatchReviewModal';
import { TestResultsPanel } from '../components/live-debug/TestResultsPanel';
import { RecoveryVerification } from '../components/live-debug/RecoveryVerification';
import { Terminal, RefreshCw, AlertCircle } from 'lucide-react';

export const LiveDebugConsole: React.FC = () => {
  const [status, setStatus] = useState<LiveSystemStatus | null>(null);
  const [testResults, setTestResults] = useState<TestExecutionResult | null>(null);
  const [investigation, setInvestigation] = useState<LiveInvestigationResult | null>(null);
  const [approvalOutcome, setApprovalOutcome] = useState<PatchApprovalResponse | null>(null);
  const [logs, setLogs] = useState<string[]>([]);
  const [showLogs, setShowLogs] = useState<boolean>(false);

  const [isTesting, setIsTesting] = useState(false);
  const [isInvestigating, setIsInvestigating] = useState(false);
  const [isApplying, setIsApplying] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const fetchStatus = async () => {
    try {
      const s = await liveDebugApi.getStatus();
      setStatus(s);
    } catch (e: any) {
      console.warn('Failed to fetch live status:', e);
    }
  };

  const fetchLogs = async () => {
    try {
      const l = await liveDebugApi.getLogs(60);
      setLogs(l.logs);
    } catch (e) {
      console.warn('Failed to fetch logs:', e);
    }
  };

  useEffect(() => {
    fetchStatus();
    const interval = setInterval(fetchStatus, 4000);
    return () => clearInterval(interval);
  }, []);

  const handleStart = async () => {
    try {
      await liveDebugApi.startProcess();
      await fetchStatus();
    } catch (e: any) {
      setErrorMsg(e.message);
    }
  };

  const handleStop = async () => {
    try {
      await liveDebugApi.stopProcess();
      await fetchStatus();
    } catch (e: any) {
      setErrorMsg(e.message);
    }
  };

  const handleRestart = async () => {
    try {
      await liveDebugApi.restartProcess();
      await fetchStatus();
    } catch (e: any) {
      setErrorMsg(e.message);
    }
  };

  const handleRunTests = async () => {
    setIsTesting(true);
    setErrorMsg(null);
    try {
      const res = await liveDebugApi.runTests();
      setTestResults(res);
      await fetchStatus();
    } catch (e: any) {
      setErrorMsg(e.message);
    } finally {
      setIsTesting(false);
    }
  };

  const handleInvestigate = async () => {
    setIsInvestigating(true);
    setErrorMsg(null);
    setApprovalOutcome(null);
    try {
      const res = await liveDebugApi.investigate();
      setInvestigation(res);
      await fetchStatus();
    } catch (e: any) {
      setErrorMsg(e.message);
    } finally {
      setIsInvestigating(false);
    }
  };

  const handleApprovePatch = async (token: string) => {
    if (!investigation || !investigation.proposed_patch) return;
    setIsApplying(true);
    setErrorMsg(null);
    try {
      const res = await liveDebugApi.approvePatch({
        run_id: investigation.run_id,
        patch_hash: investigation.proposed_patch.patch_hash,
        auth_token: token,
        comment: "Operator verified and authorized live patch application"
      });
      setApprovalOutcome(res);
      await fetchStatus();
    } catch (e: any) {
      setErrorMsg(e.message);
    } finally {
      setIsApplying(false);
    }
  };

  const handleRejectPatch = async () => {
    if (!investigation) return;
    try {
      await liveDebugApi.rejectPatch(investigation.run_id);
      setInvestigation(null);
    } catch (e: any) {
      setErrorMsg(e.message);
    }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '16px', maxWidth: '1400px', margin: '0 auto', width: '100%' }}>
      {/* Top Banner with Instructions */}
      <div style={{
        background: 'rgba(56, 189, 248, 0.08)',
        border: '1px solid rgba(56, 189, 248, 0.2)',
        borderRadius: '8px',
        padding: '12px 16px',
        fontSize: '12px',
        color: '#bae6fd',
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center'
      }}>
        <div>
          <strong>Live Application Debugging Mode:</strong> Monitor and repair the standalone sample microservice (<code>live-lab/</code>). Edit code manually during demonstrations to trigger real health, request, or test failures.
        </div>
        <button
          onClick={() => {
            fetchStatus();
            if (showLogs) fetchLogs();
          }}
          style={{
            background: 'transparent',
            border: 'none',
            color: '#38bdf8',
            cursor: 'pointer',
            display: 'flex',
            alignItems: 'center',
            gap: '4px',
            fontSize: '11px'
          }}
        >
          <RefreshCw size={12} /> Refresh
        </button>
      </div>

      {errorMsg && (
        <div style={{
          background: 'rgba(239, 68, 68, 0.15)',
          border: '1px solid rgba(239, 68, 68, 0.3)',
          color: '#f87171',
          padding: '10px',
          borderRadius: '6px',
          fontSize: '12px',
          display: 'flex',
          alignItems: 'center',
          gap: '8px'
        }}>
          <AlertCircle size={16} /> {errorMsg}
        </div>
      )}

      {/* Main Process Control and Health Monitor */}
      <LiveAppStatusCard
        status={status}
        onStart={handleStart}
        onStop={handleStop}
        onRestart={handleRestart}
        onRunTests={handleRunTests}
        onInvestigate={handleInvestigate}
        isInvestigating={isInvestigating}
        isTesting={isTesting}
      />

      {/* Test Execution Panel */}
      {testResults && (
        <TestResultsPanel results={testResults} />
      )}

      {/* Active Candidate Patch Proposal Modal */}
      {investigation && investigation.proposed_patch && !approvalOutcome && (
        <PatchReviewModal
          proposal={investigation.proposed_patch}
          onApprove={handleApprovePatch}
          onReject={handleRejectPatch}
          isApplying={isApplying}
        />
      )}

      {/* Recovery Verification Outcome */}
      {approvalOutcome && (
        <RecoveryVerification
          recovery={approvalOutcome.recovery_result}
          modifiedFiles={approvalOutcome.modified_files}
        />
      )}

      {/* Four-Agent Architecture & Log Intelligence Trace */}
      {investigation && (
        <FourAgentTraceCard
          agentTraces={investigation.agent_traces}
          logIntelligence={investigation.log_intelligence}
          historicalCases={investigation.retrieved_historical_cases}
        />
      )}

      {/* Hypotheses & Critic Falsification Card */}
      {investigation && (
        <HypothesisCriticCard
          hypotheses={investigation.hypotheses}
          critic={investigation.critic_evaluation}
          diagnosis={investigation.diagnosis}
          abstained={investigation.abstained}
          abstentionReason={investigation.abstention_reason}
        />
      )}

      {/* Evidence Timeline with Mined Log Templates */}
      {investigation && (
        <EvidenceTimeline
          evidence={investigation.evidence_collected}
          logIntelligence={investigation.log_intelligence}
        />
      )}

      {/* Process Terminal Output Toggle */}
      <div style={{
        background: 'rgba(15, 23, 42, 0.75)',
        border: '1px solid rgba(255, 255, 255, 0.1)',
        borderRadius: '8px',
        padding: '12px 16px'
      }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '13px', fontWeight: 600, color: '#f8fafc' }}>
            <Terminal size={15} color="#38bdf8" />
            <span>Process Logs Console</span>
          </div>
          <button
            onClick={() => {
              if (!showLogs) fetchLogs();
              setShowLogs(!showLogs);
            }}
            style={{
              background: 'rgba(255, 255, 255, 0.08)',
              border: '1px solid rgba(255, 255, 255, 0.15)',
              color: '#cbd5e1',
              borderRadius: '4px',
              padding: '4px 10px',
              fontSize: '11px',
              cursor: 'pointer'
            }}
          >
            {showLogs ? 'Hide Output' : 'View Process Stdout/Stderr'}
          </button>
        </div>

        {showLogs && (
          <div style={{
            marginTop: '10px',
            background: '#090d16',
            borderRadius: '6px',
            border: '1px solid rgba(255, 255, 255, 0.08)',
            padding: '10px',
            fontFamily: 'var(--font-mono)',
            fontSize: '11px',
            color: '#cbd5e1',
            maxHeight: '200px',
            overflowY: 'auto'
          }}>
            {logs.length > 0 ? (
              logs.map((l, i) => (
                <div key={i} style={{ padding: '1px 0' }}>{l}</div>
              ))
            ) : (
              <span style={{ color: '#64748b' }}>No log output buffered yet.</span>
            )}
          </div>
        )}
      </div>
    </div>
  );
};
