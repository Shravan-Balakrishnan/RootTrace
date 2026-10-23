"""
Simulated environment fixtures and scenarios for RootTrace.
Provides realistic, timestamped logs, metrics, traces, database records,
git diffs, and deployment records with causal connections and red herrings.
"""
from typing import Dict, Any, List
import copy


SCENARIO_CALLBACK_RACE = {
    "scenario_id": "callback_race",
    "title": "Payment Succeeded but Orders Marked FAILED (Concurrent Webhooks)",
    "description": "High rate of orders marked FAILED immediately following payment confirmation. Database CPU alarms firing.",
    "severity": "CRITICAL",
    "affected_services": ["order-service", "payment-service", "orders-db"],
    "created_at": "2026-10-23T14:15:00Z",
    "initial_observation": {
        "alert_name": "OrderStateInconsistencySpike",
        "service": "order-service",
        "metric": "failed_orders_rate",
        "current_value": "17.4%",
        "threshold": "1.0%",
        "summary": "17 orders marked FAILED in the last 15 minutes despite payment gateway reporting SUCCESS."
    },
    "deployments": [
        {
            "id": "dep_091",
            "service": "order-service",
            "version": "v1.2.4-order-sync",
            "deployed_at": "2026-10-23T13:50:00Z",
            "deployed_by": "ci-runner@prod",
            "commit_sha": "a7b38f2",
            "status": "ACTIVE",
            "change_summary": "Optimize webhook latency by removing Redis distributed lock on order status updates"
        },
        {
            "id": "dep_088",
            "service": "order-service",
            "version": "v1.2.3",
            "deployed_at": "2026-10-20T10:00:00Z",
            "deployed_by": "ci-runner@prod",
            "commit_sha": "f12c499",
            "status": "PREVIOUS_STABLE",
            "change_summary": "Standard release with Redlock distributed mutex on order mutations"
        },
        {
            "id": "dep_085",
            "service": "payment-service",
            "version": "v2.0.1",
            "deployed_at": "2026-10-22T08:30:00Z",
            "deployed_by": "ci-runner@prod",
            "commit_sha": "e99120b",
            "status": "ACTIVE",
            "change_summary": "Webhook retry backoff tuning"
        }
    ],
    "git_changes": [
        {
            "commit_sha": "a7b38f2",
            "repo": "order-service",
            "author": "alex.dev@internal",
            "committed_at": "2026-10-23T13:42:00Z",
            "message": "perf(order-webhook): remove Redis lock to reduce p99 latency",
            "diff": """
--- a/services/order/webhook_handler.py
+++ b/services/order/webhook_handler.py
@@ -34,10 +34,6 @@ async def handle_payment_webhook(order_id: str, status: str):
-    # Lock order to prevent concurrent duplicate transitions
-    async with redis_lock(f"order_lock:{order_id}", timeout=5):
-        order = await db.get_order_for_update(order_id)
-        return await apply_state_transition(order, status)
+    # Latency optimization: allow direct concurrent async processing without lock
+    order = await db.get_order(order_id)
+    return await apply_state_transition(order, status)
"""
        }
    ],
    "orders": [
        {"order_id": f"ORD-2026-{1000 + i}", "customer_id": f"CUST-{800 + i}", "amount": 89.50 + i * 10, "status": "FAILED", "payment_status": "SUCCESS", "error_code": "ERR_STATE_CONFLICT", "updated_at": f"2026-10-23T14:02:{10 + i % 40:02d}Z"}
        for i in range(17)
    ],
    "payment_records": [
        {"payment_id": f"PAY-{5000 + i}", "order_id": f"ORD-2026-{1000 + i}", "gateway": "Stripe", "status": "SUCCESS", "amount": 89.50 + i * 10, "charge_id": f"ch_mock_{9000 + i}", "authorized_at": f"2026-10-23T14:01:{i % 30:02d}Z"}
        for i in range(17)
    ],
    "logs": [
        {"timestamp": "2026-10-23T13:50:00Z", "service": "order-service", "level": "INFO", "message": "Deployment v1.2.4-order-sync rollout complete (pod replicas: 4/4)."},
        {"timestamp": "2026-10-23T14:01:05Z", "service": "payment-service", "level": "INFO", "message": "Gateway webhook sent: event=charge.succeeded order_id=ORD-2026-1000 try=1"},
        {"timestamp": "2026-10-23T14:01:05Z", "service": "payment-service", "level": "INFO", "message": "Gateway webhook duplicate delivered: event=payment.authorized order_id=ORD-2026-1000 try=1"},
        {"timestamp": "2026-10-23T14:01:05.102Z", "service": "order-service", "level": "INFO", "message": "Received webhook event=charge.succeeded for order_id=ORD-2026-1000 thread=async-worker-1"},
        {"timestamp": "2026-10-23T14:01:05.114Z", "service": "order-service", "level": "INFO", "message": "Received webhook event=payment.authorized for order_id=ORD-2026-1000 thread=async-worker-4"},
        {"timestamp": "2026-10-23T14:01:05.148Z", "service": "order-service", "level": "ERROR", "message": "Concurrent state transition conflict detected for order_id=ORD-2026-1000: attempted transition to 'CONFIRMED' from dirty state 'PROCESSING'. Fallback transitioning to FAILED."},
        {"timestamp": "2026-10-23T14:01:05.155Z", "service": "order-service", "level": "ERROR", "message": "Order ORD-2026-1000 transitioned to FAILED: code=ERR_STATE_CONFLICT"},
        {"timestamp": "2026-10-23T14:02:11.200Z", "service": "order-service", "level": "ERROR", "message": "Concurrent state transition conflict detected for order_id=ORD-2026-1001: attempted transition to 'CONFIRMED' from dirty state. Fallback transitioning to FAILED."},
        {"timestamp": "2026-10-23T14:03:00Z", "service": "orders-db", "level": "WARN", "message": "Row lock contention index check: Deadlock count=0, optimistic lock check conflicts=17."},
        # Misleading Red Herring: DB CPU Spikes 6 minutes AFTER failures started
        {"timestamp": "2026-10-23T14:07:30Z", "service": "orders-db", "level": "WARN", "message": "High CPU utilization detected on orders-db-replica: 88.4% (internal health check ping)"},
        {"timestamp": "2026-10-23T14:08:00Z", "service": "monitoring", "level": "ALERT", "message": "Alert triggered: DB_HIGH_CPU on orders-db-replica (threshold > 80%)"},
        {"timestamp": "2026-10-23T14:10:00Z", "service": "order-service", "level": "WARN", "message": "Retry queue accumulating 17 failed orders awaiting dead-letter replay."}
    ],
    "metrics": {
        "order-service": {
            "error_rate_percent": {"13:45": 0.05, "13:55": 0.08, "14:00": 0.1, "14:05": 17.4, "14:10": 17.2, "14:15": 17.5},
            "p99_latency_ms": {"13:45": 120, "13:55": 42, "14:00": 45, "14:05": 65, "14:10": 68, "14:15": 70},
            "active_connections": {"13:45": 45, "14:00": 48, "14:15": 52}
        },
        "orders-db": {
            "cpu_percent": {"13:45": 22.1, "13:55": 24.0, "14:00": 25.2, "14:05": 31.0, "14:07": 88.4, "14:10": 85.0, "14:15": 82.3},
            "active_transactions": {"13:45": 12, "14:00": 15, "14:05": 22, "14:15": 24},
            "disk_io_percent": {"13:45": 14.0, "14:00": 15.5, "14:15": 18.2}
        },
        "payment-service": {
            "gateway_success_rate": {"13:45": 99.9, "14:00": 100.0, "14:05": 100.0, "14:15": 100.0},
            "p99_latency_ms": {"13:45": 210, "14:00": 205, "14:15": 212}
        }
    },
    "traces": [
        {
            "trace_id": "tr_cb_race_1000",
            "root_service": "order-service",
            "endpoint": "/webhooks/payments",
            "timestamp": "2026-10-23T14:01:05.102Z",
            "spans": [
                {"name": "HTTP POST /webhooks/payments", "service": "order-service", "duration_ms": 46, "status": "ERROR", "attributes": {"order_id": "ORD-2026-1000", "thread": "async-worker-1"}},
                {"name": "db.get_order", "service": "orders-db", "duration_ms": 4, "status": "OK", "attributes": {"order_id": "ORD-2026-1000", "state": "PROCESSING"}},
                {"name": "apply_state_transition", "service": "order-service", "duration_ms": 32, "status": "ERROR", "attributes": {"error": "Conflict: Concurrent mutation in flight without lock"}}
            ]
        },
        {
            "trace_id": "tr_cb_race_1000_peer",
            "root_service": "order-service",
            "endpoint": "/webhooks/payments",
            "timestamp": "2026-10-23T14:01:05.114Z",
            "spans": [
                {"name": "HTTP POST /webhooks/payments", "service": "order-service", "duration_ms": 41, "status": "ERROR", "attributes": {"order_id": "ORD-2026-1000", "thread": "async-worker-4"}},
                {"name": "db.get_order", "service": "orders-db", "duration_ms": 3, "status": "OK", "attributes": {"order_id": "ORD-2026-1000"}},
                {"name": "apply_state_transition", "service": "order-service", "duration_ms": 28, "status": "ERROR", "attributes": {"error": "StateConflict: status already changed to FAILED"}}
            ]
        }
    ],
    "service_topology": {
        "services": [
            {"name": "payment-service", "type": "backend", "health": "HEALTHY", "instances": 3},
            {"name": "order-service", "type": "backend", "health": "DEGRADED", "instances": 4},
            {"name": "orders-db", "type": "database", "health": "WARNING", "instances": 2},
            {"name": "redis-lock-cluster", "type": "cache", "health": "HEALTHY", "instances": 3}
        ],
        "dependencies": [
            {"from": "payment-service", "to": "order-service", "type": "http_webhook"},
            {"from": "order-service", "to": "orders-db", "type": "sql"},
            {"from": "order-service", "to": "redis-lock-cluster", "type": "redis_mutex (BYPASS IN v1.2.4)"}
        ]
    },
    "historical_incidents": [
        {
            "incident_id": "INC-2025-081",
            "title": "Inventory double-allocation under load",
            "root_cause": "Missing distributed lock during flash sale concurrency",
            "remediation": "Added Redlock around inventory mutation",
            "lessons": "Removing distributed locks to lower latency risks race conditions."
        },
        {
            "incident_id": "INC-2025-044",
            "title": "Postgres connection pool saturation",
            "root_cause": "Long-running reporting query starved web workers",
            "remediation": "Created read-replica and segregated analytical queries",
            "lessons": "High DB CPU can either be root cause or side effect."
        }
    ]
}


