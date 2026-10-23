/**
 * RootTrace - Autonomous Incident Investigation & Recovery Frontend Controller
 */

let incidentState = null;
let systemState = null;
let selectedEvidence = null;

// DOM Elements
const scenarioSelect = document.getElementById('scenario-select');
const btnStep = document.getElementById('btn-step');
const btnRun = document.getElementById('btn-run');
const btnPause = document.getElementById('btn-pause');
const incidentStatusBadge = document.getElementById('incident-status-badge');
const incidentSeverityBadge = document.getElementById('incident-severity-badge');
const incidentTitle = document.getElementById('incident-title');
const currentPhaseLabel = document.getElementById('current-phase-label');
const hypothesesContainer = document.getElementById('hypotheses-container');
const timelineContainer = document.getElementById('timeline-container');
const toolLogContainer = document.getElementById('tool-log-container');
const decisionTraceContainer = document.getElementById('decision-trace-container');
const approvalCard = document.getElementById('approval-card');
const recoveryCard = document.getElementById('recovery-card');
const postmortemModal = document.getElementById('postmortem-modal');
const evidenceModal = document.getElementById('evidence-modal');

const PHASES = [
  "TRIGGERED", "OBSERVING", "COLLECTING_INITIAL_EVIDENCE", "BUILDING_TIMELINE",
  "HYPOTHESIS_GENERATION", "INVESTIGATING", "CRITIQUE", "VERIFYING",
  "AWAITING_APPROVAL", "REMEDIATING", "VERIFYING_RECOVERY", "RESOLVED"
];

// Initialize on Load
document.addEventListener('DOMContentLoaded', async () => {
  await loadScenarios();
  await refreshSystemStatus();
  await fetchIncidentState();
  initEvidenceGraph();
});

async function loadScenarios() {
  try {
    const res = await fetch('/api/scenarios');
    const scenarios = await res.json();
    scenarioSelect.innerHTML = scenarios.map(s => 
      `<option value="${s.id}">${s.title}</option>`
    ).join('');
  } catch (err) {
    console.error("Failed to load scenarios", err);
  }
}

async function refreshSystemStatus() {
  try {
    const res = await fetch('/api/system/status');
    systemState = await res.json();
    const modeBadge = document.getElementById('system-mode-badge');
    if (modeBadge && systemState) {
      modeBadge.textContent = systemState.llm.mode;
      modeBadge.className = systemState.llm.api_key_configured ? 'badge badge-info' : 'badge badge-warning';
    }
  } catch (err) {
    console.error("Failed to fetch system status", err);
  }
}

async function fetchIncidentState() {
  try {
    const res = await fetch('/api/incident');
    incidentState = await res.json();
    renderAll();
  } catch (err) {
    console.error("Failed to fetch incident", err);
  }
}

// Controls
scenarioSelect.addEventListener('change', async (e) => {
  const scenarioId = e.target.value;
  try {
    const res = await fetch('/api/scenarios/select', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ scenario_id: scenarioId })
    });
    const data = await res.json();
    incidentState = data.incident;
    renderAll();
  } catch (err) {
    alert("Error switching scenario: " + err);
  }
});

btnStep.addEventListener('click', async () => {
  btnStep.disabled = true;
  try {
    const res = await fetch('/api/investigate/step', { method: 'POST' });
    const data = await res.json();
    incidentState = data.incident;
    renderAll();
  } catch (err) {
    alert("Step error: " + err);
  } finally {
    btnStep.disabled = false;
  }
});

btnRun.addEventListener('click', async () => {
  btnRun.disabled = true;
  btnRun.innerHTML = `<span class="spinner"></span> Investigating...`;
  try {
    const res = await fetch('/api/investigate/run', { method: 'POST' });
    const data = await res.json();
    incidentState = data.incident;
    renderAll();
  } catch (err) {
    alert("Investigation loop error: " + err);
  } finally {
    btnRun.disabled = false;
    btnRun.innerHTML = `<span>⚡</span> Auto-Investigate`;
  }
});

