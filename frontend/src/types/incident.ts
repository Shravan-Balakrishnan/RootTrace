export type InvestigationPhase =
  | "TRIGGERED"
  | "OBSERVING"
  | "COLLECTING_INITIAL_EVIDENCE"
  | "BUILDING_TIMELINE"
  | "HYPOTHESIS_GENERATION"
  | "INVESTIGATING"
  | "CRITIQUE"
  | "VERIFYING"
  | "AWAITING_APPROVAL"
  | "REMEDIATING"
  | "VERIFYING_RECOVERY"
  | "RESOLVED"
  | "ESCALATED"
  | "FAILED"
  | "PAUSED";

export type HypothesisStatus =
  | "PROPOSED"
  | "INVESTIGATING"
  | "SUPPORTED"
  | "WEAKENED"
  | "FALSIFIED"
  | "VERIFIED";

export type VerificationStatus =
  | "UNVERIFIED"
  | "LIKELY_NEEDS_MORE_EVIDENCE"
  | "CONFLICTING_EVIDENCE"
  | "VERIFIED"
  | "REFUTED";

export interface EvidenceRecord {
  id: string;
  source_tool: string;
  timestamp: string;
  source_ref: string;
  summary: string;
  data: Record<string, any>;
  reliability: number;
  relevance_tags: string[];
}

export interface TimelineEvent {
  id: string;
  timestamp: string;
  source: string;
  event_type: string;
  description: string;
  evidence_id?: string;
  is_causal_candidate: boolean;
  is_misleading_red_herring: boolean;
  metadata: Record<string, any>;
}

export interface Hypothesis {
  id: string;
  title: string;
  description: string;
  supporting_evidence_ids: string[];
  contradicting_evidence_ids: string[];
  expected_evidence: string[];
  evidence_still_needed: string[];
  falsification_criteria: string;
  status: HypothesisStatus;
  score: number;
  rejection_explanation?: string;
}

export interface ToolCallRecord {
  id: string;
  tool_name: string;
  arguments: Record<string, any>;
  status: string;
  timestamp: string;
  returned_evidence_ids: string[];
  error_message?: string;
  duration_ms: number;
}

export interface CriticEvaluation {
  hypothesis_id: string;
  temporal_order_valid: boolean;
  contradictions_found: string[];
  missing_evidence_found: string[];
  alternative_explanations: string[];
  critique_summary: string;
  is_valid_candidate: boolean;
}

export interface VerificationResult {
  status: VerificationStatus;
  verified_hypothesis_id?: string;
  evidence_requirements_met: boolean;
  timestamp_order_consistent: boolean;
  competing_hypotheses_evaluated: boolean;
  decisive_contradiction_absent: boolean;
  explanation: string;
}

export interface RemediationProposal {
  id: string;
  action_type: string;
  target_service: string;
  risk: string;
  description: string;
  reversibility: string;
  blast_radius: string;
  parameters: Record<string, any>;
  justification_evidence_ids: string[];
}

export interface PolicyDecision {
  proposal_id: string;
  decision: "AUTO_PERMITTED" | "REQUIRES_HUMAN_APPROVAL" | "BLOCKED";
  reason: string;
  requires_approval: boolean;
  allowed_roles?: string[];
}

export interface ApprovalRecord {
  id: string;
  proposal_id: string;
  approved: boolean;
  approver: string;
  timestamp: string;
  comment?: string;
}

export interface RecoveryCheck {
  check_name: string;
  target: string;
  passed: boolean;
  details: string;
  actual_recovered_count: number;
  expected_recovered_count: number;
}

export interface RecoveryResult {
  all_checks_passed: boolean;
  checks: RecoveryCheck[];
  summary: string;
  timestamp: string;
}

export interface IncidentReport {
  incident_id: string;
  scenario_id: string;
  title: string;
  severity: string;
  started_at: string;
  resolved_at?: string;
  root_cause: string;
  verification_status: VerificationStatus;
  timeline_summary: string[];
  supporting_evidence: string[];
  rejected_hypotheses: Array<{ title: string; rejection: string }>;
  remediation_summary: string;
  recovery_verification: Record<string, any>;
  preventive_recommendations: string[];
}

export interface Incident {
  id: string;
  run_id?: string;
  scenario_id: string;
  title: string;
  severity: string;
  current_phase: InvestigationPhase;
  created_at: string;
  updated_at: string;
  affected_services: string[];
  is_autonomous_paused: boolean;
  evidence_records: Record<string, EvidenceRecord>;
  timeline: TimelineEvent[];
  hypotheses: Hypothesis[];
  tool_calls: ToolCallRecord[];
  verification?: VerificationResult;
  critic_evaluations: CriticEvaluation[];
  remediation_proposal?: RemediationProposal;
  policy_decision?: PolicyDecision;
  approval?: ApprovalRecord;
  execution_status: string;
  recovery_result?: RecoveryResult;
  decision_trace: string[];
  postmortem?: IncidentReport;
}

export interface SystemStatus {
  status: string;
  llm: {
    provider: string;
    model_name: string;
    api_key_configured: boolean;
    mode: string;
  };
  active_scenario: string;
  tool_count: number;
  version: string;
}

export interface ScenarioMeta {
  id: string;
  title: string;
  description: string;
  severity: string;
  affected_services: string[];
}
