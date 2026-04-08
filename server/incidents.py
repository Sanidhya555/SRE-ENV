# ── Shared dependency map (same for all tasks) ──────────────────
DEPS = {
    "api-gateway":          ["auth-service", "order-service", "payment-service"],
    "auth-service":         ["db-primary"],
    "order-service":        ["db-primary", "notification-service"],
    "payment-service":      ["db-primary"],
    "db-primary":           [],
    "notification-service": [],
}

# ── TASK 1 — Easy: Memory Leak ───────────────────────────────────
TASK1 = {
    "description": (
        "INCIDENT ALERT: order-service is repeatedly crashing and restarting. "
        "Customers cannot place orders. Started 25 minutes ago. "
        "Investigate and resolve the issue."
    ),
    "initial_alerts": [
        {
            "service": "order-service",
            "metric": "availability",
            "severity": "critical",
            "message": "order-service has restarted 7 times in the last 25 minutes",
        },
        {
            "service": "order-service",
            "metric": "memory",
            "severity": "critical",
            "message": "order-service memory usage at 98% before each crash",
        },
    ],
    "service_health": {
        "api-gateway":          "healthy",
        "auth-service":         "healthy",
        "order-service":        "down",
        "payment-service":      "healthy",
        "db-primary":           "healthy",
        "notification-service": "healthy",
    },
    "ground_truth": {
        "root_cause_service":  "order-service",
        "root_cause_category": "memory",
        "root_cause_specific": "memory_leak_oom",
        "correct_fix":         "restart",
    },
    "logs": {
        "order-service": {
            "entries": [
                "2026-03-27 02:41:12 [FATAL] OOMKilled — container exceeded memory limit of 512Mi",
                "2026-03-27 02:41:12 [ERROR] java.lang.OutOfMemoryError: Java heap space",
                "2026-03-27 02:38:55 [WARN]  GC overhead limit exceeded",
                "2026-03-27 02:35:10 [WARN]  Heap usage: 487Mi / 512Mi (95%)",
                "2026-03-27 02:30:01 [WARN]  Heap usage: 412Mi / 512Mi (80%)",
                "2026-03-27 02:20:00 [INFO]  order-service started successfully",
            ],
            "summary": "order-service is running out of heap memory and being OOMKilled by Kubernetes repeatedly.",
            "reveals_category": "memory",
            "reveals_specific": "memory_leak_oom",
        },
        "api-gateway": {
            "entries": [
                "2026-03-27 02:41:15 [ERROR] Upstream order-service returned 503",
            ],
            "summary": "api-gateway is seeing 503s from order-service but is otherwise healthy.",
            "reveals_category": None,
            "reveals_specific": None,
        },
        "auth-service":         {"entries": ["2026-03-27 02:41:00 [INFO] All systems normal"], "summary": "No issues.", "reveals_category": None, "reveals_specific": None},
        "payment-service":      {"entries": ["2026-03-27 02:41:00 [INFO] All systems normal"], "summary": "No issues.", "reveals_category": None, "reveals_specific": None},
        "db-primary":           {"entries": ["2026-03-27 02:41:00 [INFO] Normal. 42 active connections."], "summary": "No issues.", "reveals_category": None, "reveals_specific": None},
        "notification-service": {"entries": ["2026-03-27 02:41:00 [INFO] All systems normal"], "summary": "No issues.", "reveals_category": None, "reveals_specific": None},
    },
    "metrics": {
        "order-service": {
            "memory":     {"values": [41, 55, 68, 80, 91, 95, 98, 42, 55, 98], "unit": "%", "summary": "Memory grows linearly to 98% then crashes and restarts.", "reveals_category": "memory", "reveals_specific": "memory_leak_oom"},
            "cpu":        {"values": [12, 14, 88, 91, 12], "unit": "%", "summary": "CPU spikes only during GC before crash.", "reveals_category": None, "reveals_specific": None},
            "latency":    {"values": [45, 48, 890, 1200], "unit": "ms", "summary": "Latency spikes as memory runs out.", "reveals_category": None, "reveals_specific": None},
            "error_rate": {"values": [0, 0, 2.5, 8.0, 100], "unit": "%", "summary": "Error rate jumps as OOM approaches.", "reveals_category": None, "reveals_specific": None},
        },
        "api-gateway":      {"latency": {"values": [12, 13, 890], "unit": "ms", "summary": "Latency spikes due to order-service.", "reveals_category": None, "reveals_specific": None}},
        "auth-service":     {"cpu": {"values": [8, 9, 8], "unit": "%", "summary": "Normal.", "reveals_category": None, "reveals_specific": None}},
        "payment-service":  {"cpu": {"values": [5, 6, 5], "unit": "%", "summary": "Normal.", "reveals_category": None, "reveals_specific": None}},
        "db-primary":       {"connections": {"values": [38, 40, 42], "unit": "count", "summary": "Normal.", "reveals_category": None, "reveals_specific": None}},
        "notification-service": {"cpu": {"values": [3, 3], "unit": "%", "summary": "Normal.", "reveals_category": None, "reveals_specific": None}},
    },
    "deps": DEPS,
    "fix_outcomes": {
        "order-service": {
            "restart":              {"success": True,  "message": "order-service restarted. Memory reset to 42%. Service healthy.", "resolves": True,  "destructive": False},
            "rollback_deployment":  {"success": False, "message": "No recent deployment found. Memory leak predates last deploy.",  "resolves": False, "destructive": False},
            "increase_memory":      {"success": False, "message": "Memory limit increased but leak persists — not a real fix.",    "resolves": False, "destructive": False},
            "disable_feature_flag": {"success": False, "message": "No active feature flags on order-service.",                     "resolves": False, "destructive": False},
            "scale_up":             {"success": False, "message": "Each new pod also crashes — problem not resolved.",             "resolves": False, "destructive": True},
            "clear_cache":          {"success": False, "message": "Cache cleared but memory leak persists.",                       "resolves": False, "destructive": False},
        },
        "default": {"success": False, "message": "Fix applied to wrong service. order-service still crashing.", "resolves": False, "destructive": False},
    },
}

