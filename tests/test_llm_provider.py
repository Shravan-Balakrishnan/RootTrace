import pytest
from unittest.mock import MagicMock, patch
import os
from backend.app.llm.provider import LLMProvider, ALLOWED_TOOLS
from backend.app.models.domain import HypothesisStatus, VerificationStatus


def test_provider_status_no_key():
    with patch.dict(os.environ, {}, clear=True):
        provider = LLMProvider()
        status = provider.get_status()
        assert status["state"] == "deterministic"
        assert status["mode"] == "DETERMINISTIC_REASONING_ENGINE"
        assert status["api_key_configured"] is False
        assert "key" not in status


def test_provider_status_with_key_untested():
    with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-fake-test-key-12345678901234567890"}):
        provider = LLMProvider()
        status = provider.get_status()
        assert status["state"] == "cloud_configured"
        assert status["connected"] is False
        assert status["mode"] == "DETERMINISTIC_REASONING_ENGINE"
        assert status["api_key_configured"] is True
        # Ensure no secrets leak
        assert "sk-fake" not in str(status)


def test_tool_name_aliases_get_logs_and_query_logs():
    from backend.app.tools.investigation import ToolRegistry
    from backend.app.sandbox.engine import SimulatedEnvironment
    registry = ToolRegistry(SimulatedEnvironment("callback_race"))
    # Both query_logs and get_logs must exist and be callable
    assert hasattr(registry, "query_logs")
    assert hasattr(registry, "get_logs")
    res1 = registry.query_logs(limit=5)
    assert res1["success"] is True
    res2 = registry.get_logs(limit=5)
    assert res2["success"] is True


def test_all_allowlisted_tools_exist_and_are_callable():
    from backend.app.tools.investigation import ToolRegistry
    from backend.app.sandbox.engine import SimulatedEnvironment
    registry = ToolRegistry(SimulatedEnvironment("callback_race"))
    for tool_name in ALLOWED_TOOLS:
        assert hasattr(registry, tool_name), f"Tool '{tool_name}' in ALLOWED_TOOLS missing on ToolRegistry"
        assert callable(getattr(registry, tool_name)), f"Tool '{tool_name}' on ToolRegistry is not callable"


def test_unsupported_provider_fallback():
    # Configuring Gemini or Anthropic in Phase 1 falls back to deterministic mode with explicit notice
    with patch.dict(os.environ, {"GEMINI_API_KEY": "fake_gemini_key", "OPENAI_API_KEY": ""}, clear=True):
        provider = LLMProvider()
        status = provider.get_status()
        assert status["state"] == "deterministic"
        assert status["mode"] == "DETERMINISTIC_REASONING_ENGINE"
        assert "Gemini" in status["last_error"]
        assert "not supported in Phase 1" in status["last_error"]


def test_hypothesis_generation_grounding():
    provider = LLMProvider()
    obs = {"alert_name": "CallbackRaceDetected", "metric": "failed_orders"}
    hypotheses = provider.generate_competing_hypotheses(obs, [])

    assert len(hypotheses) >= 2
    for h in hypotheses:
        # Crucial grounding rule: Start with status PROPOSED and empty support/contradictions
        assert h.status == HypothesisStatus.PROPOSED
        assert len(h.supporting_evidence_ids) == 0
        assert len(h.contradicting_evidence_ids) == 0
        assert h.falsification_criteria is not None


def test_tool_selection_allowlist():
    provider = LLMProvider()
    obs = {"alert_name": "CallbackRaceDetected"}
    hypotheses = provider.generate_competing_hypotheses(obs, [])

    action = provider.choose_next_action(hypotheses, [], [])
    assert action is not None
    assert action["tool_name"] in ALLOWED_TOOLS


def test_critic_temporal_falsification():
    provider = LLMProvider()
    obs = {"alert_name": "CallbackRaceDetected"}
    hypotheses = provider.generate_competing_hypotheses(obs, [])
    db_hyp = next((h for h in hypotheses if h.id == "hyp_db_saturation"), None)
    assert db_hyp is not None

    eval_res = provider.critique_hypothesis(db_hyp, [], {})
    assert eval_res.is_valid_candidate is False
    assert eval_res.temporal_order_valid is False
    assert any("TEMPORAL FALSIFICATION" in c for c in eval_res.contradictions_found)


def test_mocked_cloud_llm_success():
    with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-mock-key-12345678901234567890"}):
        provider = LLMProvider()
        # Mock the client's chat completion
        mock_completion = MagicMock()
        mock_completion.choices = [
            MagicMock(message=MagicMock(content='''{
                "hypotheses": [
                    {
                        "title": "Mock AI Concurrency Conflict",
                        "description": "Concurrent callbacks collision",
                        "expected_evidence": ["duplicate webhook deliveries"],
                        "evidence_still_needed": ["logs"],
                        "falsification_criteria": "Sequential callbacks"
                    },
                    {
                        "title": "Mock AI DB Lock Timeout",
                        "description": "Database lock wait timeout",
                        "expected_evidence": ["lock wait query"],
                        "evidence_still_needed": ["pg_locks"],
                        "falsification_criteria": "No lock contention"
                    }
                ]
            }'''))
        ]
        provider._client.chat.completions.create = MagicMock(return_value=mock_completion)

        obs = {"alert_name": "CallbackRaceDetected"}
        hypotheses = provider.generate_competing_hypotheses(obs, [])

        assert len(hypotheses) == 2
        assert hypotheses[0].title == "Mock AI Concurrency Conflict"
        assert provider.state == "cloud_ready"
        assert provider.get_status()["state"] == "cloud_ready"
        assert provider.get_status()["connected"] is True
        assert provider.get_status()["mode"] == "CLOUD_AI"


def test_mocked_cloud_llm_failure_safely_falls_back():
    with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-mock-key-12345678901234567890"}):
        provider = LLMProvider()
        # Mock client error (e.g. rate limit or timeout)
        provider._client.chat.completions.create = MagicMock(side_effect=TimeoutError("Request timed out"))

        obs = {"alert_name": "CallbackRaceDetected"}
        # Must not crash, should fall back to deterministic hypotheses and mark cloud_error
        hypotheses = provider.generate_competing_hypotheses(obs, [])

        assert len(hypotheses) >= 2
        assert provider.state == "cloud_error"
        assert "TimeoutError" in provider.last_error
        assert "sk-mock" not in provider.last_error  # No secrets leaked