btnPause.addEventListener('click', async () => {
  const isPaused = incidentState?.is_autonomous_paused;
  const endpoint = isPaused ? '/api/autonomy/resume' : '/api/autonomy/pause';
  const res = await fetch(endpoint, { method: 'POST' });
  const data = await res.json();
  incidentState = data.incident;
  renderAll();
});

// Render Main UI
function renderAll() {
  if (!incidentState) return;

  // Title and Badges
  incidentTitle.textContent = incidentState.title;
  currentPhaseLabel.textContent = `Phase: ${incidentState.current_phase}`;
  
  incidentStatusBadge.textContent = incidentState.current_phase;
  incidentStatusBadge.className = `badge ${getPhaseBadgeClass(incidentState.current_phase)}`;

  incidentSeverityBadge.textContent = incidentState.severity;
  incidentSeverityBadge.className = `badge ${incidentState.severity === 'CRITICAL' ? 'badge-critical' : 'badge-warning'}`;

  // Autonomy Button State
  btnPause.textContent = incidentState.is_autonomous_paused ? "Resume Autonomy" : "Pause Autonomy";
  btnPause.className = incidentState.is_autonomous_paused ? "btn btn-success" : "btn btn-secondary";

  renderStepper();
  renderHypotheses();
  renderTimeline();
  renderToolLogs();
  renderDecisionTrace();
  renderApprovalSection();
  renderRecoverySection();
  drawEvidenceGraph();
}

function getPhaseBadgeClass(phase) {
  if (phase === "RESOLVED") return "badge-success";
  if (phase === "AWAITING_APPROVAL") return "badge-warning";
  if (phase === "FAILED") return "badge-critical";
  return "badge-info";
}

function renderStepper() {
  const container = document.getElementById('stepper-container');
  if (!container) return;

  const currentIdx = PHASES.indexOf(incidentState.current_phase);

  container.innerHTML = PHASES.map((p, idx) => {
    let statusClass = "";
    if (idx < currentIdx) statusClass = "completed";
    else if (idx === currentIdx) statusClass = "active";

    return `
      <div class="step-item ${statusClass}">
        <div class="step-dot"></div>
        <span>${p.replace(/_/g, ' ')}</span>
      </div>
    `;
  }).join('');
}

function renderHypotheses() {
  if (!hypothesesContainer) return;
  const hypotheses = incidentState.hypotheses || [];

  if (hypotheses.length === 0) {
    hypothesesContainer.innerHTML = `<div style="color: var(--text-muted); font-size: 12px;">Hypotheses will be generated during HYPOTHESIS_GENERATION phase.</div>`;
    return;
  }

  hypothesesContainer.innerHTML = hypotheses.map(h => {
    const isVerified = h.status === "VERIFIED";
    const isFalsified = h.status === "FALSIFIED";
    const cardClass = isVerified ? "verified" : (isFalsified ? "falsified" : "investigating");

    return `
      <div class="card hypothesis-card ${cardClass}">
        <div style="display: flex; justify-content: space-between; align-items: flex-start;">
          <strong style="font-size: 13px;">${h.title}</strong>
          <span class="badge ${isVerified ? 'badge-success' : (isFalsified ? 'badge-critical' : 'badge-info')}">${h.status}</span>
        </div>
        <div style="font-size: 12px; color: var(--text-secondary);">${h.description}</div>
        
        <div style="display: flex; gap: 8px; font-size: 11px; margin-top: 4px;">
          <span style="color: var(--accent-emerald);">Support: ${h.supporting_evidence_ids.length}</span>
          <span style="color: var(--accent-rose);">Contradictions: ${h.contradicting_evidence_ids.length}</span>
          <span style="color: var(--text-muted); font-family: var(--font-mono);">Score: ${h.score > 0 ? '+' : ''}${h.score}</span>
        </div>

        ${h.rejection_explanation ? `
          <div style="background: rgba(244, 63, 94, 0.1); border: 1px solid rgba(244, 63, 94, 0.2); padding: 8px; border-radius: 6px; font-size: 11px; color: #fda4af;">
            <strong>Critic Falsification:</strong> ${h.rejection_explanation}
          </div>
        ` : ''}
      </div>
    `;
  }).join('');
}

