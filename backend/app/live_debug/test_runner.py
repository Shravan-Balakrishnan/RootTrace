"""
Sandboxed Test Runner for Live Lab and Candidate Patch Workspaces.
Executes allowlisted pytest suites with strict execution timeouts and bounded output capture.
"""
import subprocess
import sys
import os
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field


class TestExecutionResult(BaseModel):
    all_passed: bool
    exit_code: int
    total_tests: int = 0
    passed_tests: int = 0
    failed_tests: int = 0
    error_summary: List[str] = Field(default_factory=list)
    raw_output: str
    duration_seconds: float = 0.0
    timed_out: bool = False


class LiveDebugTestRunner:
    """
    Executes allowlisted test suites against live-lab or isolated workspaces.
    """

    def __init__(self, timeout_seconds: float = 20.0):
        self.timeout_seconds = timeout_seconds

    def run_tests(
        self,
        target_dir: Optional[str] = None,
        test_path: Optional[str] = None
    ) -> TestExecutionResult:
        """
        Runs pytest against target_dir/tests or test_path.
        """
        import time
        base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
        resolved_dir = target_dir or os.path.join(base_dir, "live-lab")
        test_target = test_path or "tests"

        python_bin = sys.executable
        cmd = [
            python_bin,
            "-m",
            "pytest",
            "-v",
            test_target
        ]

        env = os.environ.copy()
        env["PYTHONPATH"] = resolved_dir

        start_time = time.time()
        try:
            res = subprocess.run(
                cmd,
                cwd=resolved_dir,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                timeout=self.timeout_seconds,
                env=env
            )
            duration = round(time.time() - start_time, 2)
            output = res.stdout or ""

            # Parse pytest summary
            passed = 0
            failed = 0
            total = 0
            error_lines = []

            for line in output.splitlines():
                if " PASSED" in line:
                    passed += 1
                elif " FAILED" in line:
                    failed += 1
                elif any(kw in line for kw in (
                    "E   ", "AssertionError", "ZeroDivisionError", "TypeError",
                    "SyntaxError", "IndentationError", "NameError", "ImportError",
                    "AttributeError", "ValueError", "ERROR collecting", "Error:", "FAILED"
                )):
                    error_lines.append(line.strip())

            total = passed + failed
            all_passed = (res.returncode == 0) and (failed == 0)
            if not all_passed and failed == 0:
                failed = 1
                total = max(total, 1)

            return TestExecutionResult(
                all_passed=all_passed,
                exit_code=res.returncode,
                total_tests=total,
                passed_tests=passed,
                failed_tests=failed,
                error_summary=error_lines[:10],
                raw_output=output[:10000],  # Bounded to 10KB
                duration_seconds=duration,
                timed_out=False
            )
        except subprocess.TimeoutExpired as e:
            duration = round(time.time() - start_time, 2)
            out = e.stdout if isinstance(e.stdout, str) else (e.stdout.decode("utf-8", errors="ignore") if e.stdout else "")
            return TestExecutionResult(
                all_passed=False,
                exit_code=-1,
                error_summary=[f"Test execution timed out after {self.timeout_seconds} seconds."],
                raw_output=out[:5000],
                duration_seconds=duration,
                timed_out=True
            )
        except Exception as e:
            duration = round(time.time() - start_time, 2)
            return TestExecutionResult(
                all_passed=False,
                exit_code=-2,
                error_summary=[f"Execution failed: {str(e)}"],
                raw_output=str(e),
                duration_seconds=duration,
                timed_out=False
            )
