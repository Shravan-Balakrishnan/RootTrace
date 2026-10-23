"""
Live Debug API Routes for RootTrace.
Exposes endpoints for process lifecycle management, health monitoring,
testbed testing, evidence collection, live investigation, patch approval, and recovery verification.
"""
from fastapi import APIRouter, HTTPException, Header, status
from pydantic import BaseModel, Field
from typing import Dict, Any, List, Optional
import uuid
import datetime
import threading

from ..live_debug import (
    LiveDebugProcessManager,
    HealthMonitor,
    LiveDebugTestRunner,
    LiveEvidenceCollector,
    LiveInvestigationEngine,
    PatchManager,
    WorkspaceManager,
    RecoveryVerifier,
    LiveAuditStore,
    AuditRecord
)
from ..safety.auth import authenticate_and_authorize_approver

router = APIRouter(prefix="/api/live")

# Global singleton services for live debugging
process_mgr = LiveDebugProcessManager()
health_mon = HealthMonitor(host=process_mgr.host, port=process_mgr.port)
test_runner = LiveDebugTestRunner(timeout_seconds=20.0)
evidence_col = LiveEvidenceCollector(process_mgr, health_mon, test_runner)
investigation_engine = LiveInvestigationEngine()
patch_mgr = PatchManager()
workspace_mgr = WorkspaceManager()
verifier = RecoveryVerifier(test_runner)
audit_store = LiveAuditStore()

# Thread-safe approval concurrency lock and active runs registry
_APPROVAL_LOCK = threading.Lock()
_ACTIVE_RUNS: Dict[str, Dict[str, Any]] = {}


class LiveApprovalRequest(BaseModel):
    run_id: str
    patch_hash: str
    auth_token: Optional[str] = None
    approver: Optional[str] = None
    role: Optional[str] = None
    comment: Optional[str] = None


class LiveRejectionRequest(BaseModel):
    run_id: str
    reason: Optional[str] = "Operator rejected candidate repair proposal"


@router.get("/status")
def get_live_status():
    """Returns process, port, and health telemetry of the managed live-lab application."""
    proc = process_mgr.get_status()
    health = health_mon.check_health()
    return {
        "process": proc,
        "health": health.model_dump(),
        "application": "live-lab-checkout",
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat()
    }


@router.post("/process/start")
def start_process():
    """Starts the managed sample application process."""
    res = process_mgr.start()
    return res


@router.post("/process/stop")
def stop_process():
    """Stops the managed sample application process cleanly."""
    res = process_mgr.stop()
    return res


@router.post("/process/restart")
def restart_process():
    """Restarts the managed sample application process."""
    res = process_mgr.restart()
    return res


@router.get("/logs")
def get_recent_logs(limit: int = 100):
    """Returns the most recent process log lines."""
    return {"logs": process_mgr.get_logs(limit=limit)}


@router.post("/tests/run")
def execute_tests():
    """Runs allowlisted test suite against live-lab."""
    res = test_runner.run_tests()
    return res.model_dump()


@router.post("/investigate")
def run_live_investigation():
    """
    Collects real evidence (logs, tracebacks, test errors, git diffs),
    applies input guardrails and secret sanitization,
    evaluates competing hypotheses and Critic checks,
    creates an isolated workspace, and synthesizes a candidate patch proposal.
    """
    run_id = f"RUN-{uuid.uuid4().hex[:8].upper()}"

    # 1. Collect real telemetry and failure evidence
    collected = evidence_col.collect_all_evidence(run_id)

    # 2. Create isolated workspace
    workspace_dir = workspace_mgr.create_isolated_workspace(run_id=run_id)
    # Save clean pre-patch snapshot
    workspace_mgr.create_snapshot(workspace_dir, "pre_patch")

    # 3. Run investigation loop
    inv_res = investigation_engine.run_investigation(collected, workspace_id=workspace_dir)

    _ACTIVE_RUNS[run_id] = {
        "run_id": run_id,
        "investigation": inv_res,
        "workspace_dir": workspace_dir,
        "status": "PENDING",
        "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat()
    }

    return inv_res.model_dump()


