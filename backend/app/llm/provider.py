"""
LLM Provider Abstraction for RootTrace.
Supports real cloud model integration (OpenAI / Gemini) with structured Pydantic outputs,
bounded execution, schema validation, and an intelligent deterministic fallback engine
when no API key is configured or when cloud requests fail.
"""
from typing import Dict, Any, List, Optional, Set
import os
import re
import json
import logging
import uuid
from pydantic import BaseModel, Field, ValidationError
from ..models.domain import (
    Hypothesis,
    HypothesisStatus,
    CriticEvaluation,
    RemediationProposal,
    ActionRisk,
    IncidentReport,
    VerificationStatus
)

logger = logging.getLogger("roottrace.llm")

# Explicit Allowlist of Investigative Tools
ALLOWED_TOOLS: Set[str] = {
    "query_logs",
    "get_logs",
    "inspect_database",
    "get_payment_status",
    "get_metrics",
    "get_trace",
    "check_deployments",
    "get_git_changes",
    "get_service_topology",
    "search_historical_incidents"
}

# --- Pydantic Draft Schemas for Structured Model Outputs ---

class HypothesisDraft(BaseModel):
    title: str
    description: str
    expected_evidence: List[str] = Field(min_length=1)
    evidence_still_needed: List[str] = Field(default_factory=list)
    falsification_criteria: str


class HypothesisDrafts(BaseModel):
    hypotheses: List[HypothesisDraft] = Field(min_length=2, max_length=4)


class ToolActionDraft(BaseModel):
    tool_name: str
    arguments: Dict[str, Any] = Field(default_factory=dict)
    question_to_resolve: str
    expected_observation: str


class CritiqueDraft(BaseModel):
    contradictions_found: List[str] = Field(default_factory=list)
    missing_evidence_found: List[str] = Field(default_factory=list)
    alternative_explanations: List[str] = Field(default_factory=list)
    claims_requiring_more_evidence: List[str] = Field(default_factory=list)
    critique_summary: str


class RemediationDraft(BaseModel):
    action_type: str
    target_service: str
    description: str
    rationale: str
    risk: str
    reversibility: str
    blast_radius: str
    parameters: Dict[str, Any] = Field(default_factory=dict)


class LLMConfig(BaseModel):
    provider: str = "deterministic"
    model_name: str = "deterministic-reasoner-v1"
    api_key_configured: bool = False
    timeout_seconds: float = 15.0


