import pytest
from backend.app.sandbox.engine import SimulatedEnvironment
from backend.app.sandbox.scenarios import ALL_SCENARIOS, get_scenario_fixture
from backend.app.tools.investigation import ToolRegistry


def test_scenario_loading():
    for sc_id in ["callback_race", "db_degradation", "payment_failure"]:
        data = get_scenario_fixture(sc_id)
        assert data["scenario_id"] == sc_id
        assert len(data["affected_services"]) > 0


def test_invalid_scenario_loading():
    with pytest.raises(ValueError):
        get_scenario_fixture("non_existent_scenario")


def test_all_nine_tools_execution():
    sandbox = SimulatedEnvironment("callback_race")
    registry = ToolRegistry(sandbox)

    # 1. query_logs
    res1 = registry.query_logs(limit=10)
    assert res1["success"] is True
    assert len(res1["evidence_ids"]) > 0

    # 2. inspect_database
    res2 = registry.inspect_database()
    assert res2["success"] is True
    assert "orders_status_distribution" in res2["data"]

    # 3. get_payment_status
    res3 = registry.get_payment_status()
    assert res3["success"] is True
    assert len(res3["evidence_ids"]) == 17

    # 4. get_metrics
    res4 = registry.get_metrics("orders-db")
    assert res4["success"] is True

    # 5. get_trace
    res5 = registry.get_trace()
    assert res5["success"] is True

    # 6. check_deployments
    res6 = registry.check_deployments()
    assert res6["success"] is True
    assert len(res6["deployments"]) >= 2

    # 7. get_git_changes
    res7 = registry.get_git_changes()
    assert res7["success"] is True
    assert len(res7["evidence_ids"]) >= 1

    # 8. get_service_topology
    res8 = registry.get_service_topology()
    assert res8["success"] is True
    assert "services" in res8["topology"]

    # 9. search_historical_incidents
    res9 = registry.search_historical_incidents("lock")
    assert res9["success"] is True

    # Verify tool log auditing
    assert len(registry.tool_logs) == 9
    for log in registry.tool_logs:
        assert log.status == "COMPLETED"
        assert log.duration_ms >= 0.0


def test_tool_invalid_input_handling():
    sandbox = SimulatedEnvironment("callback_race")
    registry = ToolRegistry(sandbox)

    # Invalid query_logs limit > 200
    res = registry.query_logs(limit=999)
    assert res["success"] is False
    assert "error" in res
    assert registry.tool_logs[-1].status == "FAILED"
