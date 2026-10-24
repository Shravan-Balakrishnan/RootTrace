"""
FastAPI REST Routes for RootTrace API.
"""
from fastapi import APIRouter, HTTPException, Header
from pydantic import BaseModel, field_validator
import re
from typing import Dict, Any, List, Optional
from ..orchestrator.engine import Orchestrator
from ..sandbox.scenarios import ALL_SCENARIOS

router = APIRouter(prefix="/api")

# Global singleton orchestrator
orchestrator = Orchestrator(scenario_id="callback_race")


class ScenarioSelectRequest(BaseModel):
    scenario_id: str


class SessionInitRequest(BaseModel):
    email: str
    password: Optional[str] = None


class ApprovalRequest(BaseModel):
    auth_token: Optional[str] = None
    approver: Optional[str] = None
    role: Optional[str] = None
    comment: Optional[str] = None

    @field_validator("approver")
    @classmethod
    def validate_approver(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        if not isinstance(v, str):
            raise ValueError("Approver identity must be a string.")
        trimmed = v.strip()
        if not trimmed:
            raise ValueError("Approver identity cannot be blank or whitespace.")
        if len(trimmed) < 3:
            raise ValueError("Approver identity must be at least 3 characters long.")
        if not re.match(r"^[a-zA-Z0-9_.\-+@]+$", trimmed):
            raise ValueError("Approver identity contains invalid characters.")
        return trimmed


class ToolInvocationRequest(BaseModel):
    tool_name: str
    arguments: Dict[str, Any] = {}


@router.get("/scenarios")
def list_scenarios():
    return [
        {
            "id": s_id,
            "title": data["title"],
            "description": data["description"],
            "severity": data["severity"],
            "affected_services": data["affected_services"]
        }
        for s_id, data in ALL_SCENARIOS.items()
    ]


@router.post("/scenarios/select")
def select_scenario(req: ScenarioSelectRequest):
    if req.scenario_id not in ALL_SCENARIOS:
        raise HTTPException(status_code=400, detail=f"Scenario '{req.scenario_id}' not found.")
    inc = orchestrator.reset_scenario(req.scenario_id)
    return {"message": f"Scenario switched to '{req.scenario_id}'", "incident": inc.model_dump()}


@router.get("/incident")
def get_incident():
    return orchestrator.incident.model_dump()


@router.post("/investigate/step")
def step_investigation():
    phase = orchestrator.incident.current_phase
    from ..models.domain import InvestigationPhase

    if phase == InvestigationPhase.TRIGGERED:
        orchestrator.step_observe()
    elif phase == InvestigationPhase.OBSERVING:
        orchestrator.step_collect_initial_evidence()
    elif phase == InvestigationPhase.COLLECTING_INITIAL_EVIDENCE:
        orchestrator.step_build_timeline()
    elif phase == InvestigationPhase.BUILDING_TIMELINE:
        orchestrator.step_generate_hypotheses()
    elif phase == InvestigationPhase.HYPOTHESIS_GENERATION:
        orchestrator.step_investigate_tools()
    elif phase == InvestigationPhase.INVESTIGATING:
        orchestrator.step_critique()
    elif phase == InvestigationPhase.CRITIQUE:
        orchestrator.step_verify()
    elif phase == InvestigationPhase.VERIFYING:
        # Check if approval needed or if can proceed
        if orchestrator.incident.remediation_proposal:
            orchestrator.incident.decision_trace.append("Investigation verified. Awaiting operator approval for remediation.")
    else:
        return {"message": f"Cannot step from phase '{phase.value}'", "incident": orchestrator.incident.model_dump()}

    return {"message": f"Stepped to '{orchestrator.incident.current_phase.value}'", "incident": orchestrator.incident.model_dump()}


@router.post("/investigate/reset")
def reset_investigation():
    inc = orchestrator.reset_investigation()
    return {"message": "Investigation reset with fresh run ID and clean simulator state", "incident": inc.model_dump()}


@router.get("/investigate/stream")
async def stream_investigation():
    import asyncio
    import json
    from fastapi.responses import StreamingResponse
    from ..models.domain import InvestigationPhase

    async def event_generator():
        # First ensure incident is in initial phase
        if orchestrator.incident.current_phase != InvestigationPhase.TRIGGERED:
            orchestrator.reset_investigation()

        yield f"data: {json.dumps({'event': 'started', 'incident': orchestrator.incident.model_dump()})}\n\n"
        await asyncio.sleep(0.3)

        pipeline_init = [
            ("observe", orchestrator.step_observe, 0.4),
            ("collect_initial", orchestrator.step_collect_initial_evidence, 0.5),
            ("build_timeline", orchestrator.step_build_timeline, 0.4),
            ("hypotheses", orchestrator.step_generate_hypotheses, 0.5),
        ]

        for name, step_fn, delay in pipeline_init:
            if orchestrator.incident.is_autonomous_paused:
                yield f"data: {json.dumps({'event': 'paused', 'incident': orchestrator.incident.model_dump()})}\n\n"
                return

            step_fn()
            yield f"data: {json.dumps({'event': name, 'phase': orchestrator.incident.current_phase.value, 'incident': orchestrator.incident.model_dump()})}\n\n"
            await asyncio.sleep(delay)

        # Granular investigation tool execution
        orchestrator._transition_to(InvestigationPhase.INVESTIGATING, "Invoking targeted investigation tools to test hypotheses")
        yield f"data: {json.dumps({'event': 'investigating_started', 'phase': orchestrator.incident.current_phase.value, 'incident': orchestrator.incident.model_dump()})}\n\n"
        await asyncio.sleep(0.3)

        for _ in range(4):
            if orchestrator.incident.is_autonomous_paused:
                yield f"data: {json.dumps({'event': 'paused', 'incident': orchestrator.incident.model_dump()})}\n\n"
                return

            act = orchestrator.step_single_tool()
            if not act:
                break
            yield f"data: {json.dumps({'event': 'tool_invoked', 'tool': act['tool_name'], 'phase': orchestrator.incident.current_phase.value, 'incident': orchestrator.incident.model_dump()})}\n\n"
            await asyncio.sleep(0.45)

        pipeline_verify = [
            ("critique", orchestrator.step_critique, 0.5),
            ("verify", orchestrator.step_verify, 0.4)
        ]

        for name, step_fn, delay in pipeline_verify:
            if orchestrator.incident.is_autonomous_paused:
                yield f"data: {json.dumps({'event': 'paused', 'incident': orchestrator.incident.model_dump()})}\n\n"
                return

            step_fn()
            yield f"data: {json.dumps({'event': name, 'phase': orchestrator.incident.current_phase.value, 'incident': orchestrator.incident.model_dump()})}\n\n"
            await asyncio.sleep(delay)

        if orchestrator.incident.current_phase == InvestigationPhase.AWAITING_APPROVAL:
            yield f"data: {json.dumps({'event': 'awaiting_approval', 'incident': orchestrator.incident.model_dump()})}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.post("/investigate/run")
def run_investigation():
    inc = orchestrator.run_full_investigation_loop()
    return {"message": f"Investigation loop reached phase '{inc.current_phase.value}'", "incident": inc.model_dump()}


AUTHORIZED_APPROVER_ROLES = {
    "incident_commander",
    "oncall_sre",
    "lead_sre",
    "staff_sre",
    "principal_sre"
}


def _validate_and_bind_arguments(tool_name: str, tool_fn: Any, args: Dict[str, Any]) -> Dict[str, Any]:
    import inspect
    import typing

    sig = inspect.signature(tool_fn)
    try:
        bound = sig.bind(**args)
        bound.apply_defaults()
    except TypeError as e:
        raise HTTPException(status_code=400, detail=f"Invalid arguments for tool '{tool_name}': {str(e)}")

    def check_type(val: Any, expected: Any) -> bool:
        if expected is inspect.Parameter.empty or val is None:
            return True
        origin = typing.get_origin(expected)
        type_args = typing.get_args(expected)
        if origin is typing.Union:
            return any(check_type(val, t) for t in type_args)
        if expected is int:
            return isinstance(val, int) and not isinstance(val, bool)
        if expected is str:
            return isinstance(val, str)
        if expected is float:
            return isinstance(val, (int, float)) and not isinstance(val, bool)
        if expected is bool:
            return isinstance(val, bool)
        if expected is list or origin is list:
            return isinstance(val, list)
        if expected is dict or origin is dict:
            return isinstance(val, dict)
        if isinstance(expected, type):
            return isinstance(val, expected)
        return True

    for param_name, val in bound.arguments.items():
        param = sig.parameters.get(param_name)
        if param and param.annotation != inspect.Parameter.empty and val is not None:
            if not check_type(val, param.annotation):
                expected_name = getattr(param.annotation, "__name__", str(param.annotation))
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid type for argument '{param_name}' on tool '{tool_name}': expected {expected_name}, got {type(val).__name__}."
                )

    return bound.arguments


