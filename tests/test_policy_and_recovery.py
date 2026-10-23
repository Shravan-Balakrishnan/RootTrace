import pytest
from backend.app.orchestrator.engine import Orchestrator
from backend.app.models.domain import (
    InvestigationPhase,
    VerificationStatus,
    PolicyDecisionType,
    ExecutionStatus,
    ActionRisk,
    RemediationProposal,
    ApprovalRecord
)
from backend.app.safety.policy import SafetyPolicyEngine


def test_safety_policy_blocks_unverified_remediation():
    prop = RemediationProposal(
        id="prop_test",
        action_type="ROLLBACK",
        target_service="order-service",
        risk=ActionRisk.HIGH_CONSEQUENTIAL,
        description="Test rollback",
        reversibility="High",
        blast_radius="Single service"
    )
    # When status is UNVERIFIED, policy must block autonomous remediation
    decision = SafetyPolicyEngine.evaluate_proposal(prop, VerificationStatus.UNVERIFIED)
    assert decision.decision == PolicyDecisionType.BLOCKED
    assert "requires VERIFIED" in decision.reason


def test_safety_policy_blocks_when_autonomy_paused():
    prop = RemediationProposal(
        id="prop_test",
        action_type="ROLLBACK",
        target_service="order-service",
        risk=ActionRisk.HIGH_CONSEQUENTIAL,
        description="Test rollback",
        reversibility="High",
        blast_radius="Single service"
    )
    decision = SafetyPolicyEngine.evaluate_proposal(prop, VerificationStatus.VERIFIED, autonomy_paused=True)
    assert decision.decision == PolicyDecisionType.BLOCKED
    assert "PAUSED" in decision.reason


def test_safety_policy_requires_human_approval_for_consequential_actions():
    prop = RemediationProposal(
        id="prop_test",
        action_type="ROLLBACK_AND_REPLAY_CALLBACKS",
        target_service="order-service",
        risk=ActionRisk.HIGH_CONSEQUENTIAL,
        description="Rollback and replay",
        reversibility="High",
        blast_radius="Order service"
    )
    decision = SafetyPolicyEngine.evaluate_proposal(prop, VerificationStatus.VERIFIED, autonomy_paused=False)
    assert decision.decision == PolicyDecisionType.REQUIRES_HUMAN_APPROVAL
    assert decision.requires_approval is True


def test_full_approval_and_recovery_flow():
    orch = Orchestrator("callback_race")
    orch.run_full_investigation_loop()

    assert orch.incident.current_phase == InvestigationPhase.AWAITING_APPROVAL
    assert orch.incident.remediation_proposal is not None

    # Before approval, 17 orders are in FAILED state in the simulator
    pre_orders = orch.sandbox.state["orders"]
    failed_pre = sum(1 for o in pre_orders if o["status"] == "FAILED")
    assert failed_pre == 17

    # Operator approves remediation
    orch.approve_remediation(approver="lead_sre@company.com", comment="Production rollback authorized")

    # Check state transitions and recovery result
    assert orch.incident.current_phase == InvestigationPhase.RESOLVED
    assert orch.incident.recovery_result is not None
    assert orch.incident.recovery_result.all_checks_passed is True

    # Real simulator inspection: 17/17 orders must now be CONFIRMED!
    post_orders = orch.sandbox.state["orders"]
    confirmed_post = sum(1 for o in post_orders if o["status"] == "CONFIRMED")
    failed_post = sum(1 for o in post_orders if o["status"] == "FAILED")
    assert confirmed_post == 17
    assert failed_post == 0

    # Postmortem must be generated and stored
    assert orch.incident.postmortem is not None
    assert len(orch.memory.list_all()) >= 1


def test_remediation_executor_rejects_unauthorized():
    orch = Orchestrator("callback_race")
    orch.run_full_investigation_loop()

    prop = orch.incident.remediation_proposal
    # Provide rejected approval record
    fake_approval = ApprovalRecord(
        id="appr_bad",
        proposal_id=prop.id,
        approved=False,
        approver="operator",
        timestamp="2026-10-23T14:30:00Z"
    )
    res = orch.remediation_executor.execute(prop, fake_approval)
    assert res["success"] is False
    assert res["execution_status"] == ExecutionStatus.REJECTED
