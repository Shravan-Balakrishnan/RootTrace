"""
Investigation Tools for RootTrace.
Real tool implementations querying the active simulated environment.
Validates inputs, formats structured EvidenceRecords, and maintains an auditable tool call log.
"""
from typing import Dict, Any, List, Optional
import datetime
import time
import uuid

from ..models.domain import EvidenceRecord, ToolCallRecord
from ..sandbox.engine import SimulatedEnvironment


class ToolRegistry:
    def __init__(self, sandbox: SimulatedEnvironment):
        self.sandbox = sandbox
        self.tool_logs: List[ToolCallRecord] = []
        self.evidence_store: Dict[str, EvidenceRecord] = {}

    def _record_call(self, tool_name: str, args: Dict[str, Any], evidence_ids: List[str], error: Optional[str] = None, duration_ms: float = 0.0) -> ToolCallRecord:
        record = ToolCallRecord(
            id=f"tool_call_{uuid.uuid4().hex[:8]}",
            tool_name=tool_name,
            arguments=args,
            status="FAILED" if error else "COMPLETED",
            timestamp=datetime.datetime.now(datetime.timezone.utc).isoformat(),
            returned_evidence_ids=evidence_ids,
            error_message=error,
            duration_ms=round(duration_ms, 2)
        )
        self.tool_logs.append(record)
        return record

    def query_logs(self, service: Optional[str] = None, level: Optional[str] = None, limit: int = 50) -> Dict[str, Any]:
        """Query application and infrastructure logs with service and severity filtering."""
        t0 = time.time()
        try:
            if limit < 1 or limit > 200:
                raise ValueError("Limit must be between 1 and 200.")
            logs = self.sandbox.query_logs(service=service, level=level, limit=limit)
            evidence_ids = []

            for item in logs:
                ev_id = f"ev_log_{uuid.uuid4().hex[:8]}"
                record = EvidenceRecord(
                    id=ev_id,
                    source_tool="query_logs",
                    timestamp=item.get("timestamp", datetime.datetime.now(datetime.timezone.utc).isoformat()),
                    source_ref=f"{item.get('service', 'unknown')}:log",
                    summary=f"[{item.get('level')}] {item.get('service')}: {item.get('message')}",
                    data=item,
                    reliability=0.95,
                    relevance_tags=[item.get("service", "service"), item.get("level", "INFO"), "log"]
                )
                self.evidence_store[ev_id] = record
                evidence_ids.append(ev_id)

            duration = (time.time() - t0) * 1000
            self._record_call("query_logs", {"service": service, "level": level, "limit": limit}, evidence_ids, duration_ms=duration)
            return {
                "success": True,
                "evidence_ids": evidence_ids,
                "evidence": [self.evidence_store[eid].model_dump() for eid in evidence_ids],
                "count": len(logs)
            }
        except Exception as e:
            self._record_call("query_logs", {"service": service, "level": level, "limit": limit}, [], error=str(e), duration_ms=(time.time() - t0) * 1000)
            return {"success": False, "error": str(e), "evidence_ids": []}

    def inspect_database(self, table: Optional[str] = None) -> Dict[str, Any]:
        """Inspect database tables, order statuses, row lock contention, and load metrics."""
        t0 = time.time()
        try:
            data = self.sandbox.inspect_database(table=table)
            ev_id = f"ev_db_{uuid.uuid4().hex[:8]}"
            record = EvidenceRecord(
                id=ev_id,
                source_tool="inspect_database",
                timestamp=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                source_ref=f"db:{table or 'all_tables'}",
                summary=f"Database inspection: status distribution {data.get('orders_status_distribution', {})}",
                data=data,
                reliability=0.98,
                relevance_tags=["database", "orders", "table_inspection"]
            )
            self.evidence_store[ev_id] = record
            duration = (time.time() - t0) * 1000
            self._record_call("inspect_database", {"table": table}, [ev_id], duration_ms=duration)
            return {
                "success": True,
                "evidence_ids": [ev_id],
                "evidence": [record.model_dump()],
                "data": data
            }
        except Exception as e:
            self._record_call("inspect_database", {"table": table}, [], error=str(e), duration_ms=(time.time() - t0) * 1000)
            return {"success": False, "error": str(e), "evidence_ids": []}

    def get_payment_status(self, order_id: Optional[str] = None) -> Dict[str, Any]:
        """Fetch payment transaction status from the payment gateway records."""
        t0 = time.time()
        try:
            records = self.sandbox.get_payment_status(order_id=order_id)
            evidence_ids = []
            for p in records:
                ev_id = f"ev_pay_{uuid.uuid4().hex[:8]}"
                rec = EvidenceRecord(
                    id=ev_id,
                    source_tool="get_payment_status",
                    timestamp=p.get("authorized_at") or datetime.datetime.now(datetime.timezone.utc).isoformat(),
                    source_ref=f"gateway:{p.get('payment_id')}",
                    summary=f"Payment for {p.get('order_id')}: status={p.get('status')} amount={p.get('amount')}",
                    data=p,
                    reliability=0.99,
                    relevance_tags=["payment", p.get("status", "status")]
                )
                self.evidence_store[ev_id] = rec
                evidence_ids.append(ev_id)

            duration = (time.time() - t0) * 1000
            self._record_call("get_payment_status", {"order_id": order_id}, evidence_ids, duration_ms=duration)
            return {
                "success": True,
                "evidence_ids": evidence_ids,
                "evidence": [self.evidence_store[eid].model_dump() for eid in evidence_ids],
                "count": len(records)
            }
        except Exception as e:
            self._record_call("get_payment_status", {"order_id": order_id}, [], error=str(e), duration_ms=(time.time() - t0) * 1000)
            return {"success": False, "error": str(e), "evidence_ids": []}

    def get_metrics(self, service: Optional[str] = None) -> Dict[str, Any]:
        """Fetch CPU, error rate, latency, and connection metrics for services."""
        t0 = time.time()
        try:
            metrics_data = self.sandbox.get_metrics(service=service)
            ev_id = f"ev_metric_{uuid.uuid4().hex[:8]}"
            rec = EvidenceRecord(
                id=ev_id,
                source_tool="get_metrics",
                timestamp=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                source_ref=f"telemetry:{service or 'all_services'}",
                summary=f"Metrics snapshot for {service or 'all_services'}",
                data=metrics_data,
                reliability=0.95,
                relevance_tags=["metrics", "telemetry", service or "cluster"]
            )
            self.evidence_store[ev_id] = rec
            duration = (time.time() - t0) * 1000
            self._record_call("get_metrics", {"service": service}, [ev_id], duration_ms=duration)
            return {
                "success": True,
                "evidence_ids": [ev_id],
                "evidence": [rec.model_dump()],
                "metrics": metrics_data
            }
        except Exception as e:
            self._record_call("get_metrics", {"service": service}, [], error=str(e), duration_ms=(time.time() - t0) * 1000)
            return {"success": False, "error": str(e), "evidence_ids": []}

    def get_trace(self, trace_id: Optional[str] = None) -> Dict[str, Any]:
        """Inspect distributed trace spans showing inter-service calls and timing."""
        t0 = time.time()
        try:
            traces = self.sandbox.get_trace(trace_id=trace_id)
            evidence_ids = []
            for t in traces:
                ev_id = f"ev_trace_{uuid.uuid4().hex[:8]}"
                rec = EvidenceRecord(
                    id=ev_id,
                    source_tool="get_trace",
                    timestamp=t.get("timestamp", datetime.datetime.now(datetime.timezone.utc).isoformat()),
                    source_ref=f"trace:{t.get('trace_id')}",
                    summary=f"Trace {t.get('trace_id')} ({t.get('endpoint')}): {len(t.get('spans', []))} spans",
                    data=t,
                    reliability=0.97,
                    relevance_tags=["trace", t.get("root_service", "service")]
                )
                self.evidence_store[ev_id] = rec
                evidence_ids.append(ev_id)

            duration = (time.time() - t0) * 1000
            self._record_call("get_trace", {"trace_id": trace_id}, evidence_ids, duration_ms=duration)
            return {
                "success": True,
                "evidence_ids": evidence_ids,
                "evidence": [self.evidence_store[eid].model_dump() for eid in evidence_ids],
                "count": len(traces)
            }
        except Exception as e:
            self._record_call("get_trace", {"trace_id": trace_id}, [], error=str(e), duration_ms=(time.time() - t0) * 1000)
            return {"success": False, "error": str(e), "evidence_ids": []}

    def check_deployments(self, service: Optional[str] = None) -> Dict[str, Any]:
        """Check active and past deployments, container versions, and release times."""
        t0 = time.time()
        try:
            deploys = self.sandbox.check_deployments(service=service)
            ev_id = f"ev_dep_{uuid.uuid4().hex[:8]}"
            rec = EvidenceRecord(
                id=ev_id,
                source_tool="check_deployments",
                timestamp=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                source_ref=f"deployments:{service or 'all'}",
                summary=f"Found {len(deploys)} deployment records for {service or 'all services'}",
                data={"deployments": deploys},
                reliability=0.99,
                relevance_tags=["deployment", "ci_cd"]
            )
            self.evidence_store[ev_id] = rec
            duration = (time.time() - t0) * 1000
            self._record_call("check_deployments", {"service": service}, [ev_id], duration_ms=duration)
            return {
                "success": True,
                "evidence_ids": [ev_id],
                "evidence": [rec.model_dump()],
                "deployments": deploys
            }
        except Exception as e:
            self._record_call("check_deployments", {"service": service}, [], error=str(e), duration_ms=(time.time() - t0) * 1000)
            return {"success": False, "error": str(e), "evidence_ids": []}

    def get_git_changes(self, repo: Optional[str] = None) -> Dict[str, Any]:
        """Inspect recent git commits and code diffs across repositories."""
        t0 = time.time()
        try:
            commits = self.sandbox.get_git_changes(repo=repo)
            evidence_ids = []
            for c in commits:
                ev_id = f"ev_git_{uuid.uuid4().hex[:8]}"
                rec = EvidenceRecord(
                    id=ev_id,
                    source_tool="get_git_changes",
                    timestamp=c.get("committed_at", datetime.datetime.now(datetime.timezone.utc).isoformat()),
                    source_ref=f"git:{c.get('repo')}:{c.get('commit_sha')}",
                    summary=f"Git commit {c.get('commit_sha')} in {c.get('repo')}: {c.get('message')}",
                    data=c,
                    reliability=0.99,
                    relevance_tags=["git", c.get("repo", "repo"), "code_diff"]
                )
                self.evidence_store[ev_id] = rec
                evidence_ids.append(ev_id)

            duration = (time.time() - t0) * 1000
            self._record_call("get_git_changes", {"repo": repo}, evidence_ids, duration_ms=duration)
            return {
                "success": True,
                "evidence_ids": evidence_ids,
                "evidence": [self.evidence_store[eid].model_dump() for eid in evidence_ids],
                "count": len(commits)
            }
        except Exception as e:
            self._record_call("get_git_changes", {"repo": repo}, [], error=str(e), duration_ms=(time.time() - t0) * 1000)
            return {"success": False, "error": str(e), "evidence_ids": []}

    def get_service_topology(self) -> Dict[str, Any]:
        """Inspect microservice architecture, dependencies, and communication channels."""
        t0 = time.time()
        try:
            topo = self.sandbox.get_service_topology()
            ev_id = f"ev_topo_{uuid.uuid4().hex[:8]}"
            rec = EvidenceRecord(
                id=ev_id,
                source_tool="get_service_topology",
                timestamp=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                source_ref="service_mesh:topology",
                summary=f"Topology: {len(topo.get('services', []))} services, {len(topo.get('dependencies', []))} connections",
                data=topo,
                reliability=0.95,
                relevance_tags=["topology", "architecture"]
            )
            self.evidence_store[ev_id] = rec
            duration = (time.time() - t0) * 1000
            self._record_call("get_service_topology", {}, [ev_id], duration_ms=duration)
            return {
                "success": True,
                "evidence_ids": [ev_id],
                "evidence": [rec.model_dump()],
                "topology": topo
            }
        except Exception as e:
            self._record_call("get_service_topology", {}, [], error=str(e), duration_ms=(time.time() - t0) * 1000)
            return {"success": False, "error": str(e), "evidence_ids": []}

    def search_historical_incidents(self, query: Optional[str] = None) -> Dict[str, Any]:
        """Search past resolved postmortems and incident memory for relevant patterns."""
        t0 = time.time()
        try:
            results = self.sandbox.search_historical_incidents(query=query)
            evidence_ids = []
            for inc in results:
                ev_id = f"ev_hist_{uuid.uuid4().hex[:8]}"
                rec = EvidenceRecord(
                    id=ev_id,
                    source_tool="search_historical_incidents",
                    timestamp=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                    source_ref=f"incident_memory:{inc.get('incident_id')}",
                    summary=f"Historical Incident {inc.get('incident_id')}: {inc.get('title')}",
                    data=inc,
                    reliability=0.88,
                    relevance_tags=["historical_memory", "lessons_learned"]
                )
                self.evidence_store[ev_id] = rec
                evidence_ids.append(ev_id)

            duration = (time.time() - t0) * 1000
            self._record_call("search_historical_incidents", {"query": query}, evidence_ids, duration_ms=duration)
            return {
                "success": True,
                "evidence_ids": evidence_ids,
                "evidence": [self.evidence_store[eid].model_dump() for eid in evidence_ids],
                "count": len(results)
            }
        except Exception as e:
            self._record_call("search_historical_incidents", {"query": query}, [], error=str(e), duration_ms=(time.time() - t0) * 1000)
            return {"success": False, "error": str(e), "evidence_ids": []}