@router.post("/investigate/tool")
def invoke_tool(req: ToolInvocationRequest):
    from ..llm.provider import ALLOWED_TOOLS

    # 1. Restrict strictly to explicit allowlist of read-only investigative tools
    if req.tool_name not in ALLOWED_TOOLS:
        raise HTTPException(
            status_code=400,
            detail=f"Tool '{req.tool_name}' is not in the allowed investigative tools set. Permitted tools: {sorted(list(ALLOWED_TOOLS))}"
        )

    # 2. Block access to private/internal/dunder methods
    if req.tool_name.startswith("_"):
        raise HTTPException(
            status_code=400,
            detail=f"Access to private/internal method '{req.tool_name}' is prohibited."
        )

    tool_fn = getattr(orchestrator.tools, req.tool_name, None)
    if not tool_fn or not callable(tool_fn):
        raise HTTPException(status_code=400, detail=f"Tool '{req.tool_name}' is not executable.")

    # 3. Validate parameter names, required parameters, and runtime types
    validated_args = _validate_and_bind_arguments(req.tool_name, tool_fn, req.arguments)

    # 4. Invoke tool and handle results
    try:
        res = tool_fn(**validated_args)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Tool '{req.tool_name}' execution failed: {str(e)}")

    if isinstance(res, dict) and not res.get("success", True):
        # Returned error response from tool implementation
        return {
            "tool": req.tool_name,
            "status": "FAILED",
            "error": res.get("error", "Tool execution reported failure"),
            "result": res,
            "incident": orchestrator.incident.model_dump()
        }

    # 5. Sync new evidence into incident model
    for eid in res.get("evidence_ids", []):
        orchestrator.incident.evidence_records[eid] = orchestrator.tools.evidence_store[eid]
    orchestrator.incident.tool_calls = list(orchestrator.tools.tool_logs)
    orchestrator.incident.timeline = orchestrator.incident.timeline

    return {
        "tool": req.tool_name,
        "status": "COMPLETED",
        "result": res,
        "incident": orchestrator.incident.model_dump()
    }


