import pytest
from fastapi.testclient import TestClient
from backend.app.main import app
from backend.app.models.domain import InvestigationPhase, VerificationStatus, ExecutionStatus


@pytest.fixture
def client():
    return TestClient(app)


def test_fresh_run_isolation(client):
    # Select Scenario A and run investigation
    r1 = client.post("/api/scenarios/select", json={"scenario_id": "callback_race"})
    inc1 = r1.json()["incident"]
    run1 = inc1.get("run_id")
    assert run1 is not None

    # Step investigation to generate evidence
    client.post("/api/investigate/step")
    client.post("/api/investigate/step")
    after_step = client.get("/api/incident").json()
    assert len(after_step["evidence_records"]) > 0

    # Reset investigation: must produce a new run_id and empty evidence
    r_reset = client.post("/api/investigate/reset")
    inc_reset = r_reset.json()["incident"]
    run2 = inc_reset.get("run_id")

    assert run2 != run1
    assert inc_reset["current_phase"] == "TRIGGERED"
    assert len(inc_reset["evidence_records"]) == 0
    assert len(inc_reset["tool_calls"]) == 0
    assert len(inc_reset["timeline"]) == 0


def test_api_remediation_approval_workflow(client):
    client.post("/api/scenarios/select", json={"scenario_id": "callback_race"})
    client.post("/api/investigate/run")

    inc = client.get("/api/incident").json()
    assert inc["current_phase"] == "AWAITING_APPROVAL"
    assert inc["remediation_proposal"] is not None

    # Before approval, orders must be FAILED in simulator
    prop_id = inc["remediation_proposal"]["id"]

    # Reject remediation test
    r_reject = client.post("/api/remediation/reject")
    assert r_reject.status_code == 200

    # Explicit approval
    r_approve = client.post("/api/remediation/approve", json={
        "approver": "lead_sre@company.com",
        "comment": "Rollback to v1.2.3 authorized"
    })
    assert r_approve.status_code == 200
    inc_approved = r_approve.json()["incident"]

    assert inc_approved["current_phase"] == "RESOLVED"
    assert inc_approved["recovery_result"] is not None
    assert inc_approved["recovery_result"]["all_checks_passed"] is True
    assert "17/17" in inc_approved["recovery_result"]["summary"]


def test_scenario_switching_isolates_data(client):
    # Switch to DB degradation
    r_db = client.post("/api/scenarios/select", json={"scenario_id": "db_degradation"})
    inc_db = r_db.json()["incident"]
    assert inc_db["scenario_id"] == "db_degradation"
    assert "orders-db" in inc_db["affected_services"]

    # Switch to Payment failure
    r_pay = client.post("/api/scenarios/select", json={"scenario_id": "payment_failure"})
    inc_pay = r_pay.json()["incident"]
    assert inc_pay["scenario_id"] == "payment_failure"
    assert "payment-service" in inc_pay["affected_services"]


def test_system_status_reports_authentic_llm_mode(client):
    r = client.get("/api/system/status")
    data = r.json()
    assert data["status"] == "ONLINE"
    assert "llm" in data
    # Must report whether API key is configured or deterministic fallback
    assert data["llm"]["mode"] in ["CLOUD_AI", "DETERMINISTIC_REASONING_ENGINE"]
    assert data["tool_count"] == 9
