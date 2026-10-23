import pytest
from backend.app.models.domain import (
    Hypothesis,
    HypothesisStatus,
    VerificationStatus,
    EvidenceRecord
)
from backend.app.evidence.scoring import EvidenceEngine
from backend.app.llm.provider import LLMProvider


def test_missing_evidence_penalty():
    hyp = Hypothesis(
        id="hyp_test",
        title="Test Hypothesis",
        description="Hypothesis with missing expected evidence",
        supporting_evidence_ids=[],
        contradicting_evidence_ids=[],
        expected_evidence=["Evidence A", "Evidence B", "Evidence C"],
        evidence_still_needed=["Evidence A", "Evidence B", "Evidence C"],
        falsification_criteria="None",
        status=HypothesisStatus.PROPOSED
    )
    score = EvidenceEngine.calculate_hypothesis_score(hyp, {})
    # Score should be negative because of missing evidence
    assert score < 0.0


def test_contradictory_evidence_falsification():
    ev = EvidenceRecord(
        id="ev_contra",
        source_tool="query_logs",
        timestamp="2026-10-23T14:00:00Z",
        source_ref="log",
        summary="Deadlock count is 0, no DB deadlocks occurred",
        data={"deadlocks": 0},
        reliability=1.0
    )
    hyp = Hypothesis(
        id="hyp_test",
        title="Test DB Deadlock",
        description="Deadlock caused failure",
        supporting_evidence_ids=[],
        contradicting_evidence_ids=["ev_contra"],
        expected_evidence=[],
        evidence_still_needed=[],
        falsification_criteria="Deadlock count == 0",
        status=HypothesisStatus.PROPOSED
    )
    score = EvidenceEngine.calculate_hypothesis_score(hyp, {"ev_contra": ev})
    assert score <= -0.45
    status = EvidenceEngine.evaluate_hypothesis_status(score, has_contradiction=True)
    assert status == HypothesisStatus.FALSIFIED


def test_model_provider_offline_fallback():
    # LLMProvider must operate reliably in deterministic offline mode
    provider = LLMProvider()
    assert provider.is_available() is True
    status = provider.get_status()
    assert "provider" in status
    assert "mode" in status

    # Verify operations work without crashing or requiring cloud keys
    hyps = provider.generate_competing_hypotheses({"service": "order-service"}, [])
    assert len(hyps) >= 2

    remediation = provider.recommend_remediation("hyp_concurrency_race", "callback_race")
    assert remediation.target_service == "order-service"