function renderTimeline() {
  if (!timelineContainer) return;
  const timeline = incidentState.timeline || [];

  if (timeline.length === 0) {
    timelineContainer.innerHTML = `<div style="color: var(--text-muted); font-size: 12px;">Timeline empty. Advance to COLLECTING_INITIAL_EVIDENCE.</div>`;
    return;
  }

  timelineContainer.innerHTML = timeline.map(evt => {
    let markerClass = "";
    if (evt.is_causal_candidate) markerClass = "causal";
    if (evt.is_misleading_red_herring) markerClass = "herring";

    return `
      <div class="timeline-node">
        <div class="timeline-marker ${markerClass}"></div>
        <div style="display: flex; justify-content: space-between; font-size: 11px; color: var(--text-muted); font-family: var(--font-mono);">
          <span>${evt.timestamp.slice(11, 19)}</span>
          <span>${evt.source}</span>
        </div>
        <div style="font-size: 12px; font-weight: 500; ${evt.is_misleading_red_herring ? 'color: #f59e0b;' : ''}">
          ${evt.is_misleading_red_herring ? '⚠️ [MISLEADING RED HERRING] ' : ''}${evt.description}
        </div>
      </div>
    `;
  }).join('');
}

function renderToolLogs() {
  if (!toolLogContainer) return;
  const logs = incidentState.tool_calls || [];

  document.getElementById('tool-count-badge').textContent = `${logs.length} calls`;

  toolLogContainer.innerHTML = logs.map(t => `
    <div class="tool-log-item">
      <div style="display: flex; justify-content: space-between;">
        <span style="color: var(--accent-cyan); font-weight: 600;">${t.tool_name}()</span>
        <span style="color: var(--text-muted);">${t.duration_ms}ms</span>
      </div>
      <div style="color: var(--text-secondary); word-break: break-all;">
        args: ${JSON.stringify(t.arguments)}
      </div>
      <div style="display: flex; justify-content: space-between; font-size: 10px;">
        <span class="badge ${t.status === 'COMPLETED' ? 'badge-success' : 'badge-critical'}">${t.status}</span>
        <span style="color: var(--text-muted);">${t.returned_evidence_ids.length} evidence items</span>
      </div>
    </div>
  `).join('');
}

function renderDecisionTrace() {
  if (!decisionTraceContainer) return;
  const traces = incidentState.decision_trace || [];

  decisionTraceContainer.innerHTML = traces.map(t => `
    <div style="font-family: var(--font-mono); font-size: 11px; padding: 6px 0; border-bottom: 1px solid var(--border-subtle); color: var(--text-secondary);">
      ${t}
    </div>
  `).join('');
  decisionTraceContainer.scrollTop = decisionTraceContainer.scrollHeight;
}

