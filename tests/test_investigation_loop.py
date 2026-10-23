import pytest
from backend.app.orchestrator.engine import Orchestrator
from backend.app.models.domain import (
    InvestigationPhase,
    VerificationStatus,
    HypothesisStatus
)


def test_callback_race_diagnosis_end_to_end():
    orch = Orchestrator("callback_race")
    assert orch.incident.current_phase == InvestigationPhase.TRIGGERED

    # Step through investigation loop
    orch.step_observe()
    assert orch.incident.current_phase == InvestigationPhase.OBSERVING

    orch.step_collect_initial_evidence()
    assert orch.incident.current_phase == InvestigationPhase.COLLECTING_INITIAL_EVIDENCE
    assert len(orch.incident.evidence_records) > 0

    orch.step_build_timeline()
    assert orch.incident.current_phase == InvestigationPhase.BUILDING_TIMELINE
    assert len(orch.incident.timeline) > 0

    # Ensure timeline is sorted chronologically
    ts_list = [e.timestamp for e in orch.incident.timeline]
    assert ts_list == sorted(ts_list)

    orch.step_generate_hypotheses()
    assert orch.incident.current_phase == InvestigationPhase.HYPOTHESIS_GENERATION
    assert len(orch.incident.hypotheses) >= 2

    orch.step_investigate_tools()
    assert orch.incident.current_phase == InvestigationPhase.INVESTIGATING

    orch.step_critique()
    assert orch.incident.current_phase == InvestigationPhase.CRITIQUE
    # Verify critic falsified the misleading DB CPU spike hypothesis
    falsified = [h for h in orch.incident.hypotheses if h.status == HypothesisStatus.FALSIFIED]
    assert any(h.id == "hyp_db_saturation" for h in falsified)

    orch.step_verify()
    # Concurrency race hypothesis must be VERIFIED
    assert orch.incident.verification is not None
    assert orch.incident.verification.status == VerificationStatus.VERIFIED
    assert orch.incident.verification.verified_hypothesis_id == "hyp_concurrency_race"
    assert orch.incident.current_phase == InvestigationPhase.AWAITING_APPROVAL


def test_database_failure_scenario():
    orch = Orchestrator("db_degradation")
    orch.run_full_investigation_loop()
    # Should verify or identify pool exhaustion
    assert len(orch.incident.hypotheses) >= 1
    assert any("pool" in h.id for h in orch.incident.hypotheses)


def test_payment_failure_scenario():
    orch = Orchestrator("payment_failure")
    orch.run_full_investigation_loop()
    assert len(orch.incident.hypotheses) >= 1
    assert any("external" in h.id or "outage" in h.id for h in orch.incident.hypotheses)