# ── TASK 2 — Medium: Cascading Failure ──────────────────────────
TASK2 = {
    "description": (
        "INCIDENT ALERT: Customers reporting checkout is extremely slow — "
        "taking 15-30 seconds. api-gateway latency spiked 45 minutes ago. "
        "Investigate and resolve."
    ),
    "initial_alerts": [
        {
            "service": "api-gateway",
            "metric": "latency",
            "severity": "critical",
            "message": "api-gateway p99 latency is 18,000ms — SLO threshold is 500ms",
        }
    ],
    "service_health": {
        "api-gateway":          "degraded",
        "auth-service":         "healthy",
        "order-service":        "healthy",
        "payment-service":      "degraded",
        "db-primary":           "degraded",
        "notification-service": "healthy",
    },
    "ground_truth": {
        "root_cause_service":  "payment-service",
        "root_cause_category": "database",
        "root_cause_specific": "slow_query_connection_pool_exhaustion",
        "correct_fix":         "rollback_deployment",
    },
    "logs": {
        "api-gateway": {
            "entries": [
                "2026-03-27 03:15:44 [WARN]  Request to payment-service timed out after 15000ms",
                "2026-03-27 03:10:12 [WARN]  Upstream payment-service slow — retrying",
                "2026-03-27 03:08:00 [INFO]  Normal operation",
            ],
            "summary": "api-gateway is slow because payment-service calls are timing out. api-gateway itself is fine.",
            "reveals_category": None,
            "reveals_specific": None,
        },
        "payment-service": {
            "entries": [
                "2026-03-27 03:15:50 [ERROR] DB connection pool exhausted (pool size: 10/10 in use)",
                "2026-03-27 03:15:40 [WARN]  Slow query: SELECT * FROM transactions WHERE user_id=? took 8420ms",
                "2026-03-27 03:10:00 [INFO]  Deployment v2.4.1 started — added full transaction history query",
                "2026-03-27 03:09:55 [INFO]  payment-service v2.4.1 deployed successfully",
            ],
            "summary": "payment-service v2.4.1 added an unindexed full-table-scan query, exhausting the DB connection pool.",
            "reveals_category": "database",
            "reveals_specific": "slow_query_connection_pool_exhaustion",
        },
        "db-primary": {
            "entries": [
                "2026-03-27 03:15:55 [WARN]  10 long-running queries detected (>5s)",
                "2026-03-27 03:15:50 [WARN]  Query from payment-service: full table scan (4.2M rows)",
                "2026-03-27 03:10:05 [INFO]  New query pattern observed from payment-service",
            ],
            "summary": "DB running full table scans on every payment due to missing index in payment-service v2.4.1.",
            "reveals_category": "database",
            "reveals_specific": "slow_query_connection_pool_exhaustion",
        },
        "auth-service":         {"entries": ["2026-03-27 03:15:00 [INFO] Normal"], "summary": "No issues.", "reveals_category": None, "reveals_specific": None},
        "order-service":        {"entries": ["2026-03-27 03:15:00 [INFO] Normal"], "summary": "No issues.", "reveals_category": None, "reveals_specific": None},
        "notification-service": {"entries": ["2026-03-27 03:15:00 [INFO] Normal"], "summary": "No issues.", "reveals_category": None, "reveals_specific": None},
    },
    "metrics": {
        "api-gateway":     {"latency": {"values": [45, 48, 4200, 18000], "unit": "ms", "summary": "Latency climbed after 03:10 matching payment-service deploy.", "reveals_category": None, "reveals_specific": None}},
        "payment-service": {
            "latency":     {"values": [80, 85, 2100, 15000], "unit": "ms", "summary": "Latency spiked at 03:10 — exactly when v2.4.1 deployed.", "reveals_category": "database", "reveals_specific": None},
            "connections": {"values": [2, 3, 8, 10, 10], "unit": "count", "summary": "DB connection pool hit maximum (10) and stayed there.", "reveals_category": "database", "reveals_specific": "slow_query_connection_pool_exhaustion"},
            "error_rate":  {"values": [0, 0, 12.0, 28.0], "unit": "%", "summary": "High error rate from connection timeouts.", "reveals_category": None, "reveals_specific": None},
        },
        "db-primary": {
            "cpu":         {"values": [22, 28, 89, 98], "unit": "%", "summary": "CPU spiked to 98% — full table scans expensive.", "reveals_category": None, "reveals_specific": None},
            "connections": {"values": [20, 25, 10, 10], "unit": "count", "summary": "All 10 payment-service connections consumed.", "reveals_category": None, "reveals_specific": None},
        },
        "auth-service":         {"cpu": {"values": [9, 9, 10], "unit": "%", "summary": "Normal.", "reveals_category": None, "reveals_specific": None}},
        "order-service":        {"cpu": {"values": [11, 12, 11], "unit": "%", "summary": "Normal.", "reveals_category": None, "reveals_specific": None}},
        "notification-service": {"cpu": {"values": [3, 3], "unit": "%", "summary": "Normal.", "reveals_category": None, "reveals_specific": None}},
    },
    "deps": DEPS,
    "fix_outcomes": {
        "payment-service": {
            "rollback_deployment":  {"success": True,  "message": "Rolled back to v2.4.0. Slow query removed. DB pool freed. Latency normalising.", "resolves": True,  "destructive": False},
            "restart":              {"success": False, "message": "Restarted but v2.4.1 still running — slow query persists.",                     "resolves": False, "destructive": False},
            "disable_feature_flag": {"success": False, "message": "No feature flags control this query. Must rollback.",                            "resolves": False, "destructive": False},
        },
        "db-primary": {
            "restart":  {"success": False, "message": "DB restarted but payment-service v2.4.1 immediately re-exhausts pool.", "resolves": False, "destructive": True},
            "scale_up": {"success": False, "message": "More DB instances don't help — the query itself is the problem.",       "resolves": False, "destructive": False},
        },
        "default": {"success": False, "message": "Fix applied to wrong service. Slow query still running.", "resolves": False, "destructive": False},
    },
}