function renderApprovalSection() {
  if (!approvalCard) return;

  const prop = incidentState.remediation_proposal;
  const dec = incidentState.policy_decision;
  const isAwaiting = incidentState.current_phase === "AWAITING_APPROVAL";

  if (!prop) {
    approvalCard.style.display = 'none';
    return;
  }

  approvalCard.style.display = 'flex';
  approvalCard.innerHTML = `
    <div style="display: flex; justify-content: space-between; align-items: center;">
      <strong style="color: var(--accent-amber); font-size: 13px;">🛡️ Safety Policy: ${dec?.decision || 'REVIEW'}</strong>
      <span class="badge badge-warning">${prop.risk}</span>
    </div>
    <div style="font-size: 12px; color: var(--text-primary); margin: 6px 0;">
      <strong>Action:</strong> ${prop.description}
    </div>
    <div style="font-size: 11px; color: var(--text-muted); margin-bottom: 8px;">
      Reversibility: ${prop.reversibility} | Blast Radius: ${prop.blast_radius}
    </div>
    ${isAwaiting ? `
      <div style="display: flex; gap: 10px; margin-top: 6px;">
        <button id="btn-approve-action" class="btn btn-success" style="flex: 1;">
          ✓ Approve & Execute Remediation
        </button>
        <button id="btn-reject-action" class="btn btn-danger">
          ✕ Reject
        </button>
      </div>
    ` : `
      <div style="font-size: 12px; color: var(--accent-emerald);">
        Status: ${incidentState.execution_status} (Remediation Dispatched)
      </div>
    `}
  `;

  const btnApprove = document.getElementById('btn-approve-action');
  if (btnApprove) {
    btnApprove.addEventListener('click', async () => {
      btnApprove.disabled = true;
      btnApprove.textContent = "Executing Rollback & Replay...";
      try {
        const res = await fetch('/api/remediation/approve', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ approver: "incident_commander@corp.internal" })
        });
        const data = await res.json();
        incidentState = data.incident;
        renderAll();
      } catch (err) {
        alert("Execution error: " + err);
      }
    });
  }
}

function renderRecoverySection() {
  if (!recoveryCard) return;

  const rec = incidentState.recovery_result;
  if (!rec) {
    recoveryCard.style.display = 'none';
    return;
  }

  recoveryCard.style.display = 'flex';
  recoveryCard.innerHTML = `
    <div style="display: flex; justify-content: space-between; align-items: center;">
      <strong style="color: ${rec.all_checks_passed ? 'var(--accent-emerald)' : 'var(--accent-rose)'}; font-size: 13px;">
        ${rec.all_checks_passed ? '✅ Recovery Verified in Simulator' : '❌ Recovery Checks Failed'}
      </strong>
      <span class="badge ${rec.all_checks_passed ? 'badge-success' : 'badge-critical'}">
        ${rec.all_checks_passed ? 'ALL CHECKS PASSED' : 'CHECK FAILED'}
      </span>
    </div>
    <div style="font-size: 12px; margin: 6px 0; color: var(--text-primary);">
      ${rec.summary}
    </div>
    <div style="display: flex; flex-direction: column; gap: 6px;">
      ${rec.checks.map(c => `
        <div style="background: rgba(0,0,0,0.3); padding: 8px; border-radius: 6px; font-size: 11px; display: flex; justify-content: space-between; border-left: 3px solid ${c.passed ? 'var(--accent-emerald)' : 'var(--accent-rose)'};">
          <span>${c.check_name} (${c.target})</span>
          <strong>${c.actual_recovered_count}/${c.expected_recovered_count} recovered</strong>
        </div>
      `).join('')}
    </div>
    ${incidentState.postmortem ? `
      <button id="btn-view-postmortem" class="btn btn-secondary" style="margin-top: 8px;">
        📄 View Incident Postmortem
      </button>
    ` : ''}
  `;

  const btnViewPm = document.getElementById('btn-view-postmortem');
  if (btnViewPm) {
    btnViewPm.addEventListener('click', showPostmortem);
  }
}

function showPostmortem() {
  const pm = incidentState?.postmortem;
  if (!pm) return;

  document.getElementById('postmortem-content').innerHTML = `
    <h2 style="color: var(--accent-cyan); margin-bottom: 8px;">${pm.title}</h2>
    <div style="color: var(--text-muted); margin-bottom: 16px;">Incident ID: ${pm.incident_id} | Severity: ${pm.severity}</div>
    
    <h3 style="color: #fff; margin-top: 12px;">Root Cause</h3>
    <p style="color: var(--text-secondary);">${pm.root_cause}</p>

    <h3 style="color: #fff; margin-top: 12px;">Remediation & Recovery</h3>
    <p style="color: var(--text-secondary);">${pm.remediation_summary}</p>

    <h3 style="color: #fff; margin-top: 12px;">Preventive Recommendations</h3>
    <ul style="padding-left: 20px; color: var(--text-secondary);">
      ${pm.preventive_recommendations.map(r => `<li>${r}</li>`).join('')}
    </ul>
  `;
  postmortemModal.classList.add('open');
}

