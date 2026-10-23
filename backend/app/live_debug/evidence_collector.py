"""
Evidence Collector for Live Lab Incidents.
Aggregates real runtime evidence: process logs, tracebacks, health probe failures,
test assertion errors, git diffs, and source context.
Sanitizes all evidence before dispatch to the model.
"""
import os
import re
import datetime
import subprocess
from typing import Dict, List, Any, Optional
from pydantic import BaseModel, Field

from .process_manager import LiveDebugProcessManager
from .health_monitor import HealthMonitor, HealthStatus
from .test_runner import LiveDebugTestRunner, TestExecutionResult
from .evidence_sanitizer import EvidenceSanitizer, SanitizedEvidenceRecord, SanitizationSummary
from .log_intelligence import LogIntelligenceMiner, LogIntelligenceReport


class CollectedLiveEvidence(BaseModel):
    run_id: str
    observed_failure_type: str  # "PROCESS_CRASH", "HEALTH_CHECK_FAILED", "TEST_FAILURE", "NO_FAILURE"
    evidence_records: List[SanitizedEvidenceRecord] = Field(default_factory=list)
    sanitization_summary: SanitizationSummary
    is_failing: bool
    summary: str
    log_intelligence: Optional[LogIntelligenceReport] = None


class LiveEvidenceCollector:
    """
    Collects and sanitizes real failure evidence from the live-lab testbed.
    """

    def __init__(
        self,
        process_manager: LiveDebugProcessManager,
        health_monitor: HealthMonitor,
        test_runner: LiveDebugTestRunner,
        sanitizer: Optional[EvidenceSanitizer] = None
    ):
        self.process_manager = process_manager
        self.health_monitor = health_monitor
        self.test_runner = test_runner
        self.sanitizer = sanitizer or EvidenceSanitizer()

    def collect_all_evidence(self, run_id: str) -> CollectedLiveEvidence:
        """
        Executes health checks, inspects process logs, runs tests, and gathers git diff.
        Produces sanitized evidence records.
        """
        raw_items: List[Dict[str, Any]] = []
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        failure_detected = False
        failure_type = "NO_FAILURE"
        failure_descriptions = []

        # 1. Process Status Evidence
        proc_status = self.process_manager.get_status()
        raw_items.append({
            "id": f"ev_proc_{run_id[:6]}",
            "source_tool": "process_monitor",
            "timestamp": now,
            "source_ref": f"live-lab:pid:{proc_status.get('pid')}",
            "summary": f"Process running: {proc_status.get('is_running')}, exit code: {proc_status.get('last_exit_code')}",
            "data": proc_status
        })
        if not proc_status.get("is_running") and proc_status.get("last_exit_code") not in (None, 0):
            failure_detected = True
            failure_type = "PROCESS_CRASH"
            failure_descriptions.append(f"Process crashed with exit code {proc_status.get('last_exit_code')}")

        # 2. Health Check Probe Evidence
        health = self.health_monitor.check_health()
        raw_items.append({
            "id": f"ev_health_{run_id[:6]}",
            "source_tool": "health_probe",
            "timestamp": now,
            "source_ref": f"http://{self.health_monitor.host}:{self.health_monitor.port}/health",
            "summary": f"Health status: {health.status_label} (HTTP {health.http_status}), latency: {health.latency_ms}ms",
            "data": health.model_dump()
        })
        if not health.is_healthy and (proc_status.get("is_running") or proc_status.get("last_exit_code") not in (None, 0)):
            failure_detected = True
            if failure_type == "NO_FAILURE":
                failure_type = "HEALTH_CHECK_FAILED"
            failure_descriptions.append(f"Health probe failed: {health.error_message or health.status_label}")

        # 3. Recent Process Logs Evidence
        recent_logs = self.process_manager.get_logs(limit=80)
        traceback_lines = []
        is_in_tb = False
        for line in recent_logs:
            if "Traceback (most recent call last):" in line:
                is_in_tb = True
            if is_in_tb:
                traceback_lines.append(line)
            if is_in_tb and ("Error:" in line or "Exception:" in line):
                is_in_tb = False

        if recent_logs:
            raw_items.append({
                "id": f"ev_logs_{run_id[:6]}",
                "source_tool": "process_logs",
                "timestamp": now,
                "source_ref": "live-lab:stdout_stderr",
                "summary": f"Captured {len(recent_logs)} recent process log lines",
                "data": {
                    "lines": recent_logs[-50:],
                    "traceback": traceback_lines[-20:] if traceback_lines else None
                }
            })
            if traceback_lines:
                failure_detected = True
                if failure_type == "NO_FAILURE":
                    failure_type = "RUNTIME_EXCEPTION"
                failure_descriptions.append("Exception traceback detected in application process logs")

        # 3b. Log Intelligence & Template Mining (Drain3 / Fallback)
        log_intel_report: Optional[LogIntelligenceReport] = None
        if recent_logs:
            miner = LogIntelligenceMiner()
            log_intel_report = miner.mine_log_templates(recent_logs)
            top_templates_str = ", ".join(
                f"'{t.template_text}' (x{t.occurrence_count})" for t in log_intel_report.templates[:3]
            )
            raw_items.append({
                "id": f"ev_log_intel_{run_id[:6]}",
                "source_tool": "log_intelligence",
                "timestamp": now,
                "source_ref": f"{log_intel_report.implementation_used}:template_miner",
                "summary": f"Mined {log_intel_report.unique_templates_count} log template(s) via {log_intel_report.implementation_used}: {top_templates_str or 'No repeated templates'}",
                "data": log_intel_report.model_dump()
            })

        # 4. Test Execution Evidence
        test_res = self.test_runner.run_tests()
        raw_items.append({
            "id": f"ev_test_{run_id[:6]}",
            "source_tool": "regression_test_runner",
            "timestamp": now,
            "source_ref": "live-lab/tests/test_api.py",
            "summary": f"Tests all passed: {test_res.all_passed} ({test_res.passed_tests}/{test_res.total_tests} passed, {test_res.failed_tests} failed)",
            "data": test_res.model_dump()
        })
        if not test_res.all_passed:
            failure_detected = True
            if failure_type in ("NO_FAILURE", "HEALTH_CHECK_FAILED"):
                failure_type = "TEST_FAILURE"
            failure_descriptions.append(f"Regression tests failed ({test_res.failed_tests} failure(s))")

        # 5. Git Diff Evidence of live-lab
        git_diff = self._get_live_lab_git_diff()
        if git_diff:
            raw_items.append({
                "id": f"ev_diff_{run_id[:6]}",
                "source_tool": "git_inspector",
                "timestamp": now,
                "source_ref": "git:diff:live-lab",
                "summary": "Detected uncommitted modifications in live-lab source directory",
                "data": {"diff": git_diff}
            })

        # Sanitize all collected evidence
        sanitized_records, summary = self.sanitizer.sanitize_evidence_collection(raw_items)

        overall_summary = "Application is healthy." if not failure_detected else " | ".join(failure_descriptions)

        return CollectedLiveEvidence(
            run_id=run_id,
            observed_failure_type=failure_type,
            evidence_records=sanitized_records,
            sanitization_summary=summary,
            is_failing=failure_detected,
            summary=overall_summary,
            log_intelligence=log_intel_report
        )

    def _get_live_lab_git_diff(self) -> Optional[str]:
        """Captures local git diff for live-lab directory."""
        try:
            repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
            res = subprocess.run(
                ["git", "diff", "live-lab"],
                cwd=repo_root,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=5.0
            )
            out = res.stdout.strip()
            return out if out else None
        except Exception:
            return None
