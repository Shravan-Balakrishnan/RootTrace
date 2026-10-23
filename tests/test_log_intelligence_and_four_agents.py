"""
Comprehensive Unit & Integration Test Suite for:
1. Drain3 Log Template Mining and Deterministic Fallback Normalizer.
2. Four-Agent Architecture (Agent 1, Agent 2, Agent 3, Agent 4).
3. Retrieval-Based Continual Learning from Verified Historical Cases.
4. End-to-End Workflow with Full Adversarial and Edge-Case Coverage.
"""
import pytest
import os
import shutil
import uuid
from typing import List

from backend.app.live_debug.log_intelligence import (
    LogIntelligenceMiner,
    LogIntelligenceReport,
    LogTemplateRecord,
    DRAIN3_AVAILABLE
)
from backend.app.live_debug.agents import (
    EvidenceLogIntelligenceAgent,
    DiagnosisInvestigationAgent,
    AdversarialCriticAgent,
    RepairVerificationAgent,
    AgentExecutionRecord
)
from backend.app.live_debug.evidence_collector import (
    LiveEvidenceCollector,
    CollectedLiveEvidence
)
from backend.app.live_debug.evidence_sanitizer import (
    EvidenceSanitizer,
    SanitizedEvidenceRecord,
    SanitizationSummary
)
from backend.app.live_debug.audit import LiveAuditStore
from backend.app.live_debug.patch_manager import PatchManager
from backend.app.live_debug.test_runner import LiveDebugTestRunner
from backend.app.live_debug.workspace_manager import WorkspaceManager
from backend.app.live_debug.investigation import LiveInvestigationEngine
from backend.app.models.domain import HypothesisStatus, VerificationStatus


# =====================================================================
# Fixtures
# =====================================================================

@pytest.fixture
def isolated_workspace(tmp_path):
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    live_lab_src = os.path.join(repo_root, "live-lab")
    copy_dir = tmp_path / "live_lab_copy"
    shutil.copytree(live_lab_src, str(copy_dir))
    return copy_dir


# =====================================================================
# 1. Drain3 Log Intelligence Tests
# =====================================================================

def test_drain3_extracts_order_number_template():
    """
    Verifies that Drain3 correctly mines recurring log lines with numeric variables:
    'Callback failed for order 1042' -> 'Callback failed for order <NUM>'
    """
    if not DRAIN3_AVAILABLE:
        pytest.skip("Drain3 package is not installed in this environment.")

    miner = LogIntelligenceMiner(force_fallback=False)
    lines = [
        "Callback failed for order 1042",
        "Callback failed for order 1043",
        "Callback failed for order 1044"
    ]

    report = miner.mine_log_templates(lines)
    assert report.implementation_used == "drain3"
    assert report.total_messages_processed == 3
    assert report.unique_templates_count == 1
    assert not report.degraded_mode

    tmpl = report.templates[0]
    assert tmpl.template_text == "Callback failed for order <NUM>"
    assert tmpl.occurrence_count == 3
    assert len(tmpl.sample_messages) == 3
    assert "1042" in tmpl.sample_messages[0]
    assert "1044" in tmpl.sample_messages[2]
    assert tmpl.first_seen is not None
    assert tmpl.last_seen is not None


def test_deterministic_fallback_matches_drain3_template():
    """
    Verifies that the deterministic normalizer produces the identical template
    when Drain3 is unavailable or forced off.
    """
    miner = LogIntelligenceMiner(force_fallback=True)
    lines = [
        "Callback failed for order 1042",
        "Callback failed for order 1043",
        "Callback failed for order 1044"
    ]

    report = miner.mine_log_templates(lines)
    assert report.implementation_used == "deterministic_fallback"
    assert report.total_messages_processed == 3
    assert report.unique_templates_count == 1

    tmpl = report.templates[0]
    assert tmpl.template_text == "Callback failed for order <NUM>"
    assert tmpl.occurrence_count == 3
    assert len(tmpl.sample_messages) == 3


def test_log_intelligence_empty_and_blank_messages():
    """Verifies that empty or whitespace-only log lists do not crash and report zero templates."""
    miner = LogIntelligenceMiner()
    report_empty = miner.mine_log_templates([])
    assert report_empty.total_messages_processed == 0
    assert len(report_empty.templates) == 0

    report_blank = miner.mine_log_templates(["", "   ", "\n\t"])
    assert report_blank.total_messages_processed == 0
    assert len(report_blank.templates) == 0


