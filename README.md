# RootTrace — Autonomous Incident Investigation & Verified Recovery

> *"When production breaks, engineers don't need another chatbot. They need an investigator."*

RootTrace is an evidence-driven autonomous software-incident investigation and verified-recovery system. It does not simply summarize logs or guess plausible answers. It systematically gathers real evidence through typed tools, constructs chronological multi-source timelines, generates competing hypotheses, challenges them with an adversarial red-team critic, enforces deterministic safety policies, requests human approval for consequential actions, executes simulated remediations, and verifies genuine recovery against live environment records.

---

## The RootTrace Closed Loop

```
INCIDENT TRIGGERED
  └──> OBSERVE (alert analysis & service telemetry)
         └──> COLLECT EVIDENCE (query_logs, inspect_database, get_trace, etc.)
                └──> BUILD TIMELINE (merged chronological order, causal & red herring detection)
                       └──> GENERATE COMPETING HYPOTHESES (formulate multiple explanations)
                              └──> INVESTIGATE USING TOOLS (gather targeted evidence)
                                     └──> CHALLENGE AND FALSIFY (adversarial red-team critic)
                                            └──> VERIFY ROOT CAUSE (strict deterministic rules)
                                                   └──> ENFORCE SAFETY POLICY (read-only allowed, consequential requires approval)
                                                          └──> REQUEST HUMAN APPROVAL (explicit operator authorization)
                                                                 └──> EXECUTE REMEDIATION (rollback + sequential callback replay)
                                                                        └──> VERIFY ACTUAL RECOVERY (17/17 orders confirmed in simulator)
                                                                               └──> GENERATE POSTMORTEM & STORE INCIDENT MEMORY
```

---

## Architecture

- **Backend**: Python 3.13, FastAPI, Pydantic v2 domain models
- **Frontend**: React 18, TypeScript, Vite, React Flow (`@xyflow/react`) for interactive topological evidence graph, Lucide icons
- **Investigation Streaming**: Real-time Server-Sent Events (SSE) `/api/investigate/stream` for live observable discovery
- **Agent Orchestrator**: Explicit Python State Machine (`InvestigationStateMachine`) controlling 12 lifecycle phases
- **Tools**: 9 real typed tool interfaces (`query_logs`, `inspect_database`, `get_payment_status`, `get_metrics`, `get_trace`, `check_deployments`, `get_git_changes`, `get_service_topology`, `search_historical_incidents`)
- **Reasoning Provider**: Cloud LLM support (Gemini / OpenAI / Anthropic) + Offline Deterministic Reasoning Engine (operates reliably without external API keys or cloud dependencies)
- **Safety Policy**: Independent deterministic policy engine enforcing human-in-the-loop approvals for state-altering actions
- **Simulator**: In-memory stateful infrastructure engine with live mutations and recovery calculation

---

## Scenarios

1. **Scenario A: Callback Race Condition (Primary Demonstration)**
   - Payment succeeds via payment gateway.
   - Concurrent webhook callbacks arrive within milliseconds of each other.
   - Unprotected order state transition collides, setting 17 orders to `FAILED`.
   - Misleading Red Herring: DB replica CPU spikes to 88% *6 minutes after* the failure started (critic identifies and refutes temporal discrepancy).
   - Root Cause: Deployment `v1.2.4-order-sync` removed the Redis distributed lock (`redlock`) to optimize latency.
   - Remediation & Recovery: Rollback to `v1.2.3` + replay failed callbacks sequentially. Real simulator state confirms **17 of 17 affected orders recovered** to `CONFIRMED`.

2. **Scenario B: Database Degradation**
   - Rogue analytics reconciliation query holding locks.
   - Connection pool saturated at 100% (142 clients waiting).
   - Remediation: Terminate rogue query PID 3912 and recycle pool.

3. **Scenario C: Third-Party Payment Gateway Outage**
   - External payment provider returning HTTP 503 Service Unavailable.
   - Remediation: Circuit breaker failover to secondary provider `AdyenBackup`.

---

## Quickstart & Startup Commands

### 1. Build Frontend & Activate Environment
```powershell
# In PowerShell:
cd frontend
$env:PATH = "C:\Program Files\nodejs;$env:PATH"
& "C:\Program Files\nodejs\npm.cmd" run build
cd ..
```

### 2. Run Automated Test Suite
Run all 19 automated verification tests:
```powershell
.venv\Scripts\pytest.exe -v tests
```

### 3. Launch RootTrace Server
Launch the FastAPI server (serves the React SPA on `/` and REST API on `/api`):
```powershell
.venv\Scripts\uvicorn.exe backend.app.main:app --host 127.0.0.1 --port 8000
```

### 4. Open in Browser
Visit: [http://127.0.0.1:8000](http://127.0.0.1:8000)
- Select scenario (e.g. `Concurrent Webhook Race Condition`)
- Click **Auto-Investigate** to watch real-time Server-Sent Events stream each phase, tool invocation, and evidence node
- Inspect discovered nodes on the interactive **React Flow Evidence Graph**
- Review Critic counterarguments and temporal falsification of the DB CPU spike
- Click **Approve & Execute Remediation** to authorize rollback & replay
- Review independent recovery verification (17/17 confirmed in simulator) and postmortem report

---

## Testing Coverage

The automated test suite in `tests/` covers:
- Scenario fixture loading and error handling
- Execution of all 9 investigation tools and tool call audit logs
- End-to-end callback-race diagnosis and red-herring falsification
- Database failure and payment gateway failure scenarios
- Safety policy blocking unverified or paused actions
- Human-in-the-loop authorization enforcement
- Simulated rollback, callback replay, and 17/17 recovery check validation
- Edge cases: missing evidence penalties, contradictory evidence falsification, and offline reasoning engine resilience
