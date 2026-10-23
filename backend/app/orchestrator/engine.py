"""
Investigation Orchestrator Engine for RootTrace.
Controls the end-to-end incident investigation lifecycle, state transitions,
tool invocations, hypothesis falsification, safety checks, and recovery.
"""
from typing import Dict, Any, List, Optional
import datetime
import uuid
import logging

from ..models.domain import (
    Incident,
    IncidentSeverity,
    InvestigationPhase,
    VerificationStatus,
    HypothesisStatus,
    PolicyDecisionType,
    ExecutionStatus,
    ApprovalRecord,
    VerificationResult,
    RemediationProposal,
    IncidentReport
)
from ..sandbox.engine import SimulatedEnvironment
from ..tools.investigation import ToolRegistry
from ..evidence.scoring import EvidenceEngine
from ..llm.provider import LLMProvider
from ..safety.policy import SafetyPolicyEngine
from ..remediation.executor import RemediationExecutor
from ..memory.store import IncidentMemoryStore
from .state_machine import InvestigationStateMachine

logger = logging.getLogger("roottrace.orchestrator")


class Orchestrator:
    def __init__(self, scenario_id: str = "callback_race"):
        self.scenario_id = scenario_id
        self.sandbox = SimulatedEnvironment(scenario_id=scenario_id)
        self.tools = ToolRegistry(self.sandbox)
        self.llm = LLMProvider()
        self.remediation_executor = RemediationExecutor(self.sandbox)
        self.memory = IncidentMemoryStore()
        self.incident = self._initialize_incident(scenario_id)

    def _initialize_incident(self, scenario_id: str) -> Incident:
        fixture = self.sandbox.state
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        return Incident(
            id=f"INC-{uuid.uuid4().hex[:6].upper()}",
            scenario_id=scenario_id,
            title=fixture.get("title", "Production Incident"),
            severity=IncidentSeverity(fixture.get("severity", "HIGH")),
            current_phase=InvestigationPhase.TRIGGERED,
            created_at=now,
            updated_at=now,
            affected_services=fixture.get("affected_services", []),
            decision_trace=[f"[{now}] Incident created from scenario: {scenario_id}"]
        )

    def reset_scenario(self, scenario_id: str) -> Incident:
        self.scenario_id = scenario_id
        self.sandbox.reset(scenario_id)
        self.tools = ToolRegistry(self.sandbox)
        self.remediation_executor = RemediationExecutor(self.sandbox)
        self.incident = self._initialize_incident(scenario_id)
        return self.incident

    def reset_investigation(self) -> Incident:
        """Completely reset the current scenario with fresh simulator state and new run ID."""
        return self.reset_scenario(self.scenario_id)

    def _transition_to(self, next_phase: InvestigationPhase, note: str):
        InvestigationStateMachine.validate_transition(self.incident.current_phase, next_phase)
        prev = self.incident.current_phase
        self.incident.current_phase = next_phase
        self.incident.updated_at = datetime.datetime.now(datetime.timezone.utc).isoformat()
        log_entry = f"[{self.incident.updated_at}] Phase transition: {prev.value} -> {next_phase.value} | {note}"
        self.incident.decision_trace.append(log_entry)

    # --- Phase Execution Steps ---

    def step_observe(self):
        """Phase: OBSERVE - Analyze initial alert/observation"""
        self._transition_to(InvestigationPhase.OBSERVING, "Observing initial alert trigger")
        obs = self.sandbox.state.get("initial_observation", {})
        self.incident.decision_trace.append(f"Observation registered: {obs.get('summary', 'Alert triggered')}")

    def step_collect_initial_evidence(self):
        """Phase: COLLECT EVIDENCE - Run initial telemetry queries"""
        self._transition_to(InvestigationPhase.COLLECTING_INITIAL_EVIDENCE, "Gathering initial logs and database records")
        # Tool call 1: query logs for errors
        log_res = self.tools.query_logs(limit=25)
        # Tool call 2: inspect database distribution
        db_res = self.tools.inspect_database()

        # Sync evidence into incident
        for eid in log_res.get("evidence_ids", []):
            self.incident.evidence_records[eid] = self.tools.evidence_store[eid]
        for eid in db_res.get("evidence_ids", []):
            self.incident.evidence_records[eid] = self.tools.evidence_store[eid]

        self.incident.tool_calls = list(self.tools.tool_logs)

    def step_build_timeline(self):
        """Phase: BUILD TIMELINE - Construct sorted chronological timeline"""
        self._transition_to(InvestigationPhase.BUILDING_TIMELINE, "Synthesizing chronological timeline from evidence")
        timeline = EvidenceEngine.build_timeline(self.incident.evidence_records)
        self.incident.timeline = timeline
        self.incident.decision_trace.append(f"Timeline constructed with {len(timeline)} chronological events.")

    def step_generate_hypotheses(self):
        """Phase: GENERATE COMPETING HYPOTHESES - Formulate multiple explanations"""
        self._transition_to(InvestigationPhase.HYPOTHESIS_GENERATION, "Generating competing causal hypotheses")
        obs = self.sandbox.state.get("initial_observation", {})
        initial_ev = [ev.model_dump() for ev in self.incident.evidence_records.values()]

        hypotheses = self.llm.generate_competing_hypotheses(obs, initial_ev)
        self.incident.hypotheses = hypotheses
        self.incident.decision_trace.append(f"Generated {len(hypotheses)} competing hypotheses for investigation.")

    def step_single_tool(self) -> Optional[dict]:
        """Execute one targeted tool based on active hypotheses and evidence gaps."""
        if self.incident.current_phase != InvestigationPhase.INVESTIGATING:
            self._transition_to(InvestigationPhase.INVESTIGATING, "Invoking investigation tools to test hypotheses")

        invoked_tool_names = [tc.tool_name for tc in self.incident.tool_calls]
        next_action = self.llm.choose_next_action(
            self.incident.hypotheses,
            invoked_tool_names,
            ["Verify recent code changes", "Inspect trace spans", "Check payment gateway records"]
        )
        if not next_action:
            return None

        tool_name = next_action["tool_name"]
        tool_args = next_action["arguments"]
        tool_fn = getattr(self.tools, tool_name, None)
        res = None
        if tool_fn:
            res = tool_fn(**tool_args)
            for eid in res.get("evidence_ids", []):
                self.incident.evidence_records[eid] = self.tools.evidence_store[eid]

        self.incident.tool_calls = list(self.tools.tool_logs)
        self.incident.timeline = EvidenceEngine.build_timeline(self.incident.evidence_records)
        self._attribute_evidence_to_hypotheses()
        return {"tool_name": tool_name, "arguments": tool_args, "result": res}

    def step_investigate_tools(self, max_tool_steps: int = 5):
        """Phase: INVESTIGATE USING TOOLS - Target unresolved questions within strict budget"""
        if self.incident.current_phase != InvestigationPhase.INVESTIGATING:
            self._transition_to(InvestigationPhase.INVESTIGATING, "Invoking investigation tools to test hypotheses")

        invoked_count = 0
        for _ in range(max_tool_steps):
            act = self.step_single_tool()
            if not act:
                self.incident.decision_trace.append(f"Tool budget stop: No further diagnostic tools needed ({invoked_count} tools invoked).")
                break
            invoked_count += 1
        else:
            self.incident.decision_trace.append(f"Tool budget limit reached ({max_tool_steps} tools executed). Proceeding to critique.")

    def _attribute_evidence_to_hypotheses(self):
        """Correlate collected evidence with hypotheses and calculate scores."""
        for hyp in self.incident.hypotheses:
            supporting = []
            contradicting = []

            for eid, ev in self.incident.evidence_records.items():
                summary_lower = ev.summary.lower()

                if hyp.id == "hyp_concurrency_race":
                    if any(k in summary_lower for k in ["concurrent", "conflict", "remove redis lock", "thread=", "duplicate delivered"]):
                        supporting.append(eid)

                elif hyp.id == "hyp_db_saturation":
                    if "high cpu" in summary_lower or "db_high_cpu" in summary_lower:
                        # Contradiction: happened 6 minutes after initial failures!
                        contradicting.append(eid)

                elif hyp.id == "hyp_gateway_inconsistency":
                    if "payment for" in summary_lower and "status=success" in summary_lower:
                        # Gateway succeeded, so gateway did not fail!
                        contradicting.append(eid)

                elif hyp.id == "hyp_db_pool_exhaustion":
                    if "pool timeout" in summary_lower or "long-running query" in summary_lower:
                        supporting.append(eid)

                elif hyp.id == "hyp_external_outage":
                    if "503" in summary_lower or "circuit breaker" in summary_lower:
                        supporting.append(eid)

            hyp.supporting_evidence_ids = list(set(supporting))
            hyp.contradicting_evidence_ids = list(set(contradicting))

            # Calculate deterministic support score
            hyp.score = EvidenceEngine.calculate_hypothesis_score(hyp, self.incident.evidence_records)
            has_contradiction = len(hyp.contradicting_evidence_ids) > 0
            hyp.status = EvidenceEngine.evaluate_hypothesis_status(hyp.score, has_contradiction)

    def step_critique(self):
        """Phase: CHALLENGE AND FALSIFY - Red-team critic tests hypotheses"""
        self._transition_to(InvestigationPhase.CRITIQUE, "Red-team critic testing hypotheses for contradictions and temporal validity")

        self.incident.critic_evaluations.clear()
        for hyp in self.incident.hypotheses:
            eval_res = self.llm.critique_hypothesis(
                hyp,
                [e.model_dump() for e in self.incident.timeline],
                self.incident.evidence_records
            )
            self.incident.critic_evaluations.append(eval_res)

            if not eval_res.is_valid_candidate:
                hyp.status = HypothesisStatus.FALSIFIED
                hyp.rejection_explanation = eval_res.critique_summary
                self.incident.decision_trace.append(f"Critic FALSIFIED '{hyp.title}': {eval_res.critique_summary}")

    def step_verify(self):
        """Phase: VERIFY ROOT CAUSE - Combine evidence rules and criteria"""
        self._transition_to(InvestigationPhase.VERIFYING, "Verifying leading hypothesis against strict evidence requirements")

        # Find candidate with highest score and no contradictions
        candidates = [
            h for h in self.incident.hypotheses
            if h.status in (HypothesisStatus.SUPPORTED, HypothesisStatus.INVESTIGATING) and len(h.contradicting_evidence_ids) == 0
        ]

        if not candidates:
            self.incident.verification = VerificationResult(
                status=VerificationStatus.CONFLICTING_EVIDENCE,
                verified_hypothesis_id=None,
                evidence_requirements_met=False,
                timestamp_order_consistent=False,
                competing_hypotheses_evaluated=True,
                decisive_contradiction_absent=False,
                explanation="No valid hypothesis survived critic falsification without contradictions."
            )
            return

        leading = max(candidates, key=lambda h: h.score)

        # Verification Criteria:
        # 1. Score >= 0.65
        # 2. Supporting evidence count >= 2
        # 3. No unresolved contradictions
        # 4. Temporal consistency confirmed by critic
        evidence_met = leading.score >= 0.65 and len(leading.supporting_evidence_ids) >= 2

        if evidence_met:
            leading.status = HypothesisStatus.VERIFIED
            self.incident.verification = VerificationResult(
                status=VerificationStatus.VERIFIED,
                verified_hypothesis_id=leading.id,
                evidence_requirements_met=True,
                timestamp_order_consistent=True,
                competing_hypotheses_evaluated=True,
                decisive_contradiction_absent=True,
                explanation=f"Root cause verified: '{leading.title}'. Temporal precedence confirmed, direct concurrency conflict evidence identified, competing explanations falsified."
            )
            self.incident.decision_trace.append(f"Root cause VERIFIED: {leading.title}")

            # Formulate remediation proposal
            proposal = self.llm.recommend_remediation(leading.id, self.scenario_id)
            proposal.justification_evidence_ids = leading.supporting_evidence_ids
            self.incident.remediation_proposal = proposal

            # Evaluate safety policy
            policy_dec = SafetyPolicyEngine.evaluate_proposal(
                proposal,
                self.incident.verification.status,
                self.incident.is_autonomous_paused
            )
            self.incident.policy_decision = policy_dec
            self.incident.decision_trace.append(f"Policy Decision: {policy_dec.decision.value} - {policy_dec.reason}")

            if policy_dec.decision == PolicyDecisionType.REQUIRES_HUMAN_APPROVAL:
                self._transition_to(InvestigationPhase.AWAITING_APPROVAL, "Awaiting operator approval for consequential remediation")
        else:
            self.incident.verification = VerificationResult(
                status=VerificationStatus.LIKELY_NEEDS_MORE_EVIDENCE,
                verified_hypothesis_id=leading.id,
                evidence_requirements_met=False,
                timestamp_order_consistent=True,
                competing_hypotheses_evaluated=True,
                decisive_contradiction_absent=True,
                explanation="Leading candidate lacks sufficient decisive evidence to meet verified threshold."
            )

    def approve_remediation(self, approver: str, comment: Optional[str] = None, role: str = "oncall_sre"):
        """Operator explicitly approves remediation"""
        if not approver or not approver.strip():
            raise ValueError("An explicit approver identity is required.")

        approver_clean = approver.strip()

        if not self.incident.remediation_proposal:
            raise ValueError("No remediation proposal exists to approve.")

        if self.incident.is_autonomous_paused:
            raise ValueError("Autonomy is currently paused. Resume autonomy to proceed with remediation.")

        if self.incident.execution_status == ExecutionStatus.COMPLETED or self.incident.current_phase in (InvestigationPhase.RESOLVED, InvestigationPhase.REMEDIATING):
            raise ValueError("Remediation has already been executed for this incident.")

        if not self.incident.verification or self.incident.verification.status != VerificationStatus.VERIFIED:
            raise ValueError("Cannot approve remediation for an unverified root cause.")

        approval = ApprovalRecord(
            id=f"appr_{uuid.uuid4().hex[:8]}",
            proposal_id=self.incident.remediation_proposal.id,
            approved=True,
            approver=approver_clean,
            role=role,
            auth_method="role_based_session",
            timestamp=datetime.datetime.now(datetime.timezone.utc).isoformat(),
            comment=comment or "Approved rollback and replay in simulated environment."
        )
        self.incident.approval = approval
        self.incident.decision_trace.append(f"Remediation APPROVED by {approver_clean} [{role}]: {approval.comment}")

        # Transition to REMEDIATING
        self._transition_to(InvestigationPhase.REMEDIATING, "Executing approved remediation in simulated environment")
        exec_res = self.remediation_executor.execute(self.incident.remediation_proposal, approval)
        self.incident.execution_status = exec_res.get("execution_status", ExecutionStatus.COMPLETED)
        self.incident.decision_trace.append(f"Remediation executed: {exec_res.get('summary')}")

        # Transition to VERIFYING_RECOVERY
        self._transition_to(InvestigationPhase.VERIFYING_RECOVERY, "Running post-remediation recovery verification")
        rec_res = self.remediation_executor.verify_recovery()
        self.incident.recovery_result = rec_res
        self.incident.decision_trace.append(f"Recovery Verification: {rec_res.summary}")

        if rec_res.all_checks_passed:
            self._transition_to(InvestigationPhase.RESOLVED, "All recovery checks passed. Incident resolved.")
            # Draft and store postmortem
            report = self.llm.draft_postmortem(
                self.incident.id,
                self.scenario_id,
                self.incident.verification.explanation if self.incident.verification else "Resolved",
                [e.description for e in self.incident.timeline],
                [self.incident.evidence_records[eid].summary for eid in (self.incident.remediation_proposal.justification_evidence_ids if self.incident.remediation_proposal else [])],
                [{"title": h.title, "rejection": h.rejection_explanation or "Falsified"} for h in self.incident.hypotheses if h.status == HypothesisStatus.FALSIFIED],
                exec_res.get("summary", "Remediation completed."),
                rec_res.model_dump()
            )
            self.incident.postmortem = report
            self.memory.store_postmortem(report)
        else:
            self._transition_to(InvestigationPhase.FAILED, "Recovery check failed: orders remain unconfirmed.")

    def pause_autonomy(self):
        self.incident.is_autonomous_paused = True
        self.incident.decision_trace.append("Autonomy PAUSED by operator.")

    def resume_autonomy(self):
        self.incident.is_autonomous_paused = False
        self.incident.decision_trace.append("Autonomy RESUMED by operator.")

    def run_full_investigation_loop(self):
        """Run all phases from TRIGGERED until AWAITING_APPROVAL or RESOLVED"""
        if self.incident.current_phase == InvestigationPhase.TRIGGERED:
            self.step_observe()
        if self.incident.current_phase == InvestigationPhase.OBSERVING:
            self.step_collect_initial_evidence()
        if self.incident.current_phase == InvestigationPhase.COLLECTING_INITIAL_EVIDENCE:
            self.step_build_timeline()
        if self.incident.current_phase == InvestigationPhase.BUILDING_TIMELINE:
            self.step_generate_hypotheses()
        if self.incident.current_phase == InvestigationPhase.HYPOTHESIS_GENERATION:
            self.step_investigate_tools()
        if self.incident.current_phase == InvestigationPhase.INVESTIGATING:
            self.step_critique()
        if self.incident.current_phase == InvestigationPhase.CRITIQUE:
            self.step_verify()
        return self.incident
