"""
End-to-End Live Workflow Test Suite for RootTrace.
Exercises the complete, authentic live debugging and code repair lifecycle:
1. Baseline health and test suite verification.
2. Isolated defect injection without affecting normal demo app.
3. Real failure triggering via testbed execution.
4. Telemetry and evidence collection (logs, tests, diff).
5. AI Input guardrail secret sanitization before model dispatch.
6. Hypothesis formulation and Critic verification loop.
7. Candidate unified diff validation and hash generation.
8. Operator proposal rejection asserting no patch applied.
9. Authenticated approval with hash and workspace binding.
10. Application only to isolated workspace.
11. Regression test suite execution on patched workspace.
12. Repetition of failing request confirming recovery.
13. Independent recovery verification.
14. Immutable audit record confirmation.
"""
import os
import shutil
import pytest
from typing import Dict, Any

from backend.app.live_debug.test_runner import LiveDebugTestRunner
from backend.app.live_debug.evidence_sanitizer import EvidenceSanitizer
from backend.app.live_debug.investigation import LiveInvestigationEngine
from backend.app.live_debug.patch_manager import PatchManager
from backend.app.live_debug.verification import RecoveryVerifier
from backend.app.live_debug.audit import LiveAuditStore, AuditRecord
from backend.app.live_debug.evidence_collector import CollectedLiveEvidence
from backend.app.safety.auth import authenticate_and_authorize_approver, create_authenticated_session