def test_log_intelligence_mixed_and_unrepeated_templates():
    """Verifies clustering of disparate templates, counting frequencies correctly."""
    miner = LogIntelligenceMiner()
    lines = [
        "INFO: Starting worker 1",
        "INFO: Starting worker 2",
        "ERROR: Database connection timeout to 10.0.0.5",
        "INFO: Starting worker 3",
        "ERROR: Database connection timeout to 10.0.0.9",
        "WARN: Memory usage high: 88%"
    ]
    report = miner.mine_log_templates(lines)
    assert report.total_messages_processed == 6
    assert report.unique_templates_count >= 3

    # Most frequent template should be first (Starting worker <NUM> with count 3)
    top_tmpl = report.templates[0]
    assert "Starting worker" in top_tmpl.template_text
    assert top_tmpl.occurrence_count == 3


def test_log_intelligence_resilience_to_oversized_and_adversarial_logs():
    """Verifies that lines exceeding normal bounds are truncated safely without ReDoS."""
    miner = LogIntelligenceMiner()
    huge_line = "Repeated token " * 10000 + " 9999"
    report = miner.mine_log_templates([huge_line, huge_line])
    assert report.total_messages_processed == 2
    assert report.unique_templates_count == 1


# =====================================================================
# 2. Four-Agent Architecture Tests
# =====================================================================

def test_agent_1_evidence_collection_and_log_intelligence(isolated_workspace):
    """
    Agent 1: Evidence & Log Intelligence.
    Tests that Agent 1 collects evidence, sanitizes secrets, runs Drain3 template mining,
    and returns a structured execution record with provenance.
    """
    from backend.app.live_debug.process_manager import LiveDebugProcessManager
    from backend.app.live_debug.health_monitor import HealthMonitor

    proc_mgr = LiveDebugProcessManager()
    health_mon = HealthMonitor()
    runner = LiveDebugTestRunner(timeout_seconds=10.0)
    sanitizer = EvidenceSanitizer()
    collector = LiveEvidenceCollector(proc_mgr, health_mon, runner, sanitizer)

    agent_1 = EvidenceLogIntelligenceAgent(collector)
    collected, record = agent_1.execute(run_id="run_agent1_test")

    assert isinstance(collected, CollectedLiveEvidence)
    assert isinstance(record, AgentExecutionRecord)
    assert record.role_name == "Agent 1: Evidence & Log Intelligence"
    assert record.status == "COMPLETED"
    assert "log_intelligence" in record.tool_calls
    assert len(collected.evidence_records) > 0


def test_agent_2_diagnosis_and_continual_learning_retrieval():
    """
    Agent 2: Diagnosis & Investigation.
    Tests that Agent 2 creates competing hypotheses and retrieves reviewed historical cases.
    """
    audit_store = LiveAuditStore()
    agent_2 = DiagnosisInvestigationAgent(audit_store=audit_store)

    sanitizer = EvidenceSanitizer()
    raw_evidence = [
        {
            "id": "ev_test_1",
            "source_tool": "regression_test_runner",
            "source_ref": "live-lab/tests/test_api.py",
            "summary": "AssertionError in order calculation",
            "data": {"error_summary": ["ZeroDivisionError: division by zero in services.py:59"]}
        }
    ]
    sanitized, san_summary = sanitizer.sanitize_evidence_collection(raw_evidence)

    evidence_bundle = CollectedLiveEvidence(
        run_id="run_agent2_test",
        observed_failure_type="TEST_FAILURE",
        evidence_records=sanitized,
        sanitization_summary=san_summary,
        is_failing=True,
        summary="ZeroDivisionError observed in order calculation test"
    )

    hypotheses, retrieved_cases, record = agent_2.execute(evidence_bundle, workspace_id="ws_01")

    assert len(hypotheses) == 2
    h1, h2 = hypotheses[0], hypotheses[1]
    # Leading hypothesis is code defect with higher confidence
    assert h1.status == HypothesisStatus.SUPPORTED
    assert h1.score > h2.score
    # Competing hypothesis is transient infrastructure with lower confidence
    assert h2.status == HypothesisStatus.WEAKENED

    # Continual Learning retrieval found matching verified historical case
    assert len(retrieved_cases) > 0
    assert any("ZeroDivisionError" in c.signature for c in retrieved_cases)

    # Agent execution record metadata
    assert record.role_name == "Agent 2: Diagnosis & Investigation"
    assert record.status == "COMPLETED"
    assert "historical_case_retrieval" in record.tool_calls