# ── TASK 3 — Hard: Red Herring Storm ────────────────────────────
TASK3 = {
    "description": (
        "INCIDENT ALERT: Multiple simultaneous alerts. "
        "1) auth-service high latency. "
        "2) db-primary CPU spike. "
        "3) api-gateway 5xx errors — logins failing. "
        "Investigate and resolve urgently."
    ),
    "initial_alerts": [
        {
            "service": "auth-service",
            "metric": "latency",
            "severity": "critical",
            "message": "auth-service p99 latency 8,200ms — SLO breach",
        },
        {
            "service": "db-primary",
            "metric": "cpu",
            "severity": "warning",
            "message": "db-primary CPU at 87% — elevated",
        },
        {
            "service": "api-gateway",
            "metric": "error_rate",
            "severity": "critical",
            "message": "api-gateway 5xx error rate 34% — logins failing",
        },
    ],
    "service_health": {
        "api-gateway":          "degraded",
        "auth-service":         "down",
        "order-service":        "healthy",
        "payment-service":      "healthy",
        "db-primary":           "degraded",
        "notification-service": "healthy",
    },
    "ground_truth": {
        "root_cause_service":  "auth-service",
        "root_cause_category": "feature_flag",
        "root_cause_specific": "token_cache_disabled_thundering_herd",
        "correct_fix":         "disable_feature_flag",
    },
    "logs": {
        "auth-service": {
            "entries": [
                "2026-03-27 04:00:05 [ERROR] Token cache MISS for user_id=8842910 — fetching from db-primary",
                "2026-03-27 04:00:03 [WARN]  Feature flag 'disable_token_cache' = TRUE — cache bypassed",
                "2026-03-27 04:00:03 [WARN]  Every authentication request now hits db-primary directly",
                "2026-03-27 03:59:55 [INFO]  Feature flag updated: disable_token_cache = true",
                "2026-03-27 03:59:50 [INFO]  auth-service normal operation",
            ],
            "summary": "Feature flag 'disable_token_cache' enabled at 03:59 — every login now hits db-primary directly. 1200 req/s thundering herd.",
            "reveals_category": "feature_flag",
            "reveals_specific": "token_cache_disabled_thundering_herd",
        },
        "db-primary": {
            "entries": [
                "2026-03-27 04:00:10 [INFO]  Automated backup started (scheduled, runs every 6h)",
                "2026-03-27 04:00:05 [WARN]  High read query volume from auth-service: 1,200 queries/sec (normal: 12/sec)",
                "2026-03-27 03:58:00 [INFO]  Automated backup started — this is normal scheduled activity",
            ],
            "summary": "DB CPU high for TWO reasons: (1) scheduled backup (normal — ignore this), (2) 100x more queries from auth-service. Backup is a red herring.",
            "reveals_category": None,
            "reveals_specific": None,
        },
        "api-gateway": {
            "entries": [
                "2026-03-27 04:00:08 [ERROR] auth-service timeout on login — returning 503",
                "2026-03-27 04:00:06 [WARN]  auth-service response time 8200ms — retrying",
            ],
            "summary": "api-gateway errors caused entirely by auth-service being slow. api-gateway itself is fine.",
            "reveals_category": None,
            "reveals_specific": None,
        },
        "order-service":        {"entries": ["2026-03-27 04:00:00 [INFO] Normal"], "summary": "No issues.", "reveals_category": None, "reveals_specific": None},
        "payment-service":      {"entries": ["2026-03-27 04:00:00 [INFO] Normal"], "summary": "No issues.", "reveals_category": None, "reveals_specific": None},
        "notification-service": {"entries": ["2026-03-27 04:00:00 [INFO] Normal"], "summary": "No issues.", "reveals_category": None, "reveals_specific": None},
    },
    "metrics": {
        "auth-service": {
            "latency":     {"values": [12, 14, 4200, 8200], "unit": "ms", "summary": "Latency spiked at exactly 03:59 — matches feature flag change.", "reveals_category": "feature_flag", "reveals_specific": None},
            "error_rate":  {"values": [0, 0, 28.0, 34.0], "unit": "%", "summary": "High error rate from DB timeouts.", "reveals_category": None, "reveals_specific": None},
            "connections": {"values": [8, 9, 10, 10], "unit": "count", "summary": "DB pool exhausted from 100x query volume.", "reveals_category": "feature_flag", "reveals_specific": "token_cache_disabled_thundering_herd"},
        },
        "db-primary": {
            "cpu":         {"values": [25, 30, 72, 87, 91], "unit": "%", "summary": "CPU elevated from backup (+20%) AND auth thundering herd (+42%).", "reveals_category": None, "reveals_specific": None},
            "connections": {"values": [22, 41, 80, 95], "unit": "count", "summary": "Connections growing rapidly — auth-service consuming most slots.", "reveals_category": None, "reveals_specific": None},
        },
        "api-gateway":     {"error_rate": {"values": [0, 0, 18, 34], "unit": "%", "summary": "Error rate matches auth-service degradation.", "reveals_category": None, "reveals_specific": None}},
        "order-service":   {"cpu": {"values": [12, 13, 12], "unit": "%", "summary": "Normal.", "reveals_category": None, "reveals_specific": None}},
        "payment-service": {"cpu": {"values": [8, 9, 8], "unit": "%", "summary": "Normal.", "reveals_category": None, "reveals_specific": None}},
        "notification-service": {"cpu": {"values": [3, 3], "unit": "%", "summary": "Normal.", "reveals_category": None, "reveals_specific": None}},
    },
    "deps": DEPS,
    "fix_outcomes": {
        "auth-service": {
            "disable_feature_flag": {"success": True,  "message": "Flag 'disable_token_cache' set FALSE. Token cache restored. Auth queries dropped from 1200/s to 12/s. All services recovering.", "resolves": True,  "destructive": False},
            "restart":              {"success": False, "message": "auth-service restarted but flag still enabled — token cache still bypassed. Problem persists.",                                  "resolves": False, "destructive": False},
            "rollback_deployment":  {"success": False, "message": "No recent auth-service deployment. Flag was changed via config, not a deploy.",                                                 "resolves": False, "destructive": False},
        },
        "db-primary": {
            "restart":  {"success": False, "message": "DB restarted — backup stops but thundering herd immediately resumes.", "resolves": False, "destructive": True},
            "scale_up": {"success": False, "message": "More DB replicas added but auth query volume still overwhelming.",     "resolves": False, "destructive": False},
        },
        "default": {"success": False, "message": "Fix applied to wrong service. auth-service still overwhelming db-primary.", "resolves": False, "destructive": False},
    },
}

# ── Final export ─────────────────────────────────────────────────
INCIDENTS = {
    1: TASK1,
    2: TASK2,
    3: TASK3,
}