"""
Health Monitor for Live Lab Microservice.
Performs real HTTP health checks, latency measurement, and failure detection.
"""
import urllib.request
import urllib.error
import json
import time
from typing import Dict, Any, Optional
from pydantic import BaseModel


class HealthStatus(BaseModel):
    is_healthy: bool
    status_label: str  # "HEALTHY", "DEGRADED", "UNHEALTHY", "OFFLINE"
    http_status: Optional[int] = None
    latency_ms: Optional[float] = None
    data: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    timestamp: float


class HealthMonitor:
    def __init__(self, host: str = "127.0.0.1", port: int = 8001, timeout: float = 2.0):
        self.host = host
        self.port = port
        self.timeout = timeout

    @property
    def base_url(self) -> str:
        return f"http://{self.host}:{self.port}"

    def check_health(self) -> HealthStatus:
        """Probes the /health endpoint and measures response latency."""
        url = f"{self.base_url}/health"
        start = time.time()
        req = urllib.request.Request(url, headers={"User-Agent": "RootTrace-HealthMonitor/1.0"})

        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                latency = round((time.time() - start) * 1000, 2)
                code = resp.getcode()
                raw_body = resp.read().decode("utf-8")
                try:
                    body = json.loads(raw_body)
                except Exception:
                    body = {"raw": raw_body}

                is_ok = code == 200 and body.get("status") == "ok"
                return HealthStatus(
                    is_healthy=is_ok,
                    status_label="HEALTHY" if is_ok else "DEGRADED",
                    http_status=code,
                    latency_ms=latency,
                    data=body,
                    timestamp=time.time()
                )
        except urllib.error.HTTPError as e:
            latency = round((time.time() - start) * 1000, 2)
            return HealthStatus(
                is_healthy=False,
                status_label="SERVER_ERROR",
                http_status=e.code,
                latency_ms=latency,
                error_message=f"HTTP {e.code}: {e.reason}",
                timestamp=time.time()
            )
        except urllib.error.URLError as e:
            latency = round((time.time() - start) * 1000, 2)
            reason = str(e.reason)
            return HealthStatus(
                is_healthy=False,
                status_label="OFFLINE",
                latency_ms=latency,
                error_message=f"Connection failed: {reason}",
                timestamp=time.time()
            )
        except Exception as e:
            latency = round((time.time() - start) * 1000, 2)
            return HealthStatus(
                is_healthy=False,
                status_label="UNHEALTHY",
                latency_ms=latency,
                error_message=str(e),
                timestamp=time.time()
            )
