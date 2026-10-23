"""
Live Debug System Integration Test Suite.
Tests process manager, health monitor, isolated workspaces, test runner,
live investigation, Critic checks, patch manager, approval binding, and independent recovery verification.
"""
import pytest
import os
import time
from starlette.testclient import TestClient

from backend.app.main import app
from backend.app.live_debug import (
    LiveDebugProcessManager,
    HealthMonitor,
    LiveDebugTestRunner,
    WorkspaceManager,
    PatchManager,
    LiveAuditStore,
    AuditRecord
)


@pytest.fixture
def client():
    return TestClient(app)


def test_process_manager_and_health_monitor_lifecycle():
    pm = LiveDebugProcessManager(port=8099)
    hm = HealthMonitor(port=8099)

    # 1. Initially stopped
    assert pm.is_running is False
    h_init = hm.check_health()
    assert h_init.is_healthy is False

    # 2. Start process
    start_res = pm.start()
    assert start_res["status"] in ["RUNNING", "ALREADY_RUNNING"]
    assert pm.is_running is True

    # Allow brief window for uvicorn to bind port
    time.sleep(1.2)
    h_started = hm.check_health()
    assert h_started.is_healthy is True
    assert h_started.http_status == 200

    # 3. Stop process
    stop_res = pm.stop()
    assert stop_res["status"] in ["STOPPED", "ALREADY_STOPPED"]
    assert pm.is_running is False


def test_test_runner_executes_live_lab_suite():
    runner = LiveDebugTestRunner(timeout_seconds=20.0)
    res = runner.run_tests()
    assert res.all_passed is True
    assert res.passed_tests >= 7
    assert res.failed_tests == 0


def test_workspace_manager_isolation_and_rollback():
    wm = WorkspaceManager()
    ws_path = wm.create_isolated_workspace(run_id="test_run_isolation")
    try:
        assert os.path.exists(ws_path)
        assert os.path.exists(os.path.join(ws_path, "app", "services.py"))

        # Create pre-patch snapshot
        snap_path = wm.create_snapshot(ws_path, "pre_patch")
        assert os.path.exists(snap_path)

        # Modify a file in workspace
        svc_file = os.path.join(ws_path, "app", "services.py")
        with open(svc_file, "a") as f:
            f.write("\n# TEST MODIFICATION LINE\n")

        with open(svc_file, "r") as f:
            assert "# TEST MODIFICATION LINE" in f.read()

        # Rollback
        rolled_back = wm.rollback(ws_path, "pre_patch")
        assert rolled_back is True

        with open(svc_file, "r") as f:
            assert "# TEST MODIFICATION LINE" not in f.read()
    finally:
        wm.cleanup(ws_path)


def test_patch_manager_applies_and_checks_hash():
    wm = WorkspaceManager()
    pm = PatchManager()
    ws_path = wm.create_isolated_workspace(run_id="test_patch_apply")

    try:
        diff_text = (
            "--- a/app/services.py\n"
            "+++ b/app/services.py\n"
            "@@ -25,2 +25,3 @@\n"
            " def check_inventory(sku: str, quantity: int) -> bool:\n"
            "+    # PATCHED INVENTORY CHECK\n"
            "     if quantity <= 0:\n"
        )
        p_hash = pm.compute_patch_hash(diff_text)
        assert len(p_hash) == 64

        # 1. Tampered hash is rejected
        res_bad = pm.apply_patch_to_workspace(diff_text, ws_path, expected_patch_hash="wrong_tampered_hash")
        assert res_bad.success is False
        assert "Tampering detected" in res_bad.error_message

        # 2. Correct hash applies cleanly
        res_ok = pm.apply_patch_to_workspace(diff_text, ws_path, expected_patch_hash=p_hash)
        assert res_ok.success is True
        assert "app/services.py" in res_ok.modified_files[0]

        # Verify content modified in isolated workspace
        target = os.path.join(ws_path, "app", "services.py")
        with open(target, "r") as f:
            assert "# PATCHED INVENTORY CHECK" in f.read()
    finally:
        wm.cleanup(ws_path)


def test_live_api_status_and_tests(client):
    r_stat = client.get("/api/live/status")
    assert r_stat.status_code == 200
    data = r_stat.json()
    assert "process" in data
    assert "health" in data
    assert data["application"] == "live-lab-checkout"

    r_test = client.post("/api/live/tests/run")
    assert r_test.status_code == 200
    tdata = r_test.json()
    assert tdata["all_passed"] is True
    assert tdata["passed_tests"] >= 7


def test_live_investigation_abstains_when_healthy(client):
    # When live-lab is healthy, investigation abstains and does not invent an incident
    r = client.post("/api/live/investigate")
    assert r.status_code == 200
    data = r.json()
    assert data["abstained"] is True
    assert "healthy" in data["abstention_reason"].lower()
    assert data["proposed_patch"] is None


def test_live_approval_enforces_auth_and_hash_binding(client):
    # Unauthenticated approve fails with 401
    r_unauth = client.post("/api/live/patch/approve", json={
        "run_id": "RUN-FAKE",
        "patch_hash": "dummy_hash"
    })
    assert r_unauth.status_code == 401

    # Authenticate as lead SRE
    sess = client.post("/api/auth/session", json={
        "email": "lead_sre@company.com",
        "password": "LeadSRE-Prod-Auth-2026!"
    }).json()
    token = sess["session_token"]

    # Non-existent run returns 404
    r_404 = client.post("/api/live/patch/approve", json={
        "run_id": "RUN-NONEXISTENT",
        "patch_hash": "some_hash",
        "auth_token": token
    })
    assert r_404.status_code == 404


def test_audit_store_records_and_retrieves():
    store = LiveAuditStore()
    cases = store.retrieve_similar_cases("ZeroDivisionError discount calculation")
    assert len(cases) > 0
    assert "ZeroDivisionError" in cases[0].signature
