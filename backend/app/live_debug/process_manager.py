"""
Managed Process Manager for Live Lab Sample Microservice.
Controls process start, stop, restart, PID tracking, and log stream capture.
Ensures RootTrace remains alive if the managed sample application crashes.
"""
import subprocess
import threading
import sys
import os
import time
import signal
from typing import Optional, List, Dict, Any
from collections import deque
import logging

logger = logging.getLogger("roottrace.live_debug.process")

MAX_LOG_LINES = 1000


class LiveDebugProcessManager:
    """
    Manages the lifecycle of the live-lab child microservice.
    """

    def __init__(
        self,
        app_dir: Optional[str] = None,
        host: str = "127.0.0.1",
        port: int = 8001
    ):
        base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
        self.app_dir = app_dir or os.path.join(base_dir, "live-lab")
        self.host = host
        self.port = port
        self.process: Optional[subprocess.Popen] = None
        self.recent_logs: deque = deque(maxlen=MAX_LOG_LINES)
        self._log_thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()
        self.last_exit_code: Optional[int] = None
        self.start_time: Optional[float] = None

    def _find_pid_on_port(self) -> Optional[int]:
        """Discovers any PID currently listening on the target port."""
        try:
            import socket
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(0.3)
                if s.connect_ex((self.host, self.port)) != 0:
                    return None
            if sys.platform == "win32":
                out = subprocess.check_output(
                    f"netstat -ano | findstr :{self.port}",
                    shell=True,
                    text=True,
                    stderr=subprocess.DEVNULL
                )
                for line in out.strip().splitlines():
                    parts = line.split()
                    if len(parts) >= 5 and "LISTENING" in parts[3].upper():
                        return int(parts[4])
        except Exception:
            pass
        return None

    @property
    def is_running(self) -> bool:
        with self._lock:
            if self.process is not None and self.process.poll() is None:
                return True
            return self._find_pid_on_port() is not None

    @property
    def pid(self) -> Optional[int]:
        with self._lock:
            if self.process and self.process.poll() is None:
                return self.process.pid
            return self._find_pid_on_port()

    def start(self) -> Dict[str, Any]:
        """Starts the live-lab microservice in an independent child process."""
        with self._lock:
            if self.process and self.process.poll() is None:
                return {
                    "status": "ALREADY_RUNNING",
                    "pid": self.process.pid,
                    "host": self.host,
                    "port": self.port
                }

            existing_pid = self._find_pid_on_port()
            if existing_pid:
                return {
                    "status": "ALREADY_RUNNING",
                    "pid": existing_pid,
                    "host": self.host,
                    "port": self.port
                }

            # Find python executable (virtualenv or current interpreter)
            python_bin = sys.executable

            cmd = [
                python_bin,
                "-m",
                "uvicorn",
                "app.main:app",
                "--host",
                self.host,
                "--port",
                str(self.port)
            ]

            env = os.environ.copy()
            env["PYTHONPATH"] = self.app_dir

            logger.info(f"Starting live-lab process: {' '.join(cmd)} in {self.app_dir}")

            self.process = subprocess.Popen(
                cmd,
                cwd=self.app_dir,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                env=env
            )
            self.start_time = time.time()
            self.last_exit_code = None

            # Background thread to capture stdout/stderr safely into bounded buffer
            self._log_thread = threading.Thread(
                target=self._capture_output,
                args=(self.process,),
                daemon=True
            )
            self._log_thread.start()

            # Wait briefly for immediate startup crash detection
            time.sleep(0.5)
            poll = self.process.poll()
            if poll is not None:
                self.last_exit_code = poll
                return {
                    "status": "CRASHED_ON_STARTUP",
                    "exit_code": poll,
                    "pid": None
                }

            return {
                "status": "RUNNING",
                "pid": self.process.pid,
                "host": self.host,
                "port": self.port
            }

    def _capture_output(self, proc: subprocess.Popen):
        try:
            if proc.stdout:
                for line in iter(proc.stdout.readline, ""):
                    clean = line.rstrip("\r\n")
                    if clean:
                        self.recent_logs.append(clean)
        except Exception as e:
            logger.debug(f"Log capture terminated: {e}")
        finally:
            if proc.stdout:
                proc.stdout.close()
            with self._lock:
                self.last_exit_code = proc.poll()

    def stop(self) -> Dict[str, Any]:
        """Stops the live-lab microservice process cleanly."""
        with self._lock:
            if not self.process:
                pid = self._find_pid_on_port()
                if pid:
                    try:
                        os.kill(pid, signal.SIGTERM)
                        time.sleep(0.5)
                        if self._find_pid_on_port():
                            os.kill(pid, getattr(signal, "SIGKILL", signal.SIGTERM))
                    except Exception:
                        pass
                    return {"status": "STOPPED", "pid": pid}
                return {"status": "STOPPED", "pid": None}

            poll = self.process.poll()
            if poll is not None:
                self.last_exit_code = poll
                self.process = None
                return {"status": "ALREADY_STOPPED", "exit_code": poll}

            pid = self.process.pid
            logger.info(f"Terminating live-lab process PID {pid}")

            # Attempt graceful termination
            self.process.terminate()
            try:
                self.process.wait(timeout=3.0)
            except subprocess.TimeoutExpired:
                logger.warning(f"Process {pid} did not terminate gracefully; killing.")
                self.process.kill()
                self.process.wait(timeout=2.0)

            self.last_exit_code = self.process.poll()
            self.process = None
            return {
                "status": "STOPPED",
                "pid": pid,
                "exit_code": self.last_exit_code
            }

    def restart(self) -> Dict[str, Any]:
        """Restarts the live-lab microservice process."""
        self.stop()
        time.sleep(0.5)
        return self.start()

    def get_logs(self, limit: int = 100) -> List[str]:
        """Returns the most recent log lines from the process."""
        return list(self.recent_logs)[-limit:]

    def get_status(self) -> Dict[str, Any]:
        """Returns comprehensive process status telemetry."""
        with self._lock:
            running = (self.process is not None and self.process.poll() is None)
            pid = self.process.pid if running else None
            if not running:
                detected_pid = self._find_pid_on_port()
                if detected_pid:
                    running = True
                    pid = detected_pid
            uptime = time.time() - self.start_time if (running and self.start_time) else (1.0 if running else 0.0)
            return {
                "is_running": running,
                "pid": pid,
                "host": self.host,
                "port": self.port,
                "uptime_seconds": round(uptime, 1),
                "last_exit_code": self.last_exit_code if not running else None,
                "log_lines_buffered": len(self.recent_logs)
            }