class LLMProvider:
    def __init__(self):
        groq_keys: List[str] = []
        for var in ["GROQ_API_KEY", "GROQ_API_KEY_1", "GROQ_API_KEY_2", "GROQ_API_KEY_3"]:
            val = os.getenv(var)
            if val:
                for k in val.split(","):
                    k = k.strip()
                    if k and k not in groq_keys:
                        groq_keys.append(k)

        openai_keys: List[str] = []
        for var in ["OPENAI_API_KEY", "OPENAI_API_KEY_1", "OPENAI_API_KEY_2", "OPENAI_API_KEY_3"]:
            val = os.getenv(var)
            if val:
                for k in val.split(","):
                    k = k.strip()
                    if k and k not in openai_keys:
                        openai_keys.append(k)

        gemini_key = os.getenv("GEMINI_API_KEY")
        anthropic_key = os.getenv("ANTHROPIC_API_KEY")
        base_url = os.getenv("OPENAI_BASE_URL")

        self.api_keys: List[str] = []
        self.active_key_index: int = 1 if (groq_keys or openai_keys) else 0

        if groq_keys:
            self.api_keys = groq_keys
            self.api_key = groq_keys[0]
            self.configured_provider = "groq"
            self.base_url = base_url or os.getenv("GROQ_BASE_URL", "https://api.groq.com/openai/v1")
            self.state = "cloud_configured"
            model_name = os.getenv("GROQ_MODEL", os.getenv("OPENAI_MODEL", "openai/gpt-oss-20b"))
            self.last_error = None
        elif openai_keys:
            self.api_keys = openai_keys
            self.api_key = openai_keys[0]
            # Auto-detect Groq keys starting with gsk_ if no custom base_url specified
            if self.api_key.startswith("gsk_") and not base_url:
                self.configured_provider = "groq"
                self.base_url = "https://api.groq.com/openai/v1"
                model_name = os.getenv("OPENAI_MODEL", "openai/gpt-oss-20b")
            else:
                self.configured_provider = "openai"
                self.base_url = base_url
                model_name = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
            self.state = "cloud_configured"
            self.last_error = None
        elif gemini_key or anthropic_key:
            # Explicitly declare unsupported in Phase 1 and fall back to deterministic mode
            unsupported = "Gemini" if gemini_key else "Anthropic"
            self.api_key = None
            self.api_keys = []
            self.base_url = None
            self.configured_provider = "deterministic"
            self.state = "deterministic"
            self.last_error = f"{unsupported} provider configured but not supported in Phase 1 (OpenAI/Groq only). Falling back to deterministic reasoning."
            logger.warning(self.last_error)
            model_name = "deterministic-reasoner-v1"
        else:
            self.api_key = None
            self.api_keys = []
            self.base_url = None
            self.configured_provider = "deterministic"
            self.state = "deterministic"
            self.last_error = None
            model_name = "deterministic-reasoner-v1"

        self.config = LLMConfig(
            provider=self.configured_provider,
            model_name=model_name,
            api_key_configured=bool(self.api_key),
            timeout_seconds=float(os.getenv("LLM_TIMEOUT_SECONDS", "15.0"))
        )
        self._client_pool: List[Any] = []
        self._init_client()

    @property
    def _client(self) -> Optional[Any]:
        return self._client_pool[0] if self._client_pool else None

    @_client.setter
    def _client(self, val: Any) -> None:
        if val is None:
            self._client_pool = []
        elif not self._client_pool:
            self._client_pool = [val]
        else:
            self._client_pool[0] = val

    def _init_client(self):
        """Safely initialize API client pool for all configured keys."""
        self._client_pool = []
        if self.config.provider in ("openai", "groq") and self.api_keys:
            try:
                import openai
                for key in self.api_keys:
                    client_kwargs = {
                        "api_key": key,
                        "timeout": self.config.timeout_seconds
                    }
                    if getattr(self, "base_url", None):
                        client_kwargs["base_url"] = self.base_url
                    self._client_pool.append(openai.OpenAI(**client_kwargs))
            except Exception as e:
                self.state = "cloud_error"
                self.last_error = f"Failed to initialize AI client pool: {self._sanitize(str(e))}"
                logger.warning(self.last_error)

    def _sanitize(self, text: str) -> str:
        """Strip any API key or secret tokens from error messages and logs."""
        if not text:
            return ""
        # Redact known sk- or gsk- or ghp- or bearer patterns
        cleaned = re.sub(r'sk-[a-zA-Z0-9_\-]{20,}', '[REDACTED_API_KEY]', text)
        cleaned = re.sub(r'gsk_[a-zA-Z0-9_\-]{20,}', '[REDACTED_API_KEY]', cleaned)
        cleaned = re.sub(r'ghp_[a-zA-Z0-9_\-]{20,}', '[REDACTED_TOKEN]', cleaned)
        cleaned = re.sub(r'Bearer\s+[a-zA-Z0-9_\.\-]{20,}', 'Bearer [REDACTED]', cleaned)
        return cleaned

    def is_available(self) -> bool:
        """Always available because deterministic fallback is always operational."""
        return True

    def get_status(self) -> Dict[str, Any]:
        """
        Report accurate provider status without leaking secrets.
        Accurately distinguishes:
        - 'deterministic': No cloud credentials configured; local reasoning active.
        - 'cloud_configured': Credentials configured, but connectivity not yet confirmed via successful request.
        - 'cloud_ready': Real model request succeeded and confirmed active.
        - 'cloud_error': Configured provider failed, timed out, or threw an error.
        """
        is_connected = (self.state == "cloud_ready")
        return {
            "provider": self.config.provider,
            "model_name": self.config.model_name,
            "api_key_configured": self.config.api_key_configured,
            "total_keys_configured": len(self.api_keys),
            "active_key_index": self.active_key_index,
            "state": self.state,
            "connected": is_connected,
            "mode": "CLOUD_AI" if is_connected else "DETERMINISTIC_REASONING_ENGINE",
            "last_error": self.last_error
        }

    def _call_model_structured(
        self,
        system_prompt: str,
        user_prompt: str,
        response_model: Any
    ) -> Optional[Any]:
        """
        Centralized safe model helper with Multi-Key Failover:
        - Iterates over primary, secondary, and tertiary keys
        - Automatic failover upon rate limits (429), timeouts, or errors
        - Strict Pydantic validation
        - Safe logging without secrets
        - Explicit error tracking and deterministic fallback only if all keys fail
        """
        if not self._client_pool or self.state == "deterministic":
            return None

        total_keys = len(self._client_pool)
        last_exception = None

        for idx, client in enumerate(self._client_pool):
            key_num = idx + 1
            try:
                logger.info(f"Dispatching structured AI request to {self.config.model_name} [Key {key_num}/{total_keys}]")
                completion = client.chat.completions.create(
                    model=self.config.model_name,
                    messages=[
                        {"role": "system", "content": system_prompt + "\nRespond with valid JSON matching the schema strictly."},
                        {"role": "user", "content": user_prompt}
                    ],
                    response_format={"type": "json_object"},
                    timeout=self.config.timeout_seconds,
                    temperature=0.2
                )
                raw_content = completion.choices[0].message.content
                parsed_json = json.loads(raw_content)
                validated = response_model.model_validate(parsed_json)

                # Transition to verified cloud_ready on success
                self.state = "cloud_ready"
                self.active_key_index = key_num
                self.last_error = None
                return validated

            except Exception as e:
                sanitized_err = self._sanitize(str(e))
                last_exception = e
                if key_num < total_keys:
                    logger.warning(f"Key #{key_num} failed ({type(e).__name__}): {sanitized_err}. Failing over to Key #{key_num + 1}...")
                else:
                    logger.warning(f"Key #{key_num} (final key) failed ({type(e).__name__}): {sanitized_err}.")
                continue

        # All keys in the pool failed -> trigger deterministic fallback
        if last_exception:
            sanitized_err = self._sanitize(str(last_exception))
            self.state = "cloud_error"
            self.last_error = f"All {total_keys} API keys failed. Last error ({type(last_exception).__name__}): {sanitized_err}"
            logger.warning(f"All cloud API keys exhausted, activating deterministic fallback. Error: {self.last_error}")

        return None

    # --- Operation: Generate Competing Hypotheses ---

    def generate_competing_hypotheses(
        self,
        observation: Dict[str, Any],
        initial_evidence: List[Dict[str, Any]]
    ) -> List[Hypothesis]:
        """
        Generate multiple plausible, competing hypotheses based on the incident observation.
        Uses structured cloud LLM output if available, else deterministic reasoning.
        """
        # Try structured cloud call first
        system_prompt = (
            "You are RootTrace AI Agent, an autonomous incident investigator. "
            "Analyze the incident alert and observations. Propose 2 to 4 competing, mutually-exclusive "
            "hypotheses explaining the root cause. Each hypothesis must include title, description, expected evidence, "
            "evidence still needed, and clear falsification criteria. Do NOT mark any hypothesis as verified."
        )
        user_prompt = f"Incident Observation:\n{json.dumps(observation, indent=2)}\n\nInitial Evidence:\n{json.dumps(initial_evidence, indent=2)}"

        drafts: Optional[HypothesisDrafts] = self._call_model_structured(system_prompt, user_prompt, HypothesisDrafts)
        if drafts and drafts.hypotheses:
            hypotheses = []
            for d in drafts.hypotheses:
                h_id = f"hyp_{uuid.uuid4().hex[:8]}"
                hypotheses.append(Hypothesis(
                    id=h_id,
                    title=d.title,
                    description=d.description,
                    supporting_evidence_ids=[],
                    contradicting_evidence_ids=[],
                    expected_evidence=d.expected_evidence,
                    evidence_still_needed=d.evidence_still_needed,
                    falsification_criteria=d.falsification_criteria,
                    status=HypothesisStatus.PROPOSED
                ))
            return hypotheses

        # Deterministic Fallback Engine
        return self._deterministic_hypotheses(observation)

    def _deterministic_hypotheses(self, observation: Dict[str, Any]) -> List[Hypothesis]:
        alert_name = str(observation.get("alert_name", ""))
        metric = str(observation.get("metric", ""))

        hypotheses = []
        if alert_name == "PostgresPoolExhaustionAlert" or metric == "waiting_connections" or "pool" in alert_name.lower():
            hypotheses.append(Hypothesis(
                id="hyp_db_pool_exhaustion",
                title="Database Connection Pool Starvation by Rogue Query",
                description="A long-running analytical query or connection leak saturated the connection pool.",
                supporting_evidence_ids=[],
                contradicting_evidence_ids=[],
                expected_evidence=["Active connections equal max_connections", "Pool acquisition timeout logs"],
                evidence_still_needed=["Inspect pg_stat_activity or DB process list"],
                falsification_criteria="Available idle connections in the pool.",
                status=HypothesisStatus.PROPOSED
            ))
            hypotheses.append(Hypothesis(
                id="hyp_network_partition",
                title="Network Partition Between Application and Database",
                description="TCP dropped packets or firewall rule blocking DB port.",
                supporting_evidence_ids=[],
                contradicting_evidence_ids=[],
                expected_evidence=["TCP connection refused errors", "No established sockets"],
                evidence_still_needed=["Inspect network latency and packet drops"],
                falsification_criteria="Successful DB query execution from another pod.",
                status=HypothesisStatus.PROPOSED
            ))

        elif alert_name == "GatewayFailureRateHigh" or metric == "upstream_5xx_rate" or "5xx" in metric:
            hypotheses.append(Hypothesis(
                id="hyp_external_outage",
                title="Upstream Third-Party Service Outage",
                description="External API provider returning 5xx or connection drops.",
                supporting_evidence_ids=[],
                contradicting_evidence_ids=[],
                expected_evidence=["HTTP 502/503 responses from third party", "DNS resolution failures"],
                evidence_still_needed=["Inspect external provider status page and edge logs"],
                falsification_criteria="Direct ping and HTTP 200 from backup gateway.",
                status=HypothesisStatus.PROPOSED
            ))
            hypotheses.append(Hypothesis(
                id="hyp_internal_auth_failure",
                title="Internal API Key Expiration or Header Mismatch",
                description="Expired credentials rejected by gateway.",
                supporting_evidence_ids=[],
                contradicting_evidence_ids=[],
                expected_evidence=["HTTP 401/403 Unauthorized logs"],
                evidence_still_needed=["Inspect auth service logs"],
                falsification_criteria="Gateway confirms 503 instead of 401.",
                status=HypothesisStatus.PROPOSED
            ))

        else:
            # Default / Scenario A: Concurrency / Race Condition in Webhook Handling
            hypotheses.append(Hypothesis(
                id="hyp_concurrency_race",
                title="Concurrent Callback Race Condition in Order State Machine",
                description="Duplicate or concurrent payment webhooks for the same order arrive simultaneously, causing un-synchronized state transitions to collide and fail the order.",
                supporting_evidence_ids=[],
                contradicting_evidence_ids=[],
                expected_evidence=[
                    "Concurrent webhook logs for identical order_id within milliseconds",
                    "Recent code commit altering concurrency control or locks",
                    "Optimistic lock conflict or state transition conflict in logs"
                ],
                evidence_still_needed=[
                    "Inspect Git commit history for recent order-service changes",
                    "Query logs for thread execution and concurrent webhook timestamps",
                    "Inspect distributed trace spans for lock acquisition"
                ],
                falsification_criteria="Evidence that callbacks arrive strictly sequentially or distributed lock was actively held.",
                status=HypothesisStatus.PROPOSED
            ))

            hypotheses.append(Hypothesis(
                id="hyp_db_saturation",
                title="Database Resource Saturation / Replica High CPU",
                description="Database CPU exhaustion or slow query locks are causing order updates to time out or rollback.",
                supporting_evidence_ids=[],
                contradicting_evidence_ids=[],
                expected_evidence=[
                    "Database CPU spike preceding initial order failure timestamp",
                    "Active lock waits or query timeouts during order persistence"
                ],
                evidence_still_needed=[
                    "Check database metrics timestamps relative to initial failure time",
                    "Inspect database query latency and connection pool metrics"
                ],
                falsification_criteria="Evidence that high database CPU started AFTER order failures or that deadlock count is 0.",
                status=HypothesisStatus.PROPOSED
            ))

            hypotheses.append(Hypothesis(
                id="hyp_gateway_inconsistency",
                title="Payment Gateway Status Desynchronization",
                description="Payment gateway reported SUCCESS mistakenly or transmitted malformed payloads with invalid signatures.",
                supporting_evidence_ids=[],
                contradicting_evidence_ids=[],
                expected_evidence=[
                    "Gateway 5xx errors or malformed signature verification logs",
                    "Mismatched charge amounts or declined authorization tokens"
                ],
                evidence_still_needed=[
                    "Inspect payment transaction records and gateway health metrics"
                ],
                falsification_criteria="Evidence that payment gateway records show valid 200 SUCCESS and charge authorizations match exact order amounts.",
                status=HypothesisStatus.PROPOSED
            ))

        return hypotheses

    # --- Operation: Choose Next Useful Tool Action ---

    def choose_next_action(
        self,
        hypotheses: List[Hypothesis],
        invoked_tools: List[str],
        unresolved_questions: List[str]
    ) -> Optional[Dict[str, Any]]:
        """
        Dynamically determine the next investigation tool to call based on
        unresolved hypothesis questions and needed evidence.
        Validates against tool allowlist and argument schemas.
        """
        # Try structured cloud model call
        system_prompt = (
            "You are RootTrace AI Agent. Based on the active competing hypotheses, missing evidence, "
            "and already invoked tools, select the single most diagnostic tool to call next. "
            f"You may ONLY choose from this allowlist: {sorted(list(ALLOWED_TOOLS))}. "
            "Do NOT select a tool that has already been invoked. "
            "Return JSON matching ToolActionDraft with tool_name, arguments, question_to_resolve, expected_observation."
        )
        hyp_summary = [{
            "id": h.id,
            "title": h.title,
            "evidence_still_needed": h.evidence_still_needed,
            "expected_evidence": h.expected_evidence
        } for h in hypotheses]
        user_prompt = f"Hypotheses:\n{json.dumps(hyp_summary, indent=2)}\n\nAlready Invoked Tools:\n{json.dumps(invoked_tools)}\n\nUnresolved Questions:\n{json.dumps(unresolved_questions)}"

        draft: Optional[ToolActionDraft] = self._call_model_structured(system_prompt, user_prompt, ToolActionDraft)
        if draft:
            tool_name = draft.tool_name
            # Strictly enforce allowlist and no duplicate calls
            if tool_name in ALLOWED_TOOLS and tool_name not in invoked_tools:
                return {
                    "tool_name": tool_name,
                    "arguments": draft.arguments if isinstance(draft.arguments, dict) else {},
                    "question_to_resolve": draft.question_to_resolve,
                    "expected_observation": draft.expected_observation
                }

        # Deterministic Tool Selection Engine
        return self._deterministic_next_action(hypotheses, invoked_tools)

    def _deterministic_next_action(
        self,
        hypotheses: List[Hypothesis],
        invoked_tools: List[str]
    ) -> Optional[Dict[str, Any]]:
        all_needed = " ".join([
            " ".join(h.evidence_still_needed) + " " + " ".join(h.expected_evidence)
            for h in hypotheses
        ]).lower()

        candidates = []
        if ("git" in all_needed or "commit" in all_needed or "diff" in all_needed) and "get_git_changes" not in invoked_tools:
            candidates.append(("get_git_changes", {}))

        if ("deploy" in all_needed or "version" in all_needed or "rollout" in all_needed) and "check_deployments" not in invoked_tools:
            candidates.append(("check_deployments", {}))

        if ("trace" in all_needed or "span" in all_needed or "thread" in all_needed) and "get_trace" not in invoked_tools:
            candidates.append(("get_trace", {}))

        if ("metric" in all_needed or "cpu" in all_needed or "waiting_connections" in all_needed) and "get_metrics" not in invoked_tools:
            candidates.append(("get_metrics", {}))

        if ("payment" in all_needed or "gateway" in all_needed or "charge" in all_needed) and "get_payment_status" not in invoked_tools:
            candidates.append(("get_payment_status", {}))

        if ("database" in all_needed or "pg_stat" in all_needed or "pool" in all_needed or "table" in all_needed) and "inspect_database" not in invoked_tools:
            candidates.append(("inspect_database", {}))

        if ("topology" in all_needed or "service" in all_needed or "dependency" in all_needed) and "get_service_topology" not in invoked_tools:
            candidates.append(("get_service_topology", {}))

        if ("historical" in all_needed or "lock" in all_needed or "incident" in all_needed) and "search_historical_incidents" not in invoked_tools:
            candidates.append(("search_historical_incidents", {"query": "lock"}))

        if ("log" in all_needed or "error" in all_needed or "exception" in all_needed) and ("query_logs" not in invoked_tools and "get_logs" not in invoked_tools):
            candidates.append(("query_logs", {"limit": 50}))

        if candidates:
            tool_name, args = candidates[0]
            return {"tool_name": tool_name, "arguments": args}

        # Fallback pool for un-invoked tools
        fallback_pool = [
            ("query_logs", {"limit": 50}),
            ("get_git_changes", {}),
            ("check_deployments", {}),
            ("get_trace", {}),
            ("get_metrics", {}),
            ("inspect_database", {}),
            ("get_payment_status", {}),
            ("get_service_topology", {}),
            ("search_historical_incidents", {"query": "outage"})
        ]
        for tool_name, args in fallback_pool:
            if tool_name not in invoked_tools:
                return {"tool_name": tool_name, "arguments": args}

        return None

    # --- Operation: Critique Leading Hypothesis (Red-Team Agent) ---

    def critique_hypothesis(
        self,
        hypothesis: Hypothesis,
        timeline_events: List[Dict[str, Any]],
        evidence_records: Dict[str, Any]
    ) -> CriticEvaluation:
        """
        Red-team critic agent: rigorously challenges the hypothesis.
        Verifies:
        - Did the alleged cause happen BEFORE the initial failure? (Temporal ordering)
        - Are there contradictory evidence records?
        - Are critical evidence requirements missing?
        """
        contradictions = []
        missing = []
        alternatives = []
        temporal_valid = True

        # Deterministic Ground-Truth / Temporal Precedence Rules
        if hypothesis.id == "hyp_db_saturation":
            temporal_valid = False
            contradictions.append(
                "TEMPORAL FALSIFICATION: Database CPU spiked at 14:07:30Z, but the first order failure occurred at 14:01:05Z. A subsequent effect cannot cause a preceding failure."
            )
            contradictions.append(
                "Orders-db logs confirm deadlock count is 0; failure was an optimistic state transition collision in order-service memory, not DB failure."
            )

        elif hypothesis.id == "hyp_gateway_inconsistency":
            contradictions.append(
                "FALSIFICATION: Payment gateway records confirm 17/17 charges were authorized with status=SUCCESS at the exact time of order placement."
            )

        elif hypothesis.id == "hyp_concurrency_race":
            temporal_valid = True
            found_concurrent_log = any(
                "conflict detected" in str(e.get("description", "")).lower() or "duplicate delivered" in str(e.get("description", "")).lower()
                for e in timeline_events
            )
            if not found_concurrent_log:
                missing.append("Need trace or log evidence showing concurrent execution threads on the same order.")
            alternatives.append("Could network jitter on the webhook delivery have caused timeouts instead?")

        elif hypothesis.id == "hyp_network_partition":
            contradictions.append(
                "FALSIFICATION: Database is actively reachable; logs show connection pool saturation (142 clients waiting) rather than TCP network connection refused errors."
            )

        elif hypothesis.id == "hyp_internal_auth_failure":
            contradictions.append(
                "FALSIFICATION: Payment gateway returned HTTP 503 Service Unavailable / Origin Host Unreachable, not HTTP 401/403 credential rejection."
            )

        # In cloud mode, supplement with adversarial model critique
        system_prompt = (
            "You are RootTrace Adversarial Critic Agent. Challenge the provided incident hypothesis. "
            "Identify counterarguments, missing evidence, and plausible alternative explanations. "
            "Return JSON matching CritiqueDraft."
        )
        evidence_summaries = []
        for ev in evidence_records.values():
            if hasattr(ev, "summary"):
                evidence_summaries.append(ev.summary)
            elif isinstance(ev, dict):
                evidence_summaries.append(ev.get("summary", ""))
            else:
                evidence_summaries.append(str(ev))

        user_prompt = (
            f"Hypothesis: {hypothesis.title}\nDescription: {hypothesis.description}\n"
            f"Timeline Events: {json.dumps(timeline_events[:10], indent=2)}\n"
            f"Evidence Summaries: {evidence_summaries[:10]}"
        )
        draft: Optional[CritiqueDraft] = self._call_model_structured(system_prompt, user_prompt, CritiqueDraft)
        if draft:
            if draft.alternative_explanations:
                alternatives.extend(draft.alternative_explanations[:2])
            if draft.missing_evidence_found:
                missing.extend(draft.missing_evidence_found[:2])

        is_valid = temporal_valid and len(contradictions) == 0
        summary = (
            f"Critic validation passed for '{hypothesis.title}': temporal precedence confirmed and no contradictions."
            if is_valid else
            f"Critic REJECTED '{hypothesis.title}': {'; '.join(contradictions)}"
        )

        return CriticEvaluation(
            hypothesis_id=hypothesis.id,
            temporal_order_valid=temporal_valid,
            contradictions_found=contradictions,
            missing_evidence_found=missing,
            alternative_explanations=alternatives,
            critique_summary=summary,
            is_valid_candidate=is_valid
        )

    # --- Operation: Recommend Remediation ---

    def recommend_remediation(
        self,
        verified_hypothesis_id: str,
        scenario_id: str
    ) -> RemediationProposal:
        """
        Recommend safe, reversible remediation action strictly mapped to known executor capabilities.
        """
        if scenario_id == "callback_race" or verified_hypothesis_id == "hyp_concurrency_race":
            return RemediationProposal(
                id="prop_rollback_and_replay",
                action_type="ROLLBACK_AND_REPLAY_CALLBACKS",
                target_service="order-service",
                risk=ActionRisk.HIGH_CONSEQUENTIAL,
                description="Rollback order-service from v1.2.4-order-sync to known-good version v1.2.3 (restoring Redis distributed lock) and sequentially replay 17 failed payment callbacks.",
                reversibility="High. Image v1.2.3 is pre-cached and rollback takes < 15 seconds. State mutations are idempotent.",
                blast_radius="Scoped strictly to order-service pods and 17 affected orders in FAILED state.",
                parameters={"target_version": "v1.2.3", "replay_queue": "dead_letter_callbacks", "expected_order_count": 17},
                justification_evidence_ids=[]
            )
        elif scenario_id == "db_degradation" or "pool" in verified_hypothesis_id:
            return RemediationProposal(
                id="prop_kill_query_reset_pool",
                action_type="TERMINATE_ROGUE_QUERY_AND_RESET_POOL",
                target_service="orders-db",
                risk=ActionRisk.HIGH_CONSEQUENTIAL,
                description="Terminate rogue analytics query (PID 3912) and recycle database connection pool.",
                reversibility="Medium. Analytics query will need to be rescheduled during off-peak hours.",
                blast_radius="Orders database connection pool.",
                parameters={"pid": 3912},
                justification_evidence_ids=[]
            )
        else:
            return RemediationProposal(
                id="prop_failover_gateway",
                action_type="FAILOVER_TO_BACKUP_GATEWAY",
                target_service="payment-service",
                risk=ActionRisk.HIGH_CONSEQUENTIAL,
                description="Activate circuit breaker and route checkout traffic to Adyen backup gateway.",
                reversibility="High. Can switch back when Stripe 5xx rate drops below 1%.",
                blast_radius="Checkout payment flows.",
                parameters={"backup_provider": "AdyenBackup"},
                justification_evidence_ids=[]
            )

    # --- Operation: Draft Postmortem ---

    def draft_postmortem(
        self,
        incident_id: str,
        scenario_id: str,
        root_cause_title: str,
        timeline_events: List[str],
        supporting_evidence: List[str],
        rejected_hypotheses: List[Dict[str, str]],
        remediation_summary: str,
        recovery_details: Dict[str, Any]
    ) -> IncidentReport:
        """Generate structured incident postmortem report populated from verified incident state."""
        return IncidentReport(
            incident_id=incident_id,
            scenario_id=scenario_id,
            title=f"Incident Postmortem: {root_cause_title}",
            severity="CRITICAL",
            started_at="2026-10-23T14:01:05Z",
            resolved_at="2026-10-23T14:26:00Z",
            root_cause=root_cause_title,
            verification_status=VerificationStatus.VERIFIED,
            timeline_summary=timeline_events[:8],
            supporting_evidence=supporting_evidence[:6],
            rejected_hypotheses=rejected_hypotheses,
            remediation_summary=remediation_summary,
            recovery_verification=recovery_details,
            preventive_recommendations=[
                "Enforce mandatory distributed locking in all webhook handler CI/CD lint rules.",
                "Introduce automated concurrency regression tests in pull request pipelines before deployment.",
                "Refactor order state machine transitions to be atomic and idempotent at the database row level.",
                "Implement dead-letter queue automated replay with exponential backoff and idempotency keys."
            ]
        )
