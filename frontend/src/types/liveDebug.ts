export interface ProcessStatus {
  is_running: boolean;
  pid: number | null;
  host: string;
  port: number;
  uptime_seconds: number;
  last_exit_code: number | null;
  log_lines_buffered: number;
}

export interface HealthStatus {
  is_healthy: boolean;
  status_label: string;
  http_status: number | null;
  latency_ms: number | null;
  data: any;
  error_message?: string | null;
  timestamp: number;
}

export interface LiveSystemStatus {
  process: ProcessStatus;
  health: HealthStatus;
  application: string;
  timestamp: string;
}

export interface TestExecutionResult {
  all_passed: boolean;
  exit_code: number;
  total_tests: number;
  passed_tests: number;
  failed_tests: number;
  error_summary: string[];
  raw_output: string;
  duration_seconds: number;
  timed_out: boolean;
}

export interface SanitizedEvidenceRecord {
  id: string;
  source_tool: string;
  timestamp: string;
  source_ref: string;
  summary: string;
  data: any;
  reliability: number;
  relevance_tags: string[];
  redaction_count: number;
  is_truncated: boolean;
  flagged_for_injection: boolean;
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
  status: string;
  score: number;
}

export interface CriticEvaluation {
  leading_hypothesis_id: string;
  has_falsified_leading_hypothesis: boolean;
  contradictions_found: string[];
  missing_evidence_found: string[];
  critique_summary: string;
}

export interface PatchProposal {
  id: string;
  run_id: string;
  title: string;
  explanation: string;
  diff: string;
  patch_hash: string;
  target_workspace: string;
  target_files: string[];
  is_critic_approved: boolean;
  is_policy_approved: boolean;
  created_at: string;
}

export interface LogTemplateRecord {
  template_id: string;
  template_text: string;
  occurrence_count: number;
  first_seen: string;
  last_seen: string;
  sample_messages: string[];
  source_refs: string[];
  parameters_extracted?: any[];
}

export interface LogIntelligenceReport {
  implementation_used: string;
  templates: LogTemplateRecord[];
  total_messages_processed: number;
  unique_templates_count: number;
  degraded_mode: boolean;
  status_message: string;
  extraction_errors: string[];
}

export interface AgentExecutionRecord {
  agent_id: string;
  role_name: string;
  status: string;
  summary: string;
  tool_calls: string[];
  artifacts_produced: string[];
  execution_time_ms: number;
  timestamp: string;
  details?: Record<string, any>;
}

export interface HistoricalIncidentCase {
  case_id: string;
  signature: string;
  root_cause: string;
  patch_summary: string;
  resolved_at: string;
  verified: boolean;
}

export interface LiveInvestigationResult {
  run_id: string;
  phase: string;
  failure_observed: string;
  evidence_collected: SanitizedEvidenceRecord[];
  hypotheses: Hypothesis[];
  critic_evaluation?: CriticEvaluation | null;
  verification_status: string;
  diagnosis: string;
  proposed_patch?: PatchProposal | null;
  abstained: boolean;
  abstention_reason?: string | null;
  decision_trace: string[];
  agent_traces?: AgentExecutionRecord[];
  log_intelligence?: LogIntelligenceReport | null;
  retrieved_historical_cases?: HistoricalIncidentCase[];
}

export interface LiveRecoveryResult {
  all_checks_passed: boolean;
  summary: string;
  regression_tests_passed: boolean;
  health_check_passed: boolean;
  test_results: any;
  health_results: any;
  verification_timestamp: string;
}

export interface PatchApprovalResponse {
  success: boolean;
  run_id: string;
  applied_patch_hash: string;
  modified_files: string[];
  recovery_result: LiveRecoveryResult;
  approver: {
    email: string;
    role: string;
  };
}