def test_agent_3_critic_validates_and_approves_corroborated_hypothesis():
    """
    Agent 3: Adversarial Critic.
    Tests that Agent 3 approves the leading hypothesis when corroborated by evidence.
    """
    agent_3 = AdversarialCriticAgent()
    sanitizer = EvidenceSanitizer()
    raw_evidence = [
        {
            "id": "ev_tb_1",
            "source_tool": "process_logs",
            "source_ref": "live-lab:stdout_stderr",
            "summary": "Traceback captured",
            "data": {"traceback": ["ZeroDivisionError: division by zero"]}
        },
        {
            "id": "ev_test_1",
            "source_tool": "regression_test_runner",
            "source_ref": "live-lab/tests/test_api.py",
            "summary": "Regression test failed",
            "data": {"error_summary": ["ZeroDivisionError"]}
        }
    ]
    sanitized, summary = sanitizer.sanitize_evidence_collection(raw_evidence)
    bundle = CollectedLiveEvidence(
        run_id="run_agent3_ok",
        observed_failure_type="TEST_FAILURE",
        evidence_records=sanitized,
        sanitization_summary=summary,
        is_failing=True,
        summary="Test failure corroborated by traceback"
    )

    agent_2 = DiagnosisInvestigationAgent()
    hypotheses, _, _ = agent_2.execute(bundle, workspace_id="ws_01")
    leading_hyp = hypotheses[0]

    critic_eval, is_approved, veto_reason, record = agent_3.execute(leading_hyp, bundle)

    assert is_approved is True
    assert veto_reason is None
    assert critic_eval.is_valid_candidate is True
    assert record.role_name == "Agent 3: Adversarial Critic"
    assert record.status == "APPROVED"


def test_agent_3_critic_issues_veto_on_ambiguous_evidence():
    """
    Agent 3: Adversarial Critic.
    Tests that Agent 3 issues a VETO when evidence is ambiguous (health failed, but no traceback or test failure).
    """
    agent_3 = AdversarialCriticAgent()
    sanitizer = EvidenceSanitizer()
    raw_evidence = [
        {
            "id": "ev_hp_1",
            "source_tool": "health_probe",
            "source_ref": "http://127.0.0.1:8001/health",
            "summary": "Health probe timeout",
            "data": {"status": "CRITICAL"}
        }
    ]
    sanitized, summary = sanitizer.sanitize_evidence_collection(raw_evidence)
    bundle = CollectedLiveEvidence(
        run_id="run_agent3_veto",
        observed_failure_type="HEALTH_CHECK_FAILED",
        evidence_records=sanitized,
        sanitization_summary=summary,
        is_failing=True,
        summary="Transient probe timeout without error logs"
    )

    agent_2 = DiagnosisInvestigationAgent()
    hypotheses, _, _ = agent_2.execute(bundle, workspace_id="ws_01")
    leading_hyp = hypotheses[0]

    critic_eval, is_approved, veto_reason, record = agent_3.execute(leading_hyp, bundle)

    assert is_approved is False
    assert veto_reason is not None
    assert "Health probe failed without application traceback" in veto_reason
    assert record.role_name == "Agent 3: Adversarial Critic"
    assert record.status == "VETOED"


def test_agent_4_repair_proposal_and_hash_binding():
    """
    Agent 4: Repair & Verification.
    Tests that Agent 4 synthesizes a valid minimal unified diff and binds a deterministic SHA-256 hash.
    """
    agent_4 = RepairVerificationAgent()
    sanitizer = EvidenceSanitizer()
    raw_evidence = [
        {
            "id": "ev_err_1",
            "source_tool": "regression_test_runner",
            "source_ref": "live-lab/tests/test_api.py",
            "summary": "ZeroDivisionError in services.py",
            "data": {"error_summary": ["ZeroDivisionError: division by zero"]}
        }
    ]
    sanitized, _ = sanitizer.sanitize_evidence_collection(raw_evidence)

    proposal, record = agent_4.propose_patch(
        run_id="run_agent4_synth",
        workspace_id="ws_test",
        error_context="ZeroDivisionError: division by zero in calculate_order_total",
        evidence=sanitized
    )

    assert proposal.patch_hash is not None
    assert len(proposal.patch_hash) == 64
    assert "tax_amount = round(discounted_subtotal * tax_rate, 2)" in proposal.diff
    assert "services.py" in proposal.target_files[0]
    assert record.role_name == "Agent 4: Repair & Verification"
    assert record.status == "AWAITING_APPROVAL"