SCENARIO_DB_DEGRADATION = {
    "scenario_id": "db_degradation",
    "title": "Database Connection Pool Exhaustion Starving Web Workers",
    "description": "API Gateway reporting widespread 504 Gateway Timeouts across order creation and checkout endpoints.",
    "severity": "CRITICAL",
    "affected_services": ["orders-db", "order-service", "checkout-service"],
    "created_at": "2026-10-23T11:20:00Z",
    "initial_observation": {
        "alert_name": "PostgresPoolExhaustionAlert",
        "service": "orders-db",
        "metric": "waiting_connections",
        "current_value": "142",
        "threshold": "10",
        "summary": "142 client queries waiting for DB connections; pool saturation at 100%."
    },
    "deployments": [
        {
            "id": "dep_070",
            "service": "order-service",
            "version": "v1.2.3",
            "deployed_at": "2026-10-20T10:00:00Z",
            "deployed_by": "ci-runner@prod",
            "commit_sha": "f12c499",
            "status": "ACTIVE",
            "change_summary": "Stable release (no deploys in past 72h)"
        }
    ],
    "git_changes": [],
    "orders": [
        {"order_id": f"ORD-2026-{2000 + i}", "customer_id": f"CUST-{900 + i}", "amount": 120.0, "status": "PENDING_PAYMENT", "payment_status": "PENDING", "error_code": "DB_CONNECTION_TIMEOUT", "updated_at": "2026-10-23T11:15:00Z"}
        for i in range(8)
    ],
    "payment_records": [],
    "logs": [
        {"timestamp": "2026-10-23T11:05:00Z", "service": "orders-db", "level": "INFO", "message": "Cron job started: analytics_reconciliation_dump_v2"},
        {"timestamp": "2026-10-23T11:08:12Z", "service": "orders-db", "level": "WARN", "message": "Long-running query detected: pid=3912 client=analytics duration=492s query='SELECT * FROM orders o JOIN order_items oi ON o.id = oi.order_id WHERE o.created_at > ...' (holding table locks)"},
        {"timestamp": "2026-10-23T11:12:00Z", "service": "order-service", "level": "ERROR", "message": "Connection pool timeout: pool size=50 max_overflow=10 waiting=45 timeout=30.0s"},
        {"timestamp": "2026-10-23T11:14:22Z", "service": "order-service", "level": "ERROR", "message": "Failed to acquire DB connection for POST /api/orders after 30s"}
    ],
    "metrics": {
        "orders-db": {
            "active_connections": {"11:00": 20, "11:05": 35, "11:10": 60, "11:15": 60, "11:20": 60},
            "waiting_connection_requests": {"11:00": 0, "11:05": 2, "11:10": 45, "11:15": 98, "11:20": 142},
            "cpu_percent": {"11:00": 15.0, "11:05": 28.0, "11:10": 94.0, "11:15": 96.5, "11:20": 98.2}
        },
        "order-service": {
            "error_rate_percent": {"11:00": 0.0, "11:05": 0.5, "11:10": 12.0, "11:15": 44.0, "11:20": 68.5},
            "p99_latency_ms": {"11:00": 85, "11:05": 140, "11:10": 30000, "11:15": 30000, "11:20": 30000}
        }
    },
    "traces": [
        {
            "trace_id": "tr_db_timeout_2001",
            "root_service": "order-service",
            "endpoint": "/api/orders",
            "timestamp": "2026-10-23T11:15:00Z",
            "spans": [
                {"name": "HTTP POST /api/orders", "service": "order-service", "duration_ms": 30005, "status": "ERROR", "attributes": {"error": "TimeoutError: connection pool exhausted after 30000ms"}}
            ]
        }
    ],
    "service_topology": {
        "services": [
            {"name": "order-service", "type": "backend", "health": "DEGRADED", "instances": 4},
            {"name": "orders-db", "type": "database", "health": "CRITICAL", "instances": 1}
        ],
        "dependencies": [
            {"from": "order-service", "to": "orders-db", "type": "sql_pool"}
        ]
    },
    "historical_incidents": []
}


