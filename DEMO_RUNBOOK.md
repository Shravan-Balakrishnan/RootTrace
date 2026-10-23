# RootTrace Live — Hackathon Demonstration Runbook

This runbook guides presenters through executing a live, verified incident diagnosis and automated repair demonstration of RootTrace Live on the `live-lab` microservice.

---

## 1. Environment Setup & Configuration

### Prerequisites
- Python 3.11+ (verified on Python 3.13)
- Node.js 18+ and npm
- Git

### Initial Build & Verification
```powershell
# Clone and enter the repository
cd RootTrace

# Verify dependencies in active Python virtual environment
.venv\Scripts\python.exe -m pip check

# Build Frontend Production Bundle
cd frontend
$env:PATH = "C:\Program Files\nodejs;" + $env:PATH
npm ci
npm run build
cd ..
```

### Security & Demo Credential Configuration
Demo operator passwords are dynamically loaded from environment variables and never bundled into compiled frontend assets:

```powershell
# Copy template and configure your secure demo passwords
Copy-Item .env.example .env

# Set your Lead SRE demo password in PowerShell (or configure in .env)
$env:ROOTTRACE_DEMO_LEAD_SRE_PASSWORD = "YourSecureDemoPassword2026!"
$env:ROOTTRACE_DEMO_CMD_PASSWORD     = "YourSecureCmdPassword2026!"
$env:ROOTTRACE_DEMO_ONCALL_PASSWORD  = "YourSecureOnCallPassword2026!"
```

> **Security & Credential Rotation Notice:**
> Passwords previously used in development or earlier Git commits must be treated as exposed and rotated in any external environments. Active production and evaluation bundles load credentials exclusively from environment variables.

---

## 2. Starting RootTrace & Live Lab

Open two terminal windows:

### Terminal 1: RootTrace Backend
```powershell
$env:ROOTTRACE_DEMO_LEAD_SRE_PASSWORD = "YourSecureDemoPassword2026!"
.venv\Scripts\python.exe -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --reload
```
- RootTrace API & Console: `http://127.0.0.1:8000`
- API Documentation: `http://127.0.0.1:8000/docs`

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
   - Status: **HEALTHY (HTTP 200)**
   - Live Lab App: Port 8001
2. Click **Run Diagnostics / Tests** in the console, or run via terminal:
   ```powershell
   .venv\Scripts\pytest.exe -v live-lab/tests
   ```
   **Expected Result:** All 7 baseline tests pass (100% green).

---

## 4. Primary Demonstration: Behavioral Logic Defect (Silent Calculation Fault)

In this scenario, the microservice remains healthy and responsive to HTTP probes, but a business calculation defect causes silent order total discrepancies.

### Step 1: Introduce the Behavioral Defect
1. Open `live-lab/app/services.py`.
2. Locate line 60 in `calculate_order_total`:
   ```python
   final_total = round(discounted_subtotal + tax_amount, 2)
   ```
3. Omit tax from the final total calculation:
   ```python
   final_total = round(discounted_subtotal, 2)
   ```
4. Save the file.

### Step 2: Trigger & Observe Failure Telemetry
1. In the Live Debug Console, click **Run Regression Tests**.
2. **Observe Behavioral Telemetry:**
   - **Process Probe:** Remains **HEALTHY (HTTP 200)**. The microservice process is alive and responding.
   - **Regression Suite:** Fails with `AssertionError: assert 120.0 == 132.0` in `test_order_calculation_with_discount`.
   - **RootTrace Safeguard:** Does **NOT** mistake HTTP 200 health for system correctness.

---

## 5. Four-Agent Live Investigation & Critic Review

1. Click **Investigate Failure** in the console.
2. **Observe Four-Agent Orchestration Card:**
   - **Agent 1 (Evidence & Log Intelligence):**
     - Collects test runner outputs, process telemetry, and git diffs.
     - Redacts sensitive patterns via bounded Secret Scanner (500 KB limit).
     - **Drain3 Template Mining:** Extracts structured templates (e.g., `Order calculation failed: <NUM> != <NUM>`).
   - **Agent 2 (Diagnosis & Investigation):**
     - Computes dynamic confidence scores grounded in observed test failures and log evidence.
     - Formulates competing hypotheses (Leading: `H1` Code Calculation Defect ~85%+ vs Competing: `H2` Port Contention ~10%).
     - Retrieves verified historical incidents via Continual Learning (`HIST-001`).
   - **Agent 3 (Adversarial Critic):**
     - Checks temporal consistency and asserts evidence support.
     - Corroborates `H1` and issues **Critic Approval** (demonstrating VETO power when evidence is contradictory).
   - **Agent 4 (Repair & Verification):**
     - Synthesizes minimal reviewable unified diff:
       ```diff
       --- a/app/services.py
       +++ b/app/services.py
       @@ -58,4 +58,4 @@
            discounted_subtotal = max(0.0, subtotal - discount_amount)
            tax_amount = round(discounted_subtotal * tax_rate, 2)
       -    final_total = round(discounted_subtotal, 2)
       +    final_total = round(discounted_subtotal + tax_amount, 2)
       ```
     - Computes deterministic SHA-256 patch hash and enforces workspace containment.

---

## 6. Review, Authorization & Patch Application

### A. Demonstrating Server-Side Authorization
1. Select operator: `lead_sre@company.com`.
2. Enter the configured password: `YourSecureDemoPassword2026!`.
3. Click **Approve & Apply Patch**.
4. **Server Authorization Gates:**
   - Server authenticates password via Salted PBKDF2-HMAC-SHA256 and issues ephemeral token.
   - Role policy enforces `lead_sre` authorization (unauthorized roles like `intern` return HTTP 403 Forbidden).
   - Concurrency lock and SQLite state store prevent duplicate/replayed approvals (HTTP 409 Conflict).
   - Pre-application check verifies diff bytes match SHA-256 patch hash.

---

## 7. Verifying Independent Recovery

1. Watch the Live Console transition through:
   `APPLYING` ➔ `APPLIED` ➔ `VALIDATING` ➔ `VERIFIED`
2. RootTrace re-executes `live-lab/tests` regression suite against the repaired isolated workspace.
3. **Recovery Verification Card:**
   - All 7 tests PASS (100%).
   - Expected order calculation ($132.00) restored.
   - Immutable audit trail record persisted with approver provenance and recovery verdict.

---

## 8. Resetting Safely to Clean Baseline

To reset the demonstration back to pristine state for another run:
```powershell
git checkout -- live-lab/app/services.py
.venv\Scripts\pytest.exe -v live-lab/tests
```

---

## 9. Fallback Scenario: Divide-by-Zero Exception

If an uncaught exception scenario is requested:
1. In `live-lab/app/services.py:59`, set:
   ```python
   tax_amount = round(discounted_subtotal / 0, 2)
   ```
2. Save and click **Investigate Failure**.
3. System captures `ZeroDivisionError`, Drain3 templates repeating callback traces, Agent 3 approves, and Agent 4 repairs to `tax_amount = round(discounted_subtotal * tax_rate, 2)`.
4. Reset via `git checkout -- live-lab/app/services.py`.

---

## 10. Operational Security Limitations

- **Authentication Boundary:** Passwords and session tokens utilize salted PBKDF2-HMAC-SHA256 and shared SQLite persistence. In enterprise environments, configure corporate OIDC/SAML providers.
- **Input Guardrails:** Regex scanner applies a 500 KB chunk boundary to guarantee ReDoS defense.
- **Isolation Boundary:** Patches are confined within target workspaces; path traversal and outside directory modifications are rejected with security errors.