@router.post("/auth/session")
def initialize_session(req: SessionInitRequest):
    """
    Authenticates an operator with real verified credentials (salted PBKDF2-HMAC-SHA256)
    against the organization directory and issues an ephemeral, cryptographically random session token.
    An email alone CANNOT obtain an authenticated session.
    """
    from ..safety.auth import create_authenticated_session
    session = create_authenticated_session(req.email, password=req.password)
    return {
        "session_token": session.token,
        "email": session.principal.email,
        "name": session.principal.name,
        "role": session.principal.role,
        "expires_at": session.expires_at.isoformat()
    }


@router.get("/auth/me")
def get_current_user_profile(authorization: Optional[str] = Header(None)):
    """Returns the verified profile of the active authenticated session. Never leaks tokens."""
    from ..safety.auth import authenticate_and_authorize_approver
    if not authorization:
        raise HTTPException(status_code=401, detail="Authentication required: Missing Authorization header.")
    principal = authenticate_and_authorize_approver(auth_token=authorization)
    return {
        "email": principal.email,
        "name": principal.name,
        "role": principal.role
    }


@router.post("/remediation/approve")
def approve_remediation(req: ApprovalRequest):
    from ..safety.auth import authenticate_and_authorize_approver

    # Server-verified identity: token is mandatory; identity and role are derived strictly on the server
    principal = authenticate_and_authorize_approver(
        auth_token=req.auth_token,
        client_claimed_approver=req.approver,
        client_claimed_role=req.role
    )

    try:
        orchestrator.approve_remediation(
            approver=principal.email,
            comment=req.comment,
            role=principal.role
        )
        return {
            "success": True,
            "message": "Remediation executed and verified.",
            "verified_principal": {
                "email": principal.email,
                "role": principal.role,
                "name": principal.name
            },
            "incident": orchestrator.incident.model_dump()
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/remediation/reject")
def reject_remediation(comment: Optional[str] = "Operator requested additional diagnostic investigation."):
    orchestrator.incident.decision_trace.append(f"Remediation REJECTED by operator: {comment}")
    return {"success": True, "message": "Remediation proposal rejected.", "incident": orchestrator.incident.model_dump()}


@router.post("/autonomy/pause")
def pause_autonomy():
    orchestrator.pause_autonomy()
    return {"message": "Autonomy paused.", "incident": orchestrator.incident.model_dump()}


@router.post("/autonomy/resume")
def resume_autonomy():
    orchestrator.resume_autonomy()
    return {"message": "Autonomy resumed.", "incident": orchestrator.incident.model_dump()}


@router.get("/system/status")
def system_status():
    from ..config import load_dotenv
    load_dotenv()
    if not orchestrator.llm.config.api_key_configured or orchestrator.llm.config.provider == "deterministic":
        orchestrator.llm = LLMProvider()
    if orchestrator.llm.state == "cloud_configured" and orchestrator.llm._client:
        try:
            orchestrator.llm._client.chat.completions.create(
                model=orchestrator.llm.config.model_name,
                messages=[{"role": "user", "content": "ping"}],
                max_tokens=2,
                timeout=3.0
            )
            orchestrator.llm.state = "cloud_ready"
        except Exception as e:
            orchestrator.llm.state = "cloud_error"
            orchestrator.llm.last_error = orchestrator.llm._sanitize(str(e))
    return {
        "status": "ONLINE",
        "llm": orchestrator.llm.get_status(),
        "active_scenario": orchestrator.scenario_id,
        "tool_count": 9,
        "version": "1.0.0-roottrace"
    }


@router.get("/memory/postmortems")
def get_postmortems():
    return orchestrator.memory.list_all()
