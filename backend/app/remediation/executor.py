"""
Remediation Executor for RootTrace.
Executes approved consequential actions in the simulated environment and
performs independent post-remediation verification checks.
"""
from typing import Dict, Any, List
import datetime
from ..models.domain import (
    RemediationProposal,
    ApprovalRecord,
    RecoveryResult,
    RecoveryCheck,
    ExecutionStatus
)
from ..sandbox.engine import SimulatedEnvironment


class RemediationExecutor:
    def __init__(self, sandbox: SimulatedEnvironment):
        self.sandbox = sandbox

    def execute(
        self,
        proposal: RemediationProposal,
        approval: ApprovalRecord
    ) -> Dict[str, Any]:
        """
        Execute an approved remediation proposal.
        Must verify that proposal_id matches approval.proposal_id and approval.approved is True!
        """
        if not approval.approved:
            return {
                "success": False,
                "execution_status": ExecutionStatus.REJECTED,
                "error": "Cannot execute: remediation proposal was rejected by operator."
            }

        if approval.proposal_id != proposal.id:
            return {
                "success": False,
                "execution_status": ExecutionStatus.FAILED,
                "error": f"Approval mismatch: approval is for '{approval.proposal_id}' but proposal is '{proposal.id}'."
            }

        action_type = proposal.action_type
        params = proposal.parameters

        if action_type == "ROLLBACK_AND_REPLAY_CALLBACKS":
            # Step 1: Rollback to target version (v1.2.3)
            target_version = params.get("target_version", "v1.2.3")
            rollback_res = self.sandbox.execute_rollback(proposal.target_service, target_version)

            # Step 2: Replay failed callbacks sequentially under restored mutex lock
            replay_res = self.sandbox.replay_failed_callbacks()

            return {
                "success": True,
                "execution_status": ExecutionStatus.COMPLETED,
                "rollback": rollback_res,
                "replay": replay_res,
                "summary": f"Rolled back {proposal.target_service} to {target_version} and replayed {replay_res.get('replayed_count', 0)} failed callbacks."
            }

        elif action_type == "TERMINATE_ROGUE_QUERY_AND_RESET_POOL":
            db_res = self.sandbox.execute_db_pool_reset()
            return {
                "success": True,
                "execution_status": ExecutionStatus.COMPLETED,
                "details": db_res,
                "summary": db_res.get("message")
            }

        elif action_type == "FAILOVER_TO_BACKUP_GATEWAY":
            pay_res = self.sandbox.execute_payment_failover()
            return {
                "success": True,
                "execution_status": ExecutionStatus.COMPLETED,
                "details": pay_res,
                "summary": pay_res.get("message")
            }

        else:
            return {
                "success": False,
                "execution_status": ExecutionStatus.FAILED,
                "error": f"Unknown remediation action type: {action_type}"
            }

    def verify_recovery(self) -> RecoveryResult:
        """
        Query actual environment state to check if recovery succeeded.
        """
        raw_result = self.sandbox.verify_recovery()
        checks = [
            RecoveryCheck(
                check_name=c["check_name"],
                target=c["target"],
                passed=c["passed"],
                details=c["details"],
                actual_recovered_count=c["actual_recovered_count"],
                expected_recovered_count=c["expected_recovered_count"]
            )
            for c in raw_result["checks"]
        ]

        return RecoveryResult(
            all_checks_passed=raw_result["all_checks_passed"],
            checks=checks,
            summary=raw_result["summary"],
            timestamp=raw_result["timestamp"]
        )