@router.post("/patch/approve")
def approve_candidate_patch(req: LiveApprovalRequest):
    """
    Applies an approved patch inside the isolated workspace:
    - Strictly verifies caller's authenticated session and authorized role
    - Rejects concurrent, duplicate, or replayed approvals with HTTP 409 Conflict
    - Verifies expected patch hash to prevent tampering or replay
    - Applies patch to isolated workspace only
    - Runs regression tests
    - Independently verifies recovery
    - Records immutable audit record
    """
    # 1. Server-verified identity check
    principal = authenticate_and_authorize_approver(
        auth_token=req.auth_token,
        client_claimed_approver=req.approver,
        client_claimed_role=req.role
    )

    with _APPROVAL_LOCK:
        run_state = _ACTIVE_RUNS.get(req.run_id)
        if not run_state:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Investigation run '{req.run_id}' not found or expired."
            )

        current_status = run_state.get("status", "PENDING")
        if current_status in ("APPLYING", "APPLIED", "VALIDATING", "VERIFIED"):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Conflict: Approval already in progress or completed for run '{req.run_id}' (status: {current_status})."
            )
        if current_status == "REJECTED":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Conflict: Patch proposal for run '{req.run_id}' was already rejected."
            )

        inv: Any = run_state["investigation"]
        workspace_dir = run_state["workspace_dir"]

        if not inv.proposed_patch:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No candidate patch available to approve."
            )

        # 2. Patch hash and workspace binding verification
        if inv.proposed_patch.patch_hash != req.patch_hash:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Stale or tampered patch: hash {req.patch_hash} does not match active proposal {inv.proposed_patch.patch_hash}."
            )

        # Transition state to APPLYING
        run_state["status"] = "APPLYING"

    # 3. Apply patch inside the isolated workspace
    try:
        apply_res = patch_mgr.apply_patch_to_workspace(
            diff_text=inv.proposed_patch.diff,
            workspace_dir=workspace_dir,
            expected_patch_hash=req.patch_hash
        )

        if not apply_res.success:
            with _APPROVAL_LOCK:
                run_state["status"] = "FAILED"
            # Rollback on application failure
            workspace_mgr.rollback(workspace_dir, "pre_patch")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Patch application failed in workspace: {apply_res.error_message}"
            )

        with _APPROVAL_LOCK:
            run_state["status"] = "APPLIED"

        # 4. Independent Recovery Verification
        with _APPROVAL_LOCK:
            run_state["status"] = "VALIDATING"

        recovery_res = verifier.verify_workspace_recovery(workspace_dir)

        with _APPROVAL_LOCK:
            run_state["status"] = "VERIFIED" if recovery_res.all_checks_passed else "FAILED"

        # 5. Persist Immutable Audit Record
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        audit_rec = AuditRecord(
            run_id=req.run_id,
            timestamp=now,
            observed_failure=inv.failure_observed,
            evidence_count=len(inv.evidence_collected),
            hypotheses_evaluated=[h.title for h in inv.hypotheses],
            critic_verdict=inv.critic_evaluation.critique_summary if inv.critic_evaluation else "N/A",
            diagnosis=inv.diagnosis,
            patch_hash=req.patch_hash,
            target_workspace=workspace_dir,
            approver=principal.email,
            approver_role=principal.role,
            approval_timestamp=now,
            test_result_summary=recovery_res.summary,
            recovery_verified=recovery_res.all_checks_passed,
            audit_tags=["live_lab", inv.failure_observed]
        )
        audit_store.record_investigation(audit_rec)

        return {
            "success": recovery_res.all_checks_passed,
            "run_id": req.run_id,
            "status": run_state["status"],
            "applied_patch_hash": req.patch_hash,
            "modified_files": apply_res.modified_files,
            "recovery_result": recovery_res.model_dump(),
            "approver": {
                "email": principal.email,
                "role": principal.role
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        with _APPROVAL_LOCK:
            run_state["status"] = "FAILED"
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Unexpected error during patch application: {str(e)}"
        )


@router.post("/patch/reject")
def reject_candidate_patch(req: LiveRejectionRequest):
    """Records operator rejection of a candidate repair proposal."""
    with _APPROVAL_LOCK:
        run_state = _ACTIVE_RUNS.get(req.run_id)
        if not run_state:
            raise HTTPException(status_code=404, detail="Run not found.")

        current_status = run_state.get("status", "PENDING")
        if current_status in ("APPLYING", "APPLIED", "VALIDATING", "VERIFIED"):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Cannot reject patch; approval or application is already in progress or completed (status: {current_status})."
            )

        run_state["status"] = "REJECTED"
        workspace_dir = run_state["workspace_dir"]
        workspace_mgr.cleanup(workspace_dir)

    return {
        "success": True,
        "run_id": req.run_id,
        "status": "REJECTED",
        "message": f"Patch proposal rejected for run {req.run_id}: {req.reason}"
    }


@router.get("/audit")
def get_audit_records():
    """Returns recent audit records and historical continual learning cases."""
    return {
        "recent_audits": [a.model_dump() for a in audit_store.get_recent_audits()],
        "historical_corpus": [c.model_dump() for c in audit_store._historical_corpus]
    }
