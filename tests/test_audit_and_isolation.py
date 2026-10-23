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

    # Missing approver must fail validation (HTTP 422)
    r_missing = client.post("/api/remediation/approve", json={})
    assert r_missing.status_code == 422

    # Blank approver must fail validation (HTTP 400 or 422)
    r_blank = client.post("/api/remediation/approve", json={"approver": "   "})
    assert r_blank.status_code in [400, 422]

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


def test_sse_stream_events_delivery(client):
    # Select Scenario A and connect to stream
    client.post("/api/scenarios/select", json={"scenario_id": "callback_race"})
    with client.stream("GET", "/api/investigate/stream") as response:
        assert response.status_code == 200
        assert "text/event-stream" in response.headers["content-type"]
        events = []
        for line in response.iter_lines():
            if line.startswith("data: "):
                import json
                ev = json.loads(line[6:])
                events.append(ev)

        assert len(events) >= 5
        event_names = [e.get("event") for e in events]
        assert "started" in event_names
        assert "investigating_started" in event_names
        assert "tool_invoked" in event_names
        assert "verify" in event_names
        assert "awaiting_approval" in event_names
        # Every event must carry a consistent run_id
        run_ids = {e["incident"]["run_id"] for e in events if "incident" in e and "run_id" in e["incident"]}
        assert len(run_ids) == 1


def test_invoke_tool_allowlist_enforcement(client):
    # Attempting to invoke a non-allowlisted tool or arbitrary function must be rejected
    r1 = client.post("/api/investigate/tool", json={"tool_name": "execute_remediation", "arguments": {}})
    assert r1.status_code == 400
    assert "not in the allowed investigative tools set" in r1.json()["detail"]

    r2 = client.post("/api/investigate/tool", json={"tool_name": "_record_call", "arguments": {}})
    assert r2.status_code == 400


def test_invoke_tool_argument_validation(client):
    # Calling an allowed tool with invalid/unexpected arguments must return 400
    r = client.post("/api/investigate/tool", json={
        "tool_name": "get_payment_status",
        "arguments": {"invalid_param_foo": 123}
    })
    assert r.status_code == 400
    assert "Invalid arguments for tool" in r.json()["detail"]

    # Calling with valid arguments must succeed
    r_valid = client.post("/api/investigate/tool", json={
        "tool_name": "get_payment_status",
        "arguments": {"order_id": "ord_1001"}
    })
    assert r_valid.status_code == 200
    assert r_valid.json()["result"]["success"] is True


def test_invoke_tool_runtime_type_validation(client):
    # Sending string or list where int is expected (e.g. limit on query_logs) must return 400
    r_bad_type = client.post("/api/investigate/tool", json={
        "tool_name": "query_logs",
        "arguments": {"limit": "not_an_integer"}
    })
    assert r_bad_type.status_code == 400
    assert "Invalid type for argument 'limit'" in r_bad_type.json()["detail"]

    r_bad_type_bool = client.post("/api/investigate/tool", json={
        "tool_name": "query_logs",
        "arguments": {"limit": True}
    })
    assert r_bad_type_bool.status_code == 400


def test_invoke_tool_failed_execution_handling(client):
    # Limit out of bounds (1..200) triggers failure in tool logic, returning structured FAILED status
    r = client.post("/api/investigate/tool", json={
        "tool_name": "query_logs",
        "arguments": {"limit": 999}
    })
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "FAILED"
    assert "Limit must be between 1 and 200" in data["error"]


def test_invoke_tool_rejects_mutating_and_unknown_methods(client):
    # Unknown tool
    r1 = client.post("/api/investigate/tool", json={"tool_name": "completely_unknown_tool", "arguments": {}})
    assert r1.status_code == 400

    # Internal or mutating method
    r2 = client.post("/api/investigate/tool", json={"tool_name": "__init__", "arguments": {}})
    assert r2.status_code == 400


def test_approver_whitespace_rejection(client):
    # Setup incident to awaiting approval
    client.post("/api/scenarios/select", json={"scenario_id": "callback_race"})
    client.post("/api/investigate/run")

    # Whitespace-only approver must be rejected
    r_space = client.post("/api/remediation/approve", json={"approver": "   "})
    assert r_space.status_code in [400, 422]

    # Too short / invalid chars
    r_short = client.post("/api/remediation/approve", json={"approver": "a"})
    assert r_short.status_code in [400, 422]


def test_approver_role_authorization_enforcement(client):
    # Setup incident to awaiting approval
    client.post("/api/scenarios/select", json={"scenario_id": "callback_race"})
    client.post("/api/investigate/run")

    # Unauthorized role must be rejected with HTTP 403 Forbidden
    r_unauth = client.post("/api/remediation/approve", json={
        "approver": "intern_user",
        "role": "intern"
    })
    assert r_unauth.status_code == 403
    assert "is not authorized to approve" in r_unauth.json()["detail"]

    # Authorized role succeeds
    r_auth = client.post("/api/remediation/approve", json={
        "approver": "lead_sre@company.com",
        "role": "incident_commander"
    })
    assert r_auth.status_code == 200
    assert r_auth.json()["success"] is True
    assert r_auth.json()["incident"]["approval"]["role"] == "incident_commander"
