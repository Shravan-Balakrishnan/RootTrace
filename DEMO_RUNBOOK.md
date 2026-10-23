# RootTrace Live — Hackathon Demonstration Runbook

This runbook guides presenters through executing a live, verified incident diagnosis and automated repair demonstration of RootTrace Live on the `live-lab` microservice.

---

## 1. Environment Setup & Prerequisites

### Prerequisites
- Python 3.11+ (verified with Python 3.13)
- Node.js 18+ and npm
- Git

### Initial Setup
```bash
# Clone and enter the repository
cd RootTrace

# Activate Python virtual environment
.venv\Scripts\activate   # Windows
# or: source .venv/bin/activate  # macOS / Linux

# Verify Python dependencies
pip check

# Build Frontend Bundle
cd frontend
npm ci
npm run build
cd ..
```

### Required Environment Configuration
RootTrace Live operates fully deterministically offline out of the box using built-in rule grounding, Critic/Veto verification, and template synthesis. To enable live cloud LLM inference:
```bash
# Optional: Set AI Provider key (Anthropic or OpenAI)
set OPENAI_API_KEY=sk-...
# or
set ANTHROPIC_API_KEY=sk-ant-...
```
> **Security Guardrail Notice:** All evidence sent to AI models is automatically sanitized by the RootTrace Secret Scanner and Input Guardrails. Sensitive environment variables, `.env` files, JWTs, Stripe/Slack keys, and prompt injections are redacted or structurally neutralized before dispatch.

---

## 2. Starting RootTrace & Live Lab

Open two terminal windows:

### Terminal 1: RootTrace Backend
```powershell
.venv\Scripts\python.exe -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --reload
```
- RootTrace API & Console: `http://127.0.0.1:8000`
- Swagger Docs: `http://127.0.0.1:8000/docs`

### Terminal 2: RootTrace Frontend
```powershell
cd frontend
$env:PATH = "C:\Program Files\nodejs;" + $env:PATH
npm run dev -- --host 127.0.0.1 --port 5173
```
- Open your browser at: `http://127.0.0.1:5173`

---

## 3. Verifying Baseline Health & Tests

Before presenting, confirm that the system is completely healthy:

1. In the Live Debug Console (`http://127.0.0.1:5173`), inspect the **Process Status Banner**:
   - Status: **HEALTHY**
   - Live Lab App: Port 8001
2. Click **Run Diagnostics / Tests** in the console, or run directly via terminal:
   ```powershell
   .venv\Scripts\pytest.exe -v live-lab/tests
   ```
   **Expected Result:** All 7 baseline tests pass (100% green).

---

## 4. Introducing a Live Defect (Presenter Workflow)

To prove authentic repair, the presenter manually introduces a defect into `live-lab/app/services.py`:

1. Open `live-lab/app/services.py` in an editor.
2. Locate line 59 inside `calculate_order_total`:
   ```python
   tax_amount = round(discounted_subtotal * tax_rate, 2)
   ```
3. Introduce a calculation fault or division by zero:
   ```python
   tax_amount = round(discounted_subtotal / 0, 2)
   ```
4. Save the file.

---

## 5. Triggering & Inspecting the Failure

1. In the Live Debug Console, click **Trigger Health Check & Regression Test**.
2. **Observe Failure Telemetry:**
   - Health status changes to degraded / failing.
   - Captured exception appears in the console:
     `ZeroDivisionError: division by zero` in `app/services.py:59`.
   - The RootTrace Evidence Collector packages process logs, test tracebacks, and git diffs.
   - Secret Scanner validates and sanitizes all telemetry.

---

## 6. Live Investigation, Critic Veto & Patch Proposal

1. Click **Investigate Incident**.
2. **Review AI & Critic Trace:**
   - **Hypothesis 1 (Leading):** Service logic calculation fault in `app/services.py`.
   - **Hypothesis 2 (Competing):** Transient network port or OS binding error.
   - **Critic Verification:** Competing hypothesis falsified; leading hypothesis corroborated by regression test stack trace.
3. **Inspect Candidate Patch Proposal:**
   - Unified diff preview:
     ```diff
     --- a/app/services.py
     +++ b/app/services.py
     @@ -58,4 +58,4 @@
          discounted_subtotal = max(0.0, subtotal - discount_amount)
     -    tax_amount = round(discounted_subtotal / 0, 2)
     +    tax_amount = round(discounted_subtotal * tax_rate, 2)
          final_total = round(discounted_subtotal + tax_amount, 2)
     ```
   - Deterministic SHA-256 Patch Hash is bound to the current proposal.

---

## 7. Review, Approval & Rejection Workflow

### A. Demonstrating Rejection (Safe No-Op)
1. Click **Reject Proposal** with comment: *"Testing rejection safety."*
2. **Verification:**
   - Proposal is dismissed.
   - File `live-lab/app/services.py` is **NOT** modified.
   - Isolated workspace snapshot is cleaned up.

### B. Demonstrating Authenticated Approval
1. Re-run investigation to regenerate the repair proposal.
2. Log in / authenticate as an authorized SRE role (`lead_sre` / `incident_commander`).
3. Click **Approve & Apply Patch**.
4. **Safety Gates Executed Under Concurrency Lock:**
   - Replay protection verifies patch hash and active run ID.
   - Workspace isolation restricts file modifications strictly within workspace bounds.
   - Outside sentinel files are protected.

---

## 8. Verifying Independent Recovery

1. Watch the Live Console transition through:
   `APPLYING` ➔ `APPLIED` ➔ `VALIDATING` ➔ `VERIFIED`
2. RootTrace re-executes the complete `live-lab/tests` regression suite against the repaired workspace.
3. **Recovery Verification Card:**
   - All 7 tests PASS.
   - Health probe returns HTTP 200 OK.
   - Immutable audit trail record is persisted to SQLite / in-memory store.

---

## 9. Resetting Safely to a Clean Baseline

To reset the demonstration back to pristine state for another run:
```powershell
git checkout -- live-lab/app/services.py
.venv\Scripts\pytest.exe -v live-lab/tests
```

---

## 10. Troubleshooting & Fallback Options

| Symptom | Cause | Solution |
| :--- | :--- | :--- |
| `Port 8001 already in use` | Zombie background process | Run `Get-Process python \| Stop-Process` in PowerShell |
| `HTTP 409 Conflict` on Approval | Duplicate approval click or replayed hash | Check active run ID; refresh console to review status |
| `Approval Unauthorized (401)` | Missing or invalid auth session | Re-authenticate with `lead_sre@company.com` |
| `npm run build` fails | Node executable not in PATH | Run `$env:PATH = "C:\Program Files\nodejs;" + $env:PATH` |

### Recording Fallback
If presentation hardware or network connectivity fails, a pre-validated deterministic execution script is available:
```powershell
.venv\Scripts\pytest.exe -v tests/test_live_e2e_workflow.py
```
This demonstrates all 14 steps executing with 100% assertions in ~5 seconds.

---

## 11. Security Limitations & Operational Boundaries

- **Single-Host Boundary:** RootTrace Live is currently configured for localhost development and evaluation testbeds. For multi-node Kubernetes clusters, deploy with distributed Redis locks and persistent volume claims.
- **Secret Scanning Bound:** The regex scanner applies a 500 KB chunk boundary to guarantee ReDoS defense. Never submit raw binary core dumps exceeding this limit.
- **Authentication:** Sessions utilize PBKDF2-HMAC-SHA256 salted hashes stored in `sessions.db`. For enterprise deployments, connect to OIDC / SAML identity providers.