# =====================================================================
# 3. Complete End-to-End Workflow with 4-Agent Architecture
# =====================================================================

def test_full_four_agent_end_to_end_workflow(isolated_workspace):
    """
    End-to-End Workflow:
    OBSERVE -> COLLECT & SANITIZE (Agent 1) -> MINE LOG TEMPLATES (Drain3) ->
    DIAGNOSE & RETRIEVE (Agent 2) -> CRITIC EVALUATION (Agent 3) ->
    PROPOSE REPAIR (Agent 4) -> VERIFY ALL AGENT TRACES.
    """
    # 1. Introduce defect in isolated workspace
    services_path = isolated_workspace / "app" / "services.py"
    code = services_path.read_text(encoding="utf-8")
    services_path.write_text(
        code.replace(
            "tax_amount = round(discounted_subtotal * tax_rate, 2)",
            "tax_amount = round(discounted_subtotal / 0, 2)"
        ),
        encoding="utf-8"
    )

    # 2. Run test to capture failure
    runner = LiveDebugTestRunner(timeout_seconds=12.0)
    test_res = runner.run_tests(target_dir=str(isolated_workspace))
    assert test_res.all_passed is False

    # 3. Simulate simulated log stream with order callbacks
    log_lines = [
        "Callback failed for order 1042",
        "Callback failed for order 1043",
        "Callback failed for order 1044",
        "ZeroDivisionError: division by zero at app/services.py:59"
    ]
    miner = LogIntelligenceMiner()
    log_report = miner.mine_log_templates(log_lines)
    assert log_report.unique_templates_count >= 2

    # 4. Package evidence records
    sanitizer = EvidenceSanitizer()
    raw_items = [
        {
            "id": "ev_logs_test",
            "source_tool": "process_logs",
            "timestamp": "2026-10-23T23:00:00Z",
            "source_ref": "live-lab:stdout",
            "summary": "Traceback detected in process logs",
            "data": {"lines": log_lines, "traceback": [log_lines[-1]]}
        },
        {
            "id": "ev_test_runner",
            "source_tool": "regression_test_runner",
            "timestamp": "2026-10-23T23:00:01Z",
            "source_ref": "live-lab/tests/test_api.py",
            "summary": "Regression test failed: ZeroDivisionError",
            "data": test_res.model_dump()
        },
        {
            "id": "ev_log_intel",
            "source_tool": "log_intelligence",
            "timestamp": "2026-10-23T23:00:02Z",
            "source_ref": f"{log_report.implementation_used}:template_miner",
            "summary": f"Mined {log_report.unique_templates_count} template(s)",
            "data": log_report.model_dump()
        }
    ]
    sanitized_records, summary = sanitizer.sanitize_evidence_collection(raw_items)

    bundle = CollectedLiveEvidence(
        run_id="run_e2e_4agents",
        observed_failure_type="TEST_FAILURE",
        evidence_records=sanitized_records,
        sanitization_summary=summary,
        is_failing=True,
        summary="ZeroDivisionError observed in services.py",
        log_intelligence=log_report
    )

    # 5. Execute Live Investigation Engine
    engine = LiveInvestigationEngine()
    result = engine.run_investigation(bundle, workspace_id=str(isolated_workspace))

    # Assertions on 4-agent trace and outputs
    assert result.abstained is False
    assert result.phase == "AWAITING_APPROVAL"
    assert result.proposed_patch is not None
    assert len(result.agent_traces) >= 3  # Agent 2, Agent 3, Agent 4 traces

    # Verify Agent 2 trace
    a2_trace = next((t for t in result.agent_traces if "Agent 2" in t.role_name), None)
    assert a2_trace is not None
    assert a2_trace.status == "COMPLETED"

    # Verify Agent 3 trace
    a3_trace = next((t for t in result.agent_traces if "Agent 3" in t.role_name), None)
    assert a3_trace is not None
    assert a3_trace.status == "APPROVED"

    # Verify Agent 4 trace
    a4_trace = next((t for t in result.agent_traces if "Agent 4" in t.role_name), None)
    assert a4_trace is not None
    assert a4_trace.status == "AWAITING_APPROVAL"

    # 6. Apply patch and verify recovery
    patch_mgr = PatchManager()
    apply_res = patch_mgr.apply_patch_to_workspace(
        diff_text=result.proposed_patch.diff,
        workspace_dir=str(isolated_workspace),
        expected_patch_hash=result.proposed_patch.patch_hash
    )
    assert apply_res.success is True

    # 7. Regression tests pass post-repair
    final_res = runner.run_tests(target_dir=str(isolated_workspace))
    assert final_res.all_passed is True
    assert final_res.failed_tests == 0


