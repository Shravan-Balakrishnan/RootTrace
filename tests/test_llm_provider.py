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


def test_groq_provider_configuration():
    # Direct GROQ_API_KEY
    with patch.dict(os.environ, {"GROQ_API_KEY": "gsk_test12345678901234567890", "OPENAI_API_KEY": ""}, clear=True):
        provider = LLMProvider()
        status = provider.get_status()
        assert status["provider"] == "groq"
        assert status["model_name"] == "openai/gpt-oss-20b"
        assert status["api_key_configured"] is True
        assert provider.base_url == "https://api.groq.com/openai/v1"
        assert "gsk_test" not in str(status)

    # OPENAI_API_KEY starting with gsk_ auto-detected
    with patch.dict(os.environ, {"OPENAI_API_KEY": "gsk_autodetect1234567890123456", "GROQ_API_KEY": ""}, clear=True):
        provider = LLMProvider()
        status = provider.get_status()
        assert status["provider"] == "groq"
        assert status["model_name"] == "openai/gpt-oss-20b"
        assert provider.base_url == "https://api.groq.com/openai/v1"


def test_multi_key_failover_pool():
    # 3 Keys configured (Primary, Secondary, Tertiary)
    env = {
        "GROQ_API_KEY": "gsk_primary12345678901234567890",
        "GROQ_API_KEY_2": "gsk_secondary12345678901234567890",
        "GROQ_API_KEY_3": "gsk_tertiary12345678901234567890",
        "OPENAI_API_KEY": ""
    }
    with patch.dict(os.environ, env, clear=True):
        provider = LLMProvider()
        status = provider.get_status()
        assert status["total_keys_configured"] == 3
        assert len(provider._client_pool) == 3

        # Key 1 fails with rate limit (429), Key 2 succeeds!
        provider._client_pool[0].chat.completions.create = MagicMock(side_effect=Exception("Rate limit 429"))
        mock_completion = MagicMock()
        mock_completion.choices = [
            MagicMock(message=MagicMock(content='''{
                "hypotheses": [
                    {
                        "title": "Failover Hyp 1",
                        "description": "Desc 1",
                        "expected_evidence": ["ev1"],
                        "evidence_still_needed": [],
                        "falsification_criteria": "crit1"
                    },
                    {
                        "title": "Failover Hyp 2",
                        "description": "Desc 2",
                        "expected_evidence": ["ev2"],
                        "evidence_still_needed": [],
                        "falsification_criteria": "crit2"
                    }
                ]
            }'''))
        ]
        provider._client_pool[1].chat.completions.create = MagicMock(return_value=mock_completion)

        obs = {"alert_name": "CallbackRaceDetected"}
        hypotheses = provider.generate_competing_hypotheses(obs, [])

        assert len(hypotheses) == 2
        assert hypotheses[0].title == "Failover Hyp 1"
        assert provider.state == "cloud_ready"
        assert provider.active_key_index == 2  # Switched to Key 2!


def test_multi_key_all_fail_falls_back():
    env = {
        "GROQ_API_KEY_1": "gsk_key1_12345678901234567890",
        "GROQ_API_KEY_2": "gsk_key2_12345678901234567890",
        "OPENAI_API_KEY": ""
    }
    with patch.dict(os.environ, env, clear=True):
        provider = LLMProvider()
        # Both keys fail
        provider._client_pool[0].chat.completions.create = MagicMock(side_effect=Exception("Key 1 Rate Limit 429"))
        provider._client_pool[1].chat.completions.create = MagicMock(side_effect=Exception("Key 2 Rate Limit 429"))

        obs = {"alert_name": "CallbackRaceDetected"}
        hypotheses = provider.generate_competing_hypotheses(obs, [])

        # Gracefully falls back to deterministic reasoning without crashing
        assert len(hypotheses) >= 2
        assert provider.state == "cloud_error"
        assert "All 2 API keys failed" in provider.last_error


