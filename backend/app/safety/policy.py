"""
Deterministic Safety Policy Engine for RootTrace.
Guarantees that the LLM cannot autonomously execute dangerous or unverified actions.
Strict enforcement:
- Read-only queries: AUTO_PERMITTED
- Consequential mutations (Rollback, Replay, Failover): REQUIRES_HUMAN_APPROVAL
- Destructive actions (Drop tables, delete data): BLOCKED
- Unverified root cause: Autonomous execution is BLOCKED
- Paused autonomy: All execution BLOCKED
"""
from typing import Dict, Any, Optional
from ..models.domain import (
    RemediationProposal,
    PolicyDecision,
    PolicyDecisionType,
    ActionRisk,
    VerificationStatus
)


class SafetyPolicyEngine:
    @staticmethod
    def evaluate_proposal(
        proposal: RemediationProposal,
        verification_status: VerificationStatus,
        autonomy_paused: bool = False
    ) -> PolicyDecision:
        # Rule 1: Autonomy Paused
        if autonomy_paused:
            return PolicyDecision(
                proposal_id=proposal.id,
                decision=PolicyDecisionType.BLOCKED,
                reason="Autonomous action execution is currently PAUSED by human operator.",
                requires_approval=True
            )

        # Rule 2: Destructive actions are strictly blocked
        if proposal.risk == ActionRisk.DESTRUCTIVE:
            return PolicyDecision(
                proposal_id=proposal.id,
                decision=PolicyDecisionType.BLOCKED,
                reason="Action is marked DESTRUCTIVE and is blocked by safety policy.",
                requires_approval=False
            )

        # Rule 3: Root cause must be verified before consequential remediation
        if verification_status != VerificationStatus.VERIFIED:
            return PolicyDecision(
                proposal_id=proposal.id,
                decision=PolicyDecisionType.BLOCKED,
                reason=f"Root cause verification status is '{verification_status.value}'. Remediation requires VERIFIED status.",
                requires_approval=True
            )

        # Rule 4: Read-only actions can proceed automatically
        if proposal.risk == ActionRisk.READ_ONLY:
            return PolicyDecision(
                proposal_id=proposal.id,
                decision=PolicyDecisionType.AUTO_PERMITTED,
                reason="Action is read-only and poses zero operational risk.",
                requires_approval=False
            )

        # Rule 5: Consequential actions (e.g. Rollback, Replay) require explicit human approval
        if proposal.risk in (ActionRisk.HIGH_CONSEQUENTIAL, ActionRisk.LOW_REVERSIBLE):
            return PolicyDecision(
                proposal_id=proposal.id,
                decision=PolicyDecisionType.REQUIRES_HUMAN_APPROVAL,
                reason=f"Action '{proposal.action_type}' modifies environment state ({proposal.target_service}). Explicit human approval required before execution.",
                requires_approval=True,
                allowed_roles=["incident_commander", "oncall_sre"]
            )

        return PolicyDecision(
            proposal_id=proposal.id,
            decision=PolicyDecisionType.REQUIRES_HUMAN_APPROVAL,
            reason="Default safety posture: requires human review.",
            requires_approval=True
        )