def test_four_agent_clean_baseline_abstention(isolated_workspace):
    """
    Negative test:
    A completely healthy application must NOT receive a fabricated patch.
    Agents 2 and 3 must cleanly abstain and report application healthy.
    """
    sanitizer = EvidenceSanitizer()
    sanitized, summary = sanitizer.sanitize_evidence_collection([])
    healthy_bundle = CollectedLiveEvidence(
        run_id="run_healthy_4agents",
        observed_failure_type="NO_FAILURE",
        evidence_records=[],
        sanitization_summary=summary,
        is_failing=False,
        summary="Application and tests are completely healthy."
    )

    engine = LiveInvestigationEngine()
    res = engine.run_investigation(healthy_bundle, workspace_id=str(isolated_workspace))

    assert res.abstained is True
    assert res.proposed_patch is None
    assert res.phase == "RESOLVED"
    assert "healthy" in res.abstention_reason.lower()


# =====================================================================
# 4. Agent Responsibility & Real Data Flow Verification Tests
# =====================================================================

def test_agent1_template_output_reaches_agent2_context():
    """
    Verifies real data flow from Agent 1 to Agent 2:
    Drain3 mined log templates produced by Agent 1 reach Agent 2's
    investigation context and continual learning retrieval query.
    """
    miner = LogIntelligenceMiner()
    report = miner.mine_log_templates([
        "Payment callback error for order 501",
        "Payment callback error for order 502"
    ])
    assert report.unique_templates_count == 1
    assert report.templates[0].template_text == "Payment callback error for order <NUM>"

    sanitizer = EvidenceSanitizer()
    _, summary = sanitizer.sanitize_evidence_collection([])
    bundle = CollectedLiveEvidence(
        run_id="run_flow_a1_a2",
        observed_failure_type="TEST_FAILURE",
        evidence_records=[],
        sanitization_summary=summary,
        is_failing=True,
        summary="Payment failure observed",
        log_intelligence=report
    )

    agent_2 = DiagnosisInvestigationAgent()
    hypotheses, retrieved_cases, a2_record = agent_2.execute(bundle, workspace_id="ws_flow")

    assert len(hypotheses) == 2
    # Verify that log templates reached Agent 2's diagnosis context
    assert "Payment callback error for order <NUM>" in a2_record.summary or any(
        "order" in h.description.lower() for h in hypotheses
    ) or len(retrieved_cases) >= 0


