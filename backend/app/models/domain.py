from __future__ import annotations
from enum import Enum
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field
import datetime
import uuid


class IncidentSeverity(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class InvestigationPhase(str, Enum):
    TRIGGERED = "TRIGGERED"
    OBSERVING = "OBSERVING"
    COLLECTING_INITIAL_EVIDENCE = "COLLECTING_INITIAL_EVIDENCE"
    BUILDING_TIMELINE = "BUILDING_TIMELINE"
    HYPOTHESIS_GENERATION = "HYPOTHESIS_GENERATION"
    INVESTIGATING = "INVESTIGATING"
    CRITIQUE = "CRITIQUE"
    VERIFYING = "VERIFYING"
    AWAITING_APPROVAL = "AWAITING_APPROVAL"
    REMEDIATING = "REMEDIATING"
    VERIFYING_RECOVERY = "VERIFYING_RECOVERY"
    RESOLVED = "RESOLVED"
    ESCALATED = "ESCALATED"
    FAILED = "FAILED"
    PAUSED = "PAUSED"


class VerificationStatus(str, Enum):
    UNVERIFIED = "UNVERIFIED"
    LIKELY_NEEDS_MORE_EVIDENCE = "LIKELY_NEEDS_MORE_EVIDENCE"
    CONFLICTING_EVIDENCE = "CONFLICTING_EVIDENCE"
    VERIFIED = "VERIFIED"
    REFUTED = "REFUTED"


class HypothesisStatus(str, Enum):
    PROPOSED = "PROPOSED"
    INVESTIGATING = "INVESTIGATING"
    SUPPORTED = "SUPPORTED"
    WEAKENED = "WEAKENED"
    FALSIFIED = "FALSIFIED"
    VERIFIED = "VERIFIED"


class ActionRisk(str, Enum):
    READ_ONLY = "READ_ONLY"
    LOW_REVERSIBLE = "LOW_REVERSIBLE"
    HIGH_CONSEQUENTIAL = "HIGH_CONSEQUENTIAL"
    DESTRUCTIVE = "DESTRUCTIVE"


class PolicyDecisionType(str, Enum):
    AUTO_PERMITTED = "AUTO_PERMITTED"
    REQUIRES_HUMAN_APPROVAL = "REQUIRES_HUMAN_APPROVAL"
    BLOCKED = "BLOCKED"


class ExecutionStatus(str, Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    EXECUTING = "EXECUTING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


# --- Core Domain Models ---

class EvidenceRecord(BaseModel):
    id: str
    source_tool: str
    timestamp: str
    source_ref: str
    summary: str
    data: Dict[str, Any]
    reliability: float = Field(default=1.0, ge=0.0, le=1.0)
    relevance_tags: List[str] = Field(default_factory=list)


class TimelineEvent(BaseModel):
    id: str
    timestamp: str
    source: str
    event_type: str
    description: str
    evidence_id: Optional[str] = None
    is_causal_candidate: bool = False
    is_misleading_red_herring: bool = False
    metadata: Dict[str, Any] = Field(default_factory=dict)


class Hypothesis(BaseModel):
    id: str
    title: str
    description: str
    supporting_evidence_ids: List[str] = Field(default_factory=list)
    contradicting_evidence_ids: List[str] = Field(default_factory=list)
    expected_evidence: List[str] = Field(default_factory=list)
    evidence_still_needed: List[str] = Field(default_factory=list)
    falsification_criteria: str
    status: HypothesisStatus = HypothesisStatus.PROPOSED
    score: float = 0.0  # Deterministic score calculated from evidence
    rejection_explanation: Optional[str] = None


class HypothesisAssessment(BaseModel):
    leading_hypothesis_id: Optional[str] = None
    leading_hypothesis_title: Optional[str] = None
    status: VerificationStatus
    rationale: str
    unresolved_questions: List[str] = Field(default_factory=list)


class ToolCallRecord(BaseModel):
    id: str
    tool_name: str
    arguments: Dict[str, Any]
    status: str = "COMPLETED"
    timestamp: str
    returned_evidence_ids: List[str] = Field(default_factory=list)
    error_message: Optional[str] = None
    duration_ms: float = 0.0


class CriticEvaluation(BaseModel):
    hypothesis_id: str
    temporal_order_valid: bool
    contradictions_found: List[str] = Field(default_factory=list)
    missing_evidence_found: List[str] = Field(default_factory=list)
    alternative_explanations: List[str] = Field(default_factory=list)
    critique_summary: str
    is_valid_candidate: bool


class VerificationResult(BaseModel):
    status: VerificationStatus
    verified_hypothesis_id: Optional[str] = None
    evidence_requirements_met: bool
    timestamp_order_consistent: bool
    competing_hypotheses_evaluated: bool
    decisive_contradiction_absent: bool
    explanation: str


class RemediationProposal(BaseModel):
    id: str
    action_type: str  # e.g., "ROLLBACK_DEPLOYMENT_AND_REPLAY_CALLBACKS"
    target_service: str
    risk: ActionRisk
    description: str
    reversibility: str
    blast_radius: str
    parameters: Dict[str, Any] = Field(default_factory=dict)
    justification_evidence_ids: List[str] = Field(default_factory=list)


class PolicyDecision(BaseModel):
    proposal_id: str
    decision: PolicyDecisionType
    reason: str
    requires_approval: bool
    allowed_roles: List[str] = Field(default_factory=lambda: ["incident_commander", "oncall_sre"])


class ApprovalRecord(BaseModel):
    id: str
    proposal_id: str
    approved: bool
    approver: str
    timestamp: str
    comment: Optional[str] = None
    role: Optional[str] = "oncall_sre"
    auth_method: Optional[str] = "role_based_session"


class RecoveryCheck(BaseModel):
    check_name: str
    target: str
    passed: bool
    details: str
    actual_recovered_count: int
    expected_recovered_count: int


class RecoveryResult(BaseModel):
    all_checks_passed: bool
    checks: List[RecoveryCheck]
    summary: str
    timestamp: str


class IncidentReport(BaseModel):
    incident_id: str
    scenario_id: str
    title: str
    severity: IncidentSeverity
    started_at: str
    resolved_at: Optional[str] = None
    root_cause: str
    verification_status: VerificationStatus
    timeline_summary: List[str]
    supporting_evidence: List[str]
    rejected_hypotheses: List[Dict[str, str]]
    remediation_summary: str
    recovery_verification: Dict[str, Any]
    preventive_recommendations: List[str]


class Incident(BaseModel):
    id: str
    run_id: str = Field(default_factory=lambda: f"run_{uuid.uuid4().hex[:8]}")
    scenario_id: str
    title: str
    severity: IncidentSeverity
    current_phase: InvestigationPhase = InvestigationPhase.TRIGGERED
    created_at: str
    updated_at: str
    affected_services: List[str]
    is_autonomous_paused: bool = False
    evidence_records: Dict[str, EvidenceRecord] = Field(default_factory=dict)
    timeline: List[TimelineEvent] = Field(default_factory=list)
    hypotheses: List[Hypothesis] = Field(default_factory=list)
    tool_calls: List[ToolCallRecord] = Field(default_factory=list)
    verification: Optional[VerificationResult] = None
    critic_evaluations: List[CriticEvaluation] = Field(default_factory=list)
    remediation_proposal: Optional[RemediationProposal] = None
    policy_decision: Optional[PolicyDecision] = None
    approval: Optional[ApprovalRecord] = None
    execution_status: ExecutionStatus = ExecutionStatus.PENDING
    recovery_result: Optional[RecoveryResult] = None
    decision_trace: List[str] = Field(default_factory=list)
    postmortem: Optional[IncidentReport] = None