document.getElementById('btn-close-pm')?.addEventListener('click', () => {
  postmortemModal.classList.remove('open');
});

// Canvas Evidence Graph Implementation
function initEvidenceGraph() {
  const canvas = document.getElementById('evidence-graph-canvas');
  if (!canvas) return;

  canvas.addEventListener('click', (e) => {
    const rect = canvas.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const y = e.clientY - rect.top;

    // Check if clicked near an evidence node
    const records = Object.values(incidentState?.evidence_records || {});
    records.forEach((rec, idx) => {
      const nodeX = 40 + (idx % 6) * 75;
      const nodeY = 40 + Math.floor(idx / 6) * 65;
      const dist = Math.hypot(x - nodeX, y - nodeY);
      if (dist < 18) {
        showEvidenceDetails(rec);
      }
    });
  });
}

function drawEvidenceGraph() {
  const canvas = document.getElementById('evidence-graph-canvas');
  if (!canvas) return;
  const ctx = canvas.getContext('2d');
  
  canvas.width = canvas.parentElement.clientWidth - 32;
  canvas.height = 240;

  ctx.clearRect(0, 0, canvas.width, canvas.height);

  const records = Object.values(incidentState?.evidence_records || {});
  if (records.length === 0) {
    ctx.fillStyle = '#6b7280';
    ctx.font = '12px Inter';
    ctx.fillText('Evidence graph awaits tool query data...', 20, 120);
    return;
  }

  // Draw nodes
  records.forEach((rec, idx) => {
    const x = 40 + (idx % 6) * 75;
    const y = 40 + Math.floor(idx / 6) * 65;

    // Color based on source or tags
    let color = '#38bdf8'; // blue default
    if (rec.relevance_tags.includes('conflict') || rec.relevance_tags.includes('code_diff')) {
      color = '#10b981'; // emerald supporting
    } else if (rec.relevance_tags.includes('ALERT') || rec.summary.includes('HIGH CPU')) {
      color = '#f59e0b'; // amber red-herring/alert
    }

    // Node glow
    ctx.beginPath();
    ctx.arc(x, y, 14, 0, Math.PI * 2);
    ctx.fillStyle = color;
    ctx.shadowColor = color;
    ctx.shadowBlur = 10;
    ctx.fill();
    ctx.shadowBlur = 0;

    // Label
    ctx.fillStyle = '#fff';
    ctx.font = '9px monospace';
    ctx.textAlign = 'center';
    ctx.fillText(rec.source_tool.slice(0, 8), x, y + 26);
  });
}

function showEvidenceDetails(record) {
  document.getElementById('evidence-details-content').innerHTML = `
    <h3 style="color: var(--accent-cyan); margin-bottom: 8px;">Evidence Record: ${record.id}</h3>
    <div style="color: var(--text-muted); margin-bottom: 12px;">Tool: ${record.source_tool} | Timestamp: ${record.timestamp} | Reliability: ${record.reliability}</div>
    <div style="font-weight: 600; margin-bottom: 12px; color: #fff;">${record.summary}</div>
    <div style="background: #090d16; padding: 12px; border-radius: 8px; border: 1px solid var(--border-subtle); overflow-x: auto;">
      <pre>${JSON.stringify(record.data, null, 2)}</pre>
    </div>
  `;
  evidenceModal.classList.add('open');
}

document.getElementById('btn-close-ev')?.addEventListener('click', () => {
  evidenceModal.classList.remove('open');
});