SCENARIO_PAYMENT_FAILURE = {
    "scenario_id": "payment_failure",
    "title": "Third-Party Payment Gateway Outage (HTTP 503)",
    "description": "All customer checkouts failing at payment authorization step. Gateway returning 503 Service Unavailable.",
    "severity": "HIGH",
    "affected_services": ["payment-service", "external-stripe-gateway"],
    "created_at": "2026-10-23T09:40:00Z",
    "initial_observation": {
        "alert_name": "GatewayFailureRateHigh",
        "service": "payment-service",
        "metric": "upstream_5xx_rate",
        "current_value": "99.2%",
        "threshold": "5.0%",
        "summary": "99.2% of calls to payment gateway returning HTTP 503 or TLS handshake timeout."
    },
    "deployments": [
        {
            "id": "dep_065",
            "service": "payment-service",
            "version": "v2.0.1",
            "deployed_at": "2026-10-22T08:30:00Z",
            "deployed_by": "ci-runner@prod",
            "commit_sha": "e99120b",
            "status": "ACTIVE",
            "change_summary": "Webhook retry tuning (stable for 25+ hours)"
        }
    ],
    "git_changes": [],
    "orders": [
        {"order_id": f"ORD-2026-{3000 + i}", "customer_id": f"CUST-{700 + i}", "amount": 65.0, "status": "FAILED", "payment_status": "GATEWAY_FAILED", "error_code": "ERR_GATEWAY_503", "updated_at": "2026-10-23T09:35:00Z"}
        for i in range(10)
    ],
    "payment_records": [
        {"payment_id": f"PAY-{7000 + i}", "order_id": f"ORD-2026-{3000 + i}", "gateway": "PrimaryStripe", "status": "FAILED", "amount": 65.0, "charge_id": None, "authorized_at": None}
        for i in range(10)
    ],
    "logs": [
        {"timestamp": "2026-10-23T09:31:00Z", "service": "payment-service", "level": "ERROR", "message": "Gateway request failed: POST https://api.stripe-mock.io/v1/charges returned HTTP 503 (Cloudflare Edge 503: Origin Host Unreachable)"},
        {"timestamp": "2026-10-23T09:32:15Z", "service": "payment-service", "level": "ERROR", "message": "Circuit breaker for PrimaryStripe open: 45 consecutive 5xx errors"},
        {"timestamp": "2026-10-23T09:33:00Z", "service": "payment-service", "level": "WARN", "message": "Secondary fallback gateway (AdyenBackup) available but auto-switch disabled by policy flag 'payment.auto_failover=false'"}
    ],
    "metrics": {
        "payment-service": {
            "gateway_5xx_rate": {"09:20": 0.0, "09:30": 8.0, "09:35": 99.2, "09:40": 99.8},
            "p99_latency_ms": {"09:20": 180, "09:30": 4500, "09:35": 10000, "09:40": 10000}
        },
        "orders-db": {
            "cpu_percent": {"09:20": 12.0, "09:30": 11.8, "09:35": 10.5, "09:40": 9.8}
        }
    },
    "traces": [
        {
            "trace_id": "tr_gateway_503_3001",
            "root_service": "payment-service",
            "endpoint": "/payments/charge",
            "timestamp": "2026-10-23T09:32:00Z",
            "spans": [
                {"name": "HTTP POST /payments/charge", "service": "payment-service", "duration_ms": 10012, "status": "ERROR", "attributes": {"upstream_error": "503 Service Unavailable", "gateway": "PrimaryStripe"}}
            ]
        }
    ],
    "service_topology": {
        "services": [
            {"name": "payment-service", "type": "backend", "health": "DEGRADED", "instances": 3},
            {"name": "external-stripe-gateway", "type": "external_api", "health": "UNAVAILABLE", "instances": 1},
            {"name": "external-adyen-backup", "type": "external_api", "health": "HEALTHY", "instances": 1}
        ],
        "dependencies": [
            {"from": "payment-service", "to": "external-stripe-gateway", "type": "https"},
            {"from": "payment-service", "to": "external-adyen-backup", "type": "https_standby"}
        ]
    },
    "historical_incidents": []
}

ALL_SCENARIOS = {
    "callback_race": SCENARIO_CALLBACK_RACE,
    "db_degradation": SCENARIO_DB_DEGRADATION,
    "payment_failure": SCENARIO_PAYMENT_FAILURE
}


def get_scenario_fixture(scenario_id: str) -> Dict[str, Any]:
    if scenario_id not in ALL_SCENARIOS:
        raise ValueError(f"Unknown scenario_id: {scenario_id}. Choose from: {list(ALL_SCENARIOS.keys())}")
    return copy.deepcopy(ALL_SCENARIOS[scenario_id])
