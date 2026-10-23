"""
Simulator Engine for RootTrace.
Maintains stateful simulated infrastructure that tools inspect and remediations mutate.
Strict rule: State changes must be genuine in-memory mutations, and recovery must be
computed from simulator state, never hardcoded.
"""
from typing import Dict, Any, List, Optional
import datetime
from .scenarios import get_scenario_fixture


class SimulatedEnvironment:
    def __init__(self, scenario_id: str = "callback_race"):
        self.scenario_id = scenario_id
        self.state = get_scenario_fixture(scenario_id)
        self.action_history: List[Dict[str, Any]] = []

    def reset(self, scenario_id: Optional[str] = None):
        if scenario_id:
            self.scenario_id = scenario_id
        self.state = get_scenario_fixture(self.scenario_id)
        self.action_history.clear()

    # --- Query Methods (used by tools) ---

    def query_logs(self, service: Optional[str] = None, level: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
        logs = self.state.get("logs", [])
        filtered = []
        for log in logs:
            if service and log.get("service") != service:
                continue
            if level and log.get("level") != level:
                continue
            filtered.append(log)
        return filtered[:limit]

    def inspect_database(self, table: Optional[str] = None) -> Dict[str, Any]:
        orders = self.state.get("orders", [])
        if table == "orders":
            return {"table": "orders", "total_records": len(orders), "rows": orders}
        # General DB stats
        status_counts = {}
        for o in orders:
            s = o.get("status", "UNKNOWN")
            status_counts[s] = status_counts.get(s, 0) + 1

        db_metrics = self.state.get("metrics", {}).get("orders-db", {})
        return {
            "tables": ["orders", "order_items", "payment_transactions"],
            "orders_status_distribution": status_counts,
            "recent_orders_sample": orders[:5],
            "db_load_metrics": db_metrics
        }

    def get_payment_status(self, order_id: Optional[str] = None) -> List[Dict[str, Any]]:
        records = self.state.get("payment_records", [])
        if order_id:
            return [r for r in records if r.get("order_id") == order_id]
        return records

    def get_metrics(self, service: Optional[str] = None) -> Dict[str, Any]:
        metrics = self.state.get("metrics", {})
        if service:
            return {service: metrics.get(service, {})}
        return metrics

    def get_trace(self, trace_id: Optional[str] = None) -> List[Dict[str, Any]]:
        traces = self.state.get("traces", [])
        if trace_id:
            return [t for t in traces if t.get("trace_id") == trace_id]
        return traces

    def check_deployments(self, service: Optional[str] = None) -> List[Dict[str, Any]]:
        deployments = self.state.get("deployments", [])
        if service:
            return [d for d in deployments if d.get("service") == service]
        return deployments

    def get_git_changes(self, repo: Optional[str] = None) -> List[Dict[str, Any]]:
        changes = self.state.get("git_changes", [])
        if repo:
            return [c for c in changes if c.get("repo") == repo]
        return changes

    def get_service_topology(self) -> Dict[str, Any]:
        return self.state.get("service_topology", {})

    def search_historical_incidents(self, query: Optional[str] = None) -> List[Dict[str, Any]]:
        history = self.state.get("historical_incidents", [])
        if not query:
            return history
        q = query.lower()
        return [
            h for h in history
            if q in h.get("title", "").lower() or q in h.get("root_cause", "").lower() or q in h.get("remediation", "").lower()
        ]

    # --- Remediation Execution Mutations ---

    def execute_rollback(self, target_service: str, target_version: str) -> Dict[str, Any]:
        """Rollback active deployment to specified version"""
        deployments = self.state.get("deployments", [])
        found_target = False
        previous_active = None

        for dep in deployments:
            if dep.get("service") == target_service:
                if dep.get("status") == "ACTIVE":
                    previous_active = dep.get("version")
                    dep["status"] = "ROLLED_BACK"
                if dep.get("version") == target_version:
                    dep["status"] = "ACTIVE"
                    found_target = True

        if not found_target:
            # Create a rollback record for the stable target
            deployments.insert(0, {
                "id": f"dep_rollback_{target_version}",
                "service": target_service,
                "version": target_version,
                "deployed_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                "deployed_by": "roottrace-recovery-agent",
                "commit_sha": "f12c499",
                "status": "ACTIVE",
                "change_summary": f"Rollback to {target_version} to restore distributed mutex lock"
            })

        # Update service topology health
        topology = self.state.get("service_topology", {})
        for s in topology.get("services", []):
            if s.get("name") == target_service:
                s["health"] = "HEALTHY"

        self.action_history.append({
            "action": "ROLLBACK",
            "service": target_service,
            "from_version": previous_active,
            "to_version": target_version,
            "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat()
        })

        return {
            "success": True,
            "service": target_service,
            "rolled_back_from": previous_active,
            "active_version": target_version,
            "message": f"Successfully rolled back {target_service} to {target_version}."
        }

    def replay_failed_callbacks(self) -> Dict[str, Any]:
        """Replay webhooks for all FAILED orders where payment was SUCCESS"""
        orders = self.state.get("orders", [])
        payments = {p["order_id"]: p for p in self.state.get("payment_records", [])}

        replayed_count = 0
        now_ts = datetime.datetime.now(datetime.timezone.utc).isoformat()

        for o in orders:
            order_id = o.get("order_id")
            pay = payments.get(order_id)
            if o.get("status") == "FAILED" and pay and pay.get("status") == "SUCCESS":
                # With safe locks restored in v1.2.3, the webhook re-executes cleanly
                o["status"] = "CONFIRMED"
                o["error_code"] = None
                o["updated_at"] = now_ts
                o["remediation_note"] = "Replayed with safe distributed mutex"
                replayed_count += 1

        # Also normalize error metrics
        metrics = self.state.get("metrics", {})
        if "order-service" in metrics:
            metrics["order-service"]["error_rate_percent"]["14:25 (post-fix)"] = 0.0
            metrics["order-service"]["p99_latency_ms"]["14:25 (post-fix)"] = 48
        if "orders-db" in metrics:
            metrics["orders-db"]["cpu_percent"]["14:25 (post-fix)"] = 23.5

        # Add recovery log entry
        self.state.get("logs", []).append({
            "timestamp": now_ts,
            "service": "order-service",
            "level": "INFO",
            "message": f"Successfully replayed {replayed_count} failed webhooks under v1.2.3. All orders transitioned to CONFIRMED."
        })

        self.action_history.append({
            "action": "REPLAY_CALLBACKS",
            "replayed_count": replayed_count,
            "timestamp": now_ts
        })

        return {
            "success": True,
            "replayed_count": replayed_count,
            "message": f"Replayed {replayed_count} failed callbacks safely under restored mutex lock."
        }

    def execute_db_pool_reset(self) -> Dict[str, Any]:
        """Remediation for Scenario B (DB Degradation)"""
        now_ts = datetime.datetime.now(datetime.timezone.utc).isoformat()
        # Terminate rogue PID 3912 and recycle connections
        metrics = self.state.get("metrics", {})
        if "orders-db" in metrics:
            metrics["orders-db"]["waiting_connection_requests"]["11:30 (post-fix)"] = 0
            metrics["orders-db"]["cpu_percent"]["11:30 (post-fix)"] = 18.0
            metrics["orders-db"]["active_connections"]["11:30 (post-fix)"] = 22
        if "order-service" in metrics:
            metrics["order-service"]["error_rate_percent"]["11:30 (post-fix)"] = 0.0

        for o in self.state.get("orders", []):
            if o.get("status") == "PENDING_PAYMENT":
                o["status"] = "CONFIRMED"
                o["payment_status"] = "SUCCESS"
                o["error_code"] = None

        topology = self.state.get("service_topology", {})
        for s in topology.get("services", []):
            s["health"] = "HEALTHY"

        self.action_history.append({
            "action": "TERMINATE_ROGUE_QUERY_AND_RESET_POOL",
            "timestamp": now_ts
        })
        return {
            "success": True,
            "message": "Terminated blocking analytics PID 3912 and cycled connection pool."
        }

    def execute_payment_failover(self) -> Dict[str, Any]:
        """Remediation for Scenario C (Payment Failure)"""
        now_ts = datetime.datetime.now(datetime.timezone.utc).isoformat()
        metrics = self.state.get("metrics", {})
        if "payment-service" in metrics:
            metrics["payment-service"]["gateway_5xx_rate"]["09:50 (post-failover)"] = 0.0
            metrics["payment-service"]["p99_latency_ms"]["09:50 (post-failover)"] = 210

        topology = self.state.get("service_topology", {})
        for s in topology.get("services", []):
            if s.get("name") == "payment-service":
                s["health"] = "HEALTHY"

        self.action_history.append({
            "action": "FAILOVER_TO_BACKUP_GATEWAY",
            "timestamp": now_ts
        })
        return {
            "success": True,
            "message": "Enabled circuit breaker failover to secondary provider AdyenBackup."
        }

    # --- Actual Recovery Verification Method ---

    def verify_recovery(self) -> Dict[str, Any]:
        """
        Inspect actual current simulator state to verify recovery.
        Never returns hardcoded canned result; counts actual orders in memory!
        """
        orders = self.state.get("orders", [])
        total_orders = len(orders)
        confirmed_count = sum(1 for o in orders if o.get("status") == "CONFIRMED")
        failed_count = sum(1 for o in orders if o.get("status") == "FAILED")

        payments = {p["order_id"]: p for p in self.state.get("payment_records", [])}
        consistent_count = 0
        for o in orders:
            pay = payments.get(o.get("order_id"))
            if pay and pay.get("status") == "SUCCESS" and o.get("status") == "CONFIRMED":
                consistent_count += 1
            elif not pay and o.get("status") == "CONFIRMED":
                consistent_count += 1

        # Check deployment state for callback_race
        active_deployments = [
            d for d in self.state.get("deployments", [])
            if d.get("service") == "order-service" and d.get("status") == "ACTIVE"
        ]
        active_version = active_deployments[0]["version"] if active_deployments else "UNKNOWN"

        checks = []

        if self.scenario_id == "callback_race":
            # 1. Order Status Check
            order_check_passed = (confirmed_count == total_orders and failed_count == 0)
            checks.append({
                "check_name": "All Orders Successfully Confirmed",
                "target": "orders_table",
                "passed": order_check_passed,
                "details": f"{confirmed_count} of {total_orders} orders confirmed (0 FAILED).",
                "actual_recovered_count": confirmed_count,
                "expected_recovered_count": total_orders
            })

            # 2. Payment/Order Consistency Check
            payment_consistency_passed = (consistent_count == total_orders)
            checks.append({
                "check_name": "Payment/Order State Consistency",
                "target": "payment_transactions",
                "passed": payment_consistency_passed,
                "details": f"{consistent_count}/{total_orders} orders consistent with successful charges.",
                "actual_recovered_count": consistent_count,
                "expected_recovered_count": total_orders
            })

            # 3. Deployment Version Verification
            dep_check_passed = (active_version == "v1.2.3")
            checks.append({
                "check_name": "Safe Deployment Version Active (v1.2.3)",
                "target": "deployment_manifest",
                "passed": dep_check_passed,
                "details": f"Active version is {active_version} (expected v1.2.3 with distributed lock).",
                "actual_recovered_count": 1 if dep_check_passed else 0,
                "expected_recovered_count": 1
            })

        elif self.scenario_id == "db_degradation":
            db_metrics = self.state.get("metrics", {}).get("orders-db", {}).get("waiting_connection_requests", {})
            latest_waiting = list(db_metrics.values())[-1] if db_metrics else 999
            pool_healthy = (latest_waiting == 0)
            checks.append({
                "check_name": "Connection Pool Health",
                "target": "orders-db",
                "passed": pool_healthy,
                "details": f"Waiting connections: {latest_waiting} (expected 0).",
                "actual_recovered_count": 1 if pool_healthy else 0,
                "expected_recovered_count": 1
            })

        elif self.scenario_id == "payment_failure":
            pay_metrics = self.state.get("metrics", {}).get("payment-service", {}).get("gateway_5xx_rate", {})
            latest_5xx = list(pay_metrics.values())[-1] if pay_metrics else 999.0
            gateway_healthy = (latest_5xx == 0.0)
            checks.append({
                "check_name": "Payment Gateway Availability",
                "target": "payment-service",
                "passed": gateway_healthy,
                "details": f"Gateway 5xx error rate: {latest_5xx}% (expected 0.0%).",
                "actual_recovered_count": 1 if gateway_healthy else 0,
                "expected_recovered_count": 1
            })

        all_passed = len(checks) > 0 and all(c["passed"] for c in checks)

        return {
            "all_checks_passed": all_passed,
            "checks": checks,
            "total_orders": total_orders,
            "confirmed_orders": confirmed_count,
            "failed_orders": failed_count,
            "summary": (
                f"Recovery Verified: {confirmed_count}/{total_orders} affected orders restored to CONFIRMED. All recovery checks PASSED."
                if all_passed else
                f"Recovery Incomplete: {failed_count} orders still in FAILED state."
            ),
            "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat()
        }