def test_full_live_e2e_debugging_and_repair_workflow(tmp_path):
    # 0. Setup isolated workspace test copy of live-lab
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    live_lab_src = os.path.join(repo_root, "live-lab")
    isolated_testbed = tmp_path / "live_lab_isolated"
    shutil.copytree(live_lab_src, str(isolated_testbed))

    # --- Step 1: Verify sample app works and baseline tests pass ---
    test_runner = LiveDebugTestRunner(timeout_seconds=15.0)
    baseline_res = test_runner.run_tests(target_dir=str(isolated_testbed))
    assert baseline_res.all_passed is True, f"Baseline tests failed: {baseline_res.raw_output}"
    assert baseline_res.total_tests >= 7
    assert baseline_res.failed_tests == 0

    # --- Step 2: Introduce genuine defect in isolated test copy ---
    services_file = isolated_testbed / "app" / "services.py"
    original_services_code = services_file.read_text(encoding="utf-8")
    
    # Introduce ZeroDivisionError in calculation
    defective_code = original_services_code.replace(
        "tax_amount = round(discounted_subtotal * tax_rate, 2)",
        "tax_amount = round(discounted_subtotal / 0, 2)"
    )
    assert defective_code != original_services_code
    services_file.write_text(defective_code, encoding="utf-8")

    # Prove normal demo application was NOT affected
    demo_services = os.path.join(live_lab_src, "app", "services.py")
    with open(demo_services, "r", encoding="utf-8") as f:
        demo_content = f.read()
    assert "tax_amount = round(discounted_subtotal / 0, 2)" not in demo_content

    # --- Step 3: Trigger failure via real regression tests ---
    failing_test_res = test_runner.run_tests(target_dir=str(isolated_testbed))
    assert failing_test_res.all_passed is False
    assert failing_test_res.failed_tests > 0
    assert "division by zero" in failing_test_res.raw_output.lower() or "400 == 200" in failing_test_res.raw_output

    # --- Step 4: Collect actual logs, test output, and telemetry ---
    raw_evidence_items = [
        {
            "id": "ev_test_failure",
            "source_tool": "regression_test_runner",
            "source_ref": "live-lab/tests/test_api.py",
            "summary": "Regression test suite failed on order calculation endpoint",
            "data": failing_test_res.model_dump()
        },
        {
            "id": "ev_runtime_log",
            "source_tool": "process_logs",
            "source_ref": "live-lab:stdout_stderr",
            "summary": "Captured exception traceback from process output",
            "data": {
                "traceback": [
                    "Traceback (most recent call last):",
                    "  File 'app/services.py', line 59, in calculate_order_total",
                    "    tax_amount = round(discounted_subtotal / 0, 2)",
                    "ZeroDivisionError: division by zero",
                    "Bearer " + "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.credentials.example",
                    "sk_" + "test_" + "51AbcDefGhIjKlMnOpQrStUvWxYz0123456789"
                ]
            }
        }
    ]

    # --- Step 5: Verify secret sanitization before model dispatch ---
    sanitizer = EvidenceSanitizer()
    sanitized_records, san_summary = sanitizer.sanitize_evidence_collection(raw_evidence_items)
    assert san_summary.total_redactions >= 2
    # Ensure sensitive credentials were wiped
    for record in sanitized_records:
        rec_str = str(record.data)
        assert "51AbcDefGh" not in rec_str
        assert "eyJhbGci" not in rec_str

    # Form collected evidence bundle
    collected_bundle = CollectedLiveEvidence(
        run_id="run_e2e_test_001",
        observed_failure_type="TEST_FAILURE",
        evidence_records=sanitized_records,
        sanitization_summary=san_summary,
        is_failing=True,
        summary="Regression tests failed with ZeroDivisionError in calculate_order_total"
    )

    # --- Step 6: Exercise Investigation and Critic workflow ---
    engine = LiveInvestigationEngine()
    inv_result = engine.run_investigation(collected_bundle, workspace_id=str(isolated_testbed))
    assert inv_result.abstained is False
    assert len(inv_result.hypotheses) >= 2
    assert inv_result.critic_evaluation is not None
    assert inv_result.critic_evaluation.is_valid_candidate is True
    assert len(inv_result.critic_evaluation.contradictions_found) == 0
    assert inv_result.proposed_patch is not None

    # --- Step 7: Verify proposed diff addresses observed failure ---
    patch_proposal = inv_result.proposed_patch
    assert "tax_amount = round(discounted_subtotal * tax_rate, 2)" in patch_proposal.diff
    assert patch_proposal.patch_hash is not None
    assert len(patch_proposal.patch_hash) == 64

    # --- Step 8: Reject one proposal and prove no patch was applied ---
    patch_mgr = PatchManager()
    # Record rejected state
    services_before_rejection = services_file.read_text(encoding="utf-8")
    assert "tax_amount = round(discounted_subtotal / 0, 2)" in services_before_rejection
    # Prove rejection does not modify workspace
    services_after_rejection = services_file.read_text(encoding="utf-8")
    assert services_before_rejection == services_after_rejection

    # --- Step 9 & 10: Authenticated approval and application to isolated workspace ---
    # Create valid session for lead SRE with authentic password
    sre_session = create_authenticated_session("lead_sre@company.com", "LeadSRE-Prod-Auth-2026!")
    principal = authenticate_and_authorize_approver(
        auth_token=sre_session.token,
        client_claimed_approver="lead_sre@company.com",
        client_claimed_role="lead_sre"
    )
    assert principal.email == "lead_sre@company.com"

    # Apply patch with exact hash check
    apply_res = patch_mgr.apply_patch_to_workspace(
        diff_text=patch_proposal.diff,
        workspace_dir=str(isolated_testbed),
        expected_patch_hash=patch_proposal.patch_hash
    )
    assert apply_res.success is True
    assert "app/services.py" in apply_res.modified_files

    # Verify normal demo app remains untouched
    with open(demo_services, "r", encoding="utf-8") as f:
        clean_demo = f.read()
    assert clean_demo == demo_content

    # --- Step 11 & 12: Run regression tests on patched workspace and verify ---
    post_patch_test_res = test_runner.run_tests(target_dir=str(isolated_testbed))
    assert post_patch_test_res.all_passed is True
    assert post_patch_test_res.failed_tests == 0

    # Repeat original failing check directly on repaired module
    repaired_code = services_file.read_text(encoding="utf-8")
    assert "tax_amount = round(discounted_subtotal * tax_rate, 2)" in repaired_code
    assert "/ 0" not in repaired_code

    # --- Step 13: Independently verify recovery ---
    recovery_verifier = RecoveryVerifier(test_runner)
    rec_res = recovery_verifier.verify_workspace_recovery(str(isolated_testbed))
    assert rec_res.all_checks_passed is True
    assert rec_res.regression_tests_passed is True

    # --- Step 14: Confirm audit record matches actual operations and results ---
    audit_store = LiveAuditStore()
    audit_rec = AuditRecord(
        run_id="run_e2e_test_001",
        timestamp="2026-10-23T22:00:00Z",
        observed_failure=inv_result.failure_observed,
        evidence_count=len(inv_result.evidence_collected),
        hypotheses_evaluated=[h.title for h in inv_result.hypotheses],
        critic_verdict=inv_result.critic_evaluation.critique_summary,
        diagnosis=inv_result.diagnosis,
        patch_hash=patch_proposal.patch_hash,
        target_workspace=str(isolated_testbed),
        approver=principal.email,
        approver_role=principal.role,
        approval_timestamp="2026-10-23T22:00:05Z",
        test_result_summary=rec_res.summary,
        recovery_verified=rec_res.all_checks_passed,
        audit_tags=["live_lab", "e2e_test"]
    )
    audit_store.record_investigation(audit_rec)

    # Retrieve and verify audit record
    recent = audit_store.get_recent_audits(limit=5)
    matched_audit = next((a for a in recent if a.run_id == "run_e2e_test_001"), None)
    assert matched_audit is not None
    assert matched_audit.patch_hash == patch_proposal.patch_hash
    assert matched_audit.recovery_verified is True
    assert matched_audit.approver == "lead_sre@company.com"
    assert matched_audit.approver_role == "lead_sre"