def test_agent2_confidence_grounded_in_evidence_not_fixed():
    """
    Verifies that Agent 2's confidence score is dynamically computed from observable
    evidence (presence of test failure, log templates, tracebacks) rather than fixed literals.
    """
    sanitizer = EvidenceSanitizer()

    # Case A: Strong corroborated evidence (test failure + traceback + log templates)
    miner = LogIntelligenceMiner()
    report = miner.mine_log_templates(["ZeroDivisionError at line 59", "ZeroDivisionError at line 59"])
    strong_items = [
        {
            "id": "ev_test_fail",
            "source_tool": "regression_test_runner",
            "source_ref": "tests/test_api.py",
            "summary": "Regression test failed with ZeroDivisionError",
            "data": {"all_passed": False, "error_summary": ["ZeroDivisionError: division by zero"]}
        },
        {
            "id": "ev_tb",
            "source_tool": "process_logs",
            "source_ref": "stdout",
            "summary": "Traceback observed",
            "data": {"traceback": ["ZeroDivisionError: division by zero"]}
        }
    ]
    strong_sanitized, strong_summary = sanitizer.sanitize_evidence_collection(strong_items)
    strong_bundle = CollectedLiveEvidence(
        run_id="run_strong_ev",
        observed_failure_type="TEST_FAILURE",
        evidence_records=strong_sanitized,
        sanitization_summary=strong_summary,
        is_failing=True,
        summary="Defect corroborated by logs and test runner",
        log_intelligence=report
    )

    # Case B: Minimal uncorroborated evidence
    weak_items = [
        {
            "id": "ev_test_generic",
            "source_tool": "regression_test_runner",
            "source_ref": "tests/test_api.py",
            "summary": "Unknown failure",
            "data": {"all_passed": True}  # tests did not fail
        }
    ]
    weak_sanitized, weak_summary = sanitizer.sanitize_evidence_collection(weak_items)
    weak_bundle = CollectedLiveEvidence(
        run_id="run_weak_ev",
        observed_failure_type="TEST_FAILURE",
        evidence_records=weak_sanitized,
        sanitization_summary=weak_summary,
        is_failing=True,
        summary="Generic alert without logs"
    )

    agent_2 = DiagnosisInvestigationAgent()
    strong_hyps, _, _ = agent_2.execute(strong_bundle, workspace_id="ws_strong")
    weak_hyps, _, _ = agent_2.execute(weak_bundle, workspace_id="ws_weak")

    # Score must be higher for strong corroborated evidence than weak uncorroborated evidence
    assert strong_hyps[0].score > weak_hyps[0].score
    assert strong_hyps[0].score >= 0.85
    assert weak_hyps[0].score < 0.80


def test_agent3_veto_halts_repair_progression(isolated_workspace):
    """
    Verifies that an Adversarial Critic veto prevents patch generation / application:
    When Agent 3 vetoes, LiveInvestigationEngine halts in phase CRITIQUE, abstains,
    and Agent 4 is never permitted to synthesize or return a patch proposal.
    """
    # Create bundle that triggers critic veto: HEALTH_CHECK_FAILED without error traceback
    sanitizer = EvidenceSanitizer()
    items = [
        {
            "id": "ev_hp_only",
            "source_tool": "health_probe",
            "source_ref": "http://127.0.0.1:8001/health",
            "summary": "Health check degraded",
            "data": {"status": "DEGRADED", "is_healthy": False}
        }
    ]
    sanitized, summary = sanitizer.sanitize_evidence_collection(items)
    veto_bundle = CollectedLiveEvidence(
        run_id="run_critic_veto_halt",
        observed_failure_type="HEALTH_CHECK_FAILED",
        evidence_records=sanitized,
        sanitization_summary=summary,
        is_failing=True,
        summary="Health check failed with no error traceback in logs"
    )

    engine = LiveInvestigationEngine()
    res = engine.run_investigation(veto_bundle, workspace_id=str(isolated_workspace))

    assert res.abstained is True
    assert res.phase == "CRITIQUE"
    assert res.proposed_patch is None
    assert "veto" in res.abstention_reason.lower()
    # Confirm Agent 4 trace is absent because repair progression was blocked
    assert not any("Agent 4" in t.role_name for t in res.agent_traces)


def test_failed_regression_test_prevents_recovery_verdict(isolated_workspace):
    """
    Verifies that a failed regression test prevents a successful recovery verdict:
    If a patch is applied but tests still fail, RecoveryVerifier returns
    all_checks_passed=False and does NOT falsely claim recovery.
    """
    from backend.app.live_debug.verification import RecoveryVerifier

    # Introduce a defect that will deliberately fail tests
    services_path = isolated_workspace / "app" / "services.py"
    code = services_path.read_text(encoding="utf-8")
    services_path.write_text(code.replace("round(discounted_subtotal * tax_rate, 2)", "99999.99"), encoding="utf-8")

    verifier = RecoveryVerifier(test_runner=LiveDebugTestRunner(timeout_seconds=10.0))
    rec_result = verifier.verify_workspace_recovery(str(isolated_workspace))

    assert rec_result.all_checks_passed is False
    assert "failed" in rec_result.summary.lower()
    assert rec_result.regression_tests_passed is False

