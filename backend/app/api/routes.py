"""
FastAPI REST Routes for RootTrace API.
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Dict, Any, List, Optional
from ..orchestrator.engine import Orchestrator
from ..sandbox.scenarios import ALL_SCENARIOS

router = APIRouter(prefix="/api")

# Global singleton orchestrator
orchestrator = Orchestrator(scenario_id="callback_race")


class ScenarioSelectRequest(BaseModel):
    scenario_id: str


class ApprovalRequest(BaseModel):
    approver: str
    comment: Optional[str] = None


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


@router.post("/investigate/tool")
def invoke_tool(req: ToolInvocationRequest):
    from ..llm.provider import ALLOWED_TOOLS
    import inspect

    # Restrict strictly to explicit allowlist of read-only investigative tools
    if req.tool_name not in ALLOWED_TOOLS:
        raise HTTPException(
            status_code=400,
            detail=f"Tool '{req.tool_name}' is not in the allowed investigative tools set. Permitted tools: {sorted(list(ALLOWED_TOOLS))}"
        )

    tool_fn = getattr(orchestrator.tools, req.tool_name, None)
    if not tool_fn or not callable(tool_fn) or req.tool_name.startswith("_"):
        raise HTTPException(status_code=400, detail=f"Tool '{req.tool_name}' is not executable.")

    # Validate arguments against the tool callable signature before executing
    try:
        sig = inspect.signature(tool_fn)
        sig.bind(**req.arguments)
    except TypeError as e:
        raise HTTPException(status_code=400, detail=f"Invalid arguments for tool '{req.tool_name}': {str(e)}")

    res = tool_fn(**req.arguments)
    # Sync new evidence
    for eid in res.get("evidence_ids", []):
        orchestrator.incident.evidence_records[eid] = orchestrator.tools.evidence_store[eid]
    orchestrator.incident.tool_calls = list(orchestrator.tools.tool_logs)
    orchestrator.incident.timeline = orchestrator.incident.timeline

    return {
        "tool": req.tool_name,
        "result": res,
        "incident": orchestrator.incident.model_dump()
    }


@router.post("/remediation/approve")
def approve_remediation(req: ApprovalRequest):
    try:
        orchestrator.approve_remediation(approver=req.approver, comment=req.comment)
        return {
            "success": True,
            "message": "Remediation executed and verified.",
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
