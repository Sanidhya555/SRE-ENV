# ── Shared dependency map ────────────────────────────────────────
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
        {"service": "order-service", "metric": "availability", "severity": "critical", "message": "order-service has restarted 7 times in the last 25 minutes (CrashLoopBackOff)"},
        {"service": "order-service", "metric": "memory",       "severity": "critical", "message": "order-service memory usage reached 98% before each crash — OOMKill suspected"},
    ],
    "service_health": {
        "api-gateway": "healthy", "auth-service": "healthy", "order-service": "down",
        "payment-service": "healthy", "db-primary": "healthy", "notification-service": "healthy",
    },
    "ground_truth": {
        "root_cause_service": "order-service", "root_cause_category": "memory",
        "root_cause_specific": "memory_leak_oom", "correct_fix": "restart",
    },
    "logs": {
        "order-service": {
            "entries": [
                "2026-03-27 02:41:12 [FATAL] pod/order-service-7d9f8b-xk2p9: OOMKilled — container exceeded memory limit of 512Mi",
                "2026-03-27 02:41:12 [ERROR] java.lang.OutOfMemoryError: Java heap space at com.company.order.cache.SessionCache.put(SessionCache.java:142)",
                "2026-03-27 02:41:11 [ERROR] GC overhead limit exceeded — JVM spent >98% time in garbage collection",
                "2026-03-27 02:40:58 [WARN]  HeapDumpOnOutOfMemoryError triggered — writing heap dump to /tmp/order-service-heap.hprof",
                "2026-03-27 02:38:55 [WARN]  GC overhead limit exceeded — garbage collector running > 98% of time",
                "2026-03-27 02:37:10 [WARN]  SessionCache size: 847,293 entries (unbounded growth — no TTL set)",
                "2026-03-27 02:35:10 [WARN]  Heap usage: 487Mi / 512Mi (95%) — approaching limit",
                "2026-03-27 02:33:44 [WARN]  Heap usage: 461Mi / 512Mi (90%) — GC pressure increasing",
                "2026-03-27 02:30:01 [WARN]  Heap usage: 412Mi / 512Mi (80%) — monitoring",
                "2026-03-27 02:25:00 [WARN]  Heap usage: 350Mi / 512Mi (68%) — slight increase",
                "2026-03-27 02:20:00 [INFO]  order-service v3.2.1 started — SessionCache initialized (unbounded, no eviction policy)",
                "2026-03-27 02:19:55 [INFO]  Connected to db-primary:5432 — connection pool: 10",
                "2026-03-27 02:19:50 [INFO]  order-service startup complete — listening on :8080",
            ],
            "summary": "order-service has an unbounded SessionCache with no TTL or eviction. Memory grows linearly until OOMKill every ~20 minutes. Restart clears cache temporarily.",
            "reveals_category": "memory", "reveals_specific": "memory_leak_oom",
        },
        "api-gateway": {
            "entries": [
                "2026-03-27 02:41:18 [ERROR] upstream order-service: connection refused (pod restarting)",
                "2026-03-27 02:41:15 [ERROR] upstream order-service: 503 Service Unavailable after 3 retries",
                "2026-03-27 02:41:14 [WARN]  circuit breaker OPEN for order-service (failure rate: 100% over last 60s)",
                "2026-03-27 02:40:55 [WARN]  upstream order-service response time: 8,420ms (SLO: 500ms)",
                "2026-03-27 02:38:00 [INFO]  upstream order-service latency degrading — p99: 2,400ms",
                "2026-03-27 02:20:05 [INFO]  upstream order-service healthy — p99: 42ms",
            ],
            "summary": "api-gateway seeing 503s from order-service. Circuit breaker opened. api-gateway itself is healthy.",
            "reveals_category": None, "reveals_specific": None,
        },
        "auth-service":         {"entries": ["2026-03-27 02:41:00 [INFO]  auth-service healthy — 1,240 token validations/min", "2026-03-27 02:40:00 [INFO]  Token cache hit rate: 94.2% — normal"], "summary": "Fully healthy.", "reveals_category": None, "reveals_specific": None},
        "payment-service":      {"entries": ["2026-03-27 02:41:00 [INFO]  payment-service healthy — 0 failed transactions", "2026-03-27 02:40:00 [INFO]  db-primary pool: 2/10 — normal"], "summary": "Fully healthy.", "reveals_category": None, "reveals_specific": None},
        "db-primary":           {"entries": ["2026-03-27 02:41:00 [INFO]  42 active connections — normal (max: 200)", "2026-03-27 02:40:00 [INFO]  Query performance nominal — avg: 4.2ms", "2026-03-27 02:39:00 [INFO]  Replication lag: 0ms"], "summary": "Fully healthy. Normal connections and query performance.", "reveals_category": None, "reveals_specific": None},
        "notification-service": {"entries": ["2026-03-27 02:41:00 [INFO]  notification-service healthy — email queue: 12", "2026-03-27 02:40:00 [INFO]  SMS gateway: connected — 0 failures"], "summary": "Fully healthy.", "reveals_category": None, "reveals_specific": None},
    },
    "metrics": {
        "order-service": {
            "memory":     {"values": [41, 48, 55, 63, 72, 80, 88, 95, 98, "OOM", 42, 55, 75, 95, 98, "OOM"], "unit": "%", "summary": "Memory grows linearly 41%→98% over ~20 min, crashes, resets. Classic memory leak sawtooth pattern.", "reveals_category": "memory", "reveals_specific": "memory_leak_oom"},
            "cpu":        {"values": [12, 13, 14, 15, 88, 92, 97, 12, 13], "unit": "%", "summary": "CPU normal until GC thrashing kicks in just before OOM.", "reveals_category": None, "reveals_specific": None},
            "latency":    {"values": [42, 45, 52, 180, 890, 2400, 6100, 8420, "timeout"], "unit": "ms", "summary": "Latency degrades sharply as heap fills — GC pauses cause delays.", "reveals_category": None, "reveals_specific": None},
            "error_rate": {"values": [0, 0, 0.1, 1.2, 8.0, 45.0, 100.0], "unit": "%", "summary": "Error rate jumps exponentially as OOM approaches.", "reveals_category": None, "reveals_specific": None},
        },
        "api-gateway":      {"latency": {"values": [11, 12, 890, 2400, 8420], "unit": "ms", "summary": "Latency mirrors order-service degradation.", "reveals_category": None, "reveals_specific": None}},
        "auth-service":     {"cpu": {"values": [8, 9, 8, 9], "unit": "%", "summary": "Normal.", "reveals_category": None, "reveals_specific": None}, "memory": {"values": [32, 32, 33], "unit": "%", "summary": "Normal.", "reveals_category": None, "reveals_specific": None}},
        "payment-service":  {"cpu": {"values": [5, 6, 5, 6], "unit": "%", "summary": "Normal.", "reveals_category": None, "reveals_specific": None}},
        "db-primary":       {"connections": {"values": [38, 40, 42, 41, 38], "unit": "count", "summary": "Normal connection count.", "reveals_category": None, "reveals_specific": None}, "cpu": {"values": [22, 23, 24, 22], "unit": "%", "summary": "Normal.", "reveals_category": None, "reveals_specific": None}},
        "notification-service": {"cpu": {"values": [3, 3, 4, 3], "unit": "%", "summary": "Normal.", "reveals_category": None, "reveals_specific": None}},
    },
    "deps": DEPS,
    "fix_outcomes": {
        "order-service": {
            "restart":              {"success": True,  "message": "order-service restarted. Memory reset to 42%. SessionCache cleared. Service healthy. NOTE: Root cause (unbounded cache) still exists — will recur in ~20 min without a code fix.", "resolves": True,  "destructive": False},
            "rollback_deployment":  {"success": False, "message": "Rolled back to v3.2.0 — but SessionCache bug also exists there. Memory leak persists.", "resolves": False, "destructive": False},
            "increase_memory":      {"success": False, "message": "Memory limit increased to 2Gi. Leak continues — crash delayed to ~80 min. Not a real fix.", "resolves": False, "destructive": False},
            "disable_feature_flag": {"success": False, "message": "No active feature flags on order-service.", "resolves": False, "destructive": False},
            "scale_up":             {"success": False, "message": "Added 3 pods. Each also leaks memory and crashes. Made things worse.", "resolves": False, "destructive": True},
            "clear_cache":          {"success": False, "message": "Cache cleared. Memory drops temporarily but leak resumes — cache fills again in ~20 min.", "resolves": False, "destructive": False},
        },
        "default": {"success": False, "message": "Fix applied to wrong service. order-service still crashing due to memory leak.", "resolves": False, "destructive": False},
    },
}

# ── TASK 2 — Medium: Cascading Failure ──────────────────────────
TASK2 = {
    "description": (
        "INCIDENT ALERT: Customers reporting checkout is extremely slow — "
        "taking 15-30 seconds or timing out. api-gateway p99 latency spiked "
        "45 minutes ago. Revenue impact confirmed. Investigate and resolve."
    ),
    "initial_alerts": [
        {"service": "api-gateway", "metric": "latency", "severity": "critical", "message": "api-gateway p99 latency is 18,000ms — SLO threshold is 500ms. Checkout flow impacted."},
    ],
    "service_health": {
        "api-gateway": "degraded", "auth-service": "healthy", "order-service": "healthy",
        "payment-service": "degraded", "db-primary": "degraded", "notification-service": "healthy",
    },
    "ground_truth": {
        "root_cause_service": "payment-service", "root_cause_category": "database",
        "root_cause_specific": "slow_query_connection_pool_exhaustion", "correct_fix": "rollback_deployment",
    },
    "logs": {
        "api-gateway": {
            "entries": [
                "2026-03-27 03:15:50 [ERROR] upstream payment-service: timeout after 15,000ms on POST /payments/process",
                "2026-03-27 03:15:44 [WARN]  upstream payment-service: request queued 8,200ms (pool saturated)",
                "2026-03-27 03:15:40 [WARN]  upstream payment-service: p99 latency 14,800ms — retrying (1/3)",
                "2026-03-27 03:14:20 [WARN]  upstream payment-service: p99 latency 9,400ms — degrading",
                "2026-03-27 03:12:00 [WARN]  upstream payment-service: p99 latency 4,200ms — slight degradation",
                "2026-03-27 03:10:15 [INFO]  upstream payment-service: latency spiked from 85ms to 2,100ms",
                "2026-03-27 03:09:58 [INFO]  upstream payment-service: healthy — p99: 85ms",
                "2026-03-27 03:09:50 [INFO]  payment-service deployment event received: v2.4.1 rolling out",
                "2026-03-27 03:08:00 [INFO]  all upstreams healthy — p99 < 100ms",
            ],
            "summary": "api-gateway is fine. All latency traces to payment-service. Spike began at 03:10 — exactly when payment-service v2.4.1 was deployed.",
            "reveals_category": None, "reveals_specific": None,
        },
        "payment-service": {
            "entries": [
                "2026-03-27 03:15:55 [ERROR] DB connection pool EXHAUSTED — 10/10 connections in use, request waiting",
                "2026-03-27 03:15:50 [ERROR] DB connection pool EXHAUSTED — queued request timed out after 5,000ms",
                "2026-03-27 03:15:45 [ERROR] Slow query: SELECT t.*, u.profile FROM transactions t JOIN users u ON t.user_id = u.id WHERE t.user_id = ? — 8,420ms (limit: 1,000ms)",
                "2026-03-27 03:15:40 [WARN]  DB connection pool: 10/10 in use — pool saturated",
                "2026-03-27 03:15:35 [WARN]  EXPLAIN output: Seq Scan on transactions — 4,218,492 rows examined — MISSING INDEX on user_id",
                "2026-03-27 03:15:20 [WARN]  DB connection pool: 9/10 in use — approaching saturation",
                "2026-03-27 03:14:10 [WARN]  Slow query: user transaction history taking 6,800ms",
                "2026-03-27 03:13:00 [WARN]  DB pool: 7/10 in use — increasing load",
                "2026-03-27 03:10:05 [INFO]  payment-service v2.4.1 started — added getUserTransactionHistory() to payment validation",
                "2026-03-27 03:10:00 [INFO]  payment-service v2.4.1 deployed — new feature: full transaction history in payment flow",
                "2026-03-27 03:09:55 [INFO]  payment-service v2.4.0 shutting down gracefully",
                "2026-03-27 03:09:00 [INFO]  payment-service v2.4.0 healthy — DB pool: 2/10, p99: 80ms",
            ],
            "summary": "payment-service v2.4.1 added getUserTransactionHistory() — full table scan on transactions (4.2M rows) with no user_id index. Each payment holds a DB connection 6-8 seconds, exhausting the pool. New payments queue and timeout.",
            "reveals_category": "database", "reveals_specific": "slow_query_connection_pool_exhaustion",
        },
        "db-primary": {
            "entries": [
                "2026-03-27 03:15:58 [WARN]  10 long-running queries active (>5,000ms) — all from payment-service",
                "2026-03-27 03:15:55 [WARN]  SLOW QUERY: SELECT t.*, u.profile FROM transactions t JOIN users u WHERE t.user_id = $1 — 8,420ms — Seq Scan on transactions (4,218,492 rows)",
                "2026-03-27 03:15:50 [WARN]  MISSING INDEX: CREATE INDEX idx_transactions_user_id ON transactions(user_id)",
                "2026-03-27 03:15:40 [WARN]  CPU: 98% — sustained by sequential scans from payment-service",
                "2026-03-27 03:15:30 [WARN]  I/O throughput: 890 MB/s read — disk thrash from table scans",
                "2026-03-27 03:15:20 [WARN]  Active connections from payment-service: 10/10 (pool maxed)",
                "2026-03-27 03:10:10 [INFO]  New query from payment-service: transaction history join — monitoring",
                "2026-03-27 03:10:05 [INFO]  First slow query from payment-service v2.4.1: 2,100ms",
                "2026-03-27 03:09:00 [INFO]  Normal — queries < 10ms, active connections: 22",
            ],
            "summary": "DB running full table scans (4.2M rows) per payment due to missing index in payment-service v2.4.1. CPU 98%. Caused entirely by new query in v2.4.1.",
            "reveals_category": "database", "reveals_specific": "slow_query_connection_pool_exhaustion",
        },
        "auth-service":         {"entries": ["2026-03-27 03:15:00 [INFO]  auth-service healthy", "2026-03-27 03:10:00 [INFO]  db pool: 3/10 — normal"], "summary": "Fully healthy.", "reveals_category": None, "reveals_specific": None},
        "order-service":        {"entries": ["2026-03-27 03:15:00 [INFO]  order-service healthy — 340 orders/min", "2026-03-27 03:14:00 [WARN]  payment-service calls timing out — order completions dropping"], "summary": "Healthy but order completions dropping because payment-service times out.", "reveals_category": None, "reveals_specific": None},
        "notification-service": {"entries": ["2026-03-27 03:15:00 [INFO]  notification-service healthy"], "summary": "Fully healthy.", "reveals_category": None, "reveals_specific": None},
    },
    "metrics": {
        "api-gateway":     {"latency": {"values": [44, 46, 85, 320, 2100, 4200, 9400, 14800, 18000], "unit": "ms", "summary": "Latency climbed from 03:10 — matches payment-service deployment time exactly.", "reveals_category": None, "reveals_specific": None}},
        "payment-service": {
            "latency":     {"values": [78, 82, 85, 90, 2100, 4800, 8000, 12000, 15000], "unit": "ms", "summary": "Latency spiked sharply at 03:10 — exact deployment correlation.", "reveals_category": "database", "reveals_specific": None},
            "connections": {"values": [2, 2, 3, 4, 6, 8, 10, 10, 10], "unit": "count", "summary": "DB connections grew to max (10) and stayed — pool exhaustion. Each connection held 8+ seconds.", "reveals_category": "database", "reveals_specific": "slow_query_connection_pool_exhaustion"},
            "error_rate":  {"values": [0, 0, 0, 0.5, 4.2, 12.0, 28.0], "unit": "%", "summary": "Error rate from DB connection timeouts.", "reveals_category": None, "reveals_specific": None},
        },
        "db-primary": {
            "cpu":         {"values": [22, 24, 26, 28, 55, 78, 89, 95, 98], "unit": "%", "summary": "CPU spiked from 28% to 98% at 03:10 — full table scans are CPU intensive.", "reveals_category": None, "reveals_specific": None},
            "connections": {"values": [20, 22, 25, 28, 10, 10, 10, 10], "unit": "count", "summary": "All 10 payment-service connections consumed.", "reveals_category": None, "reveals_specific": None},
        },
        "auth-service":         {"cpu": {"values": [9, 9, 10, 9], "unit": "%", "summary": "Normal.", "reveals_category": None, "reveals_specific": None}},
        "order-service":        {"cpu": {"values": [11, 12, 11, 12], "unit": "%", "summary": "Normal.", "reveals_category": None, "reveals_specific": None}},
        "notification-service": {"cpu": {"values": [3, 3, 4], "unit": "%", "summary": "Normal.", "reveals_category": None, "reveals_specific": None}},
    },
    "deps": DEPS,
    "fix_outcomes": {
        "payment-service": {
            "rollback_deployment":  {"success": True,  "message": "Rolled back to v2.4.0. getUserTransactionHistory() removed. DB pool freed (10→2). CPU dropped 98%→24%. p99 latency: 48ms. Revenue flow restored.", "resolves": True,  "destructive": False},
            "restart":              {"success": False, "message": "Restarted but v2.4.1 still running — slow query resumes immediately. Pool exhausts again in 30 seconds.", "resolves": False, "destructive": False},
            "disable_feature_flag": {"success": False, "message": "No flags control the transaction history query in v2.4.1. Must rollback.", "resolves": False, "destructive": False},
            "increase_memory":      {"success": False, "message": "Memory is not the issue. Slow query and connection exhaustion persist.", "resolves": False, "destructive": False},
        },
        "db-primary": {
            "restart":  {"success": False, "message": "DB restarted — brief relief but payment-service v2.4.1 immediately re-exhausts pool. CPU back to 98% in 60 seconds.", "resolves": False, "destructive": True},
            "scale_up": {"success": False, "message": "Added read replicas but payment-service still queries primary. Problem unchanged.", "resolves": False, "destructive": False},
        },
        "default": {"success": False, "message": "Fix applied to wrong service. Slow query still running. DB pool still exhausted.", "resolves": False, "destructive": False},
    },
}

# ── TASK 3 — Hard: Red Herring Storm ────────────────────────────
TASK3 = {
    "description": (
        "INCIDENT ALERT: Multiple simultaneous critical alerts — possible major outage. "
        "1) auth-service p99 latency 8,200ms — logins failing. "
        "2) db-primary CPU at 87% — elevated. "
        "3) api-gateway 5xx error rate 34%. "
        "All three fired within 30 seconds. Investigate urgently."
    ),
    "initial_alerts": [
        {"service": "auth-service",  "metric": "latency",    "severity": "critical", "message": "auth-service p99 latency 8,200ms — SLO breach (threshold: 200ms). Login flow failing."},
        {"service": "db-primary",    "metric": "cpu",        "severity": "warning",  "message": "db-primary CPU at 87% — elevated. Could be backup or query load."},
        {"service": "api-gateway",   "metric": "error_rate", "severity": "critical", "message": "api-gateway 5xx error rate 34% — all errors are auth-service timeouts."},
    ],
    "service_health": {
        "api-gateway": "degraded", "auth-service": "down", "order-service": "healthy",
        "payment-service": "healthy", "db-primary": "degraded", "notification-service": "healthy",
    },
    "ground_truth": {
        "root_cause_service": "auth-service", "root_cause_category": "feature_flag",
        "root_cause_specific": "token_cache_disabled_thundering_herd", "correct_fix": "disable_feature_flag",
    },
    "logs": {
        "auth-service": {
            "entries": [
                "2026-03-27 04:00:08 [ERROR] Token validation failed: DB query timeout after 5,000ms for user_id=9182736",
                "2026-03-27 04:00:07 [ERROR] Token cache MISS for user_id=8842910 — cache DISABLED — querying db-primary (RTT: 8,200ms)",
                "2026-03-27 04:00:06 [ERROR] Token cache MISS for user_id=7731920 — cache DISABLED — querying db-primary",
                "2026-03-27 04:00:05 [ERROR] DB connection pool EXHAUSTED — 10/10 connections in use — token validation queued",
                "2026-03-27 04:00:04 [WARN]  Feature flag 'disable_token_cache' = TRUE — JWT token cache completely bypassed",
                "2026-03-27 04:00:04 [WARN]  Cache bypass active: every auth request now queries db-primary directly",
                "2026-03-27 04:00:03 [WARN]  DB connection pool: 8/10 — rapid growth",
                "2026-03-27 04:00:02 [WARN]  DB connection pool: 4/10 — growing",
                "2026-03-27 03:59:58 [INFO]  Feature flag 'disable_token_cache' changed: false → true (by: config-service auto-deploy, reason: 'security audit mode')",
                "2026-03-27 03:59:55 [INFO]  Config refresh from config-service — applying 3 flag changes",
                "2026-03-27 03:59:50 [INFO]  auth-service healthy — token cache hit rate: 96.4%, p99: 12ms",
                "2026-03-27 03:58:00 [INFO]  auth-service healthy — 1,240 auth req/min, cache hit rate: 96.4%",
            ],
            "summary": "REAL ROOT CAUSE: Feature flag 'disable_token_cache' set TRUE at 03:59:58 by config-service auto-deploy ('security audit mode'). Token cache disabled — every auth request now hits db-primary directly. 1,240 req/min → thundering herd (100x normal DB load). Connection pool exhausted in seconds.",
            "reveals_category": "feature_flag", "reveals_specific": "token_cache_disabled_thundering_herd",
        },
        "db-primary": {
            "entries": [
                "2026-03-27 04:00:10 [INFO]  Automated scheduled backup started (runs every 6 hours — EXPECTED and NORMAL)",
                "2026-03-27 04:00:09 [INFO]  Backup: pg_basebackup started — estimated duration: 12 minutes",
                "2026-03-27 04:00:08 [WARN]  High read volume from auth-service: 1,187 queries/sec (baseline: 12/sec — 99x spike)",
                "2026-03-27 04:00:06 [WARN]  Auth token lookups flooding: SELECT * FROM auth_tokens WHERE token_hash = $1 — 1,100/sec",
                "2026-03-27 04:00:05 [WARN]  CPU breakdown: auth-service queries +62%, backup job +25% = total 87%",
                "2026-03-27 04:00:02 [WARN]  auth-service consuming 10/10 available connections",
                "2026-03-27 03:59:59 [INFO]  Pre-backup checkpoint — normal",
                "2026-03-27 03:58:00 [INFO]  Normal — connections: 22, CPU: 25%, avg query: 3.1ms",
                "2026-03-27 03:54:00 [INFO]  Last backup completed at 03:54 — next in 6h",
            ],
            "summary": "RED HERRING: CPU high for TWO reasons — (1) scheduled 6h backup (+25% CPU — normal and expected), (2) auth thundering herd (+62% CPU — the real problem). Backup is a distraction. Auth queries are the issue.",
            "reveals_category": None, "reveals_specific": None,
        },
        "api-gateway": {
            "entries": [
                "2026-03-27 04:00:12 [ERROR] auth-service timeout on POST /auth/validate — returning 503",
                "2026-03-27 04:00:11 [ERROR] auth-service timeout on POST /auth/validate — returning 503",
                "2026-03-27 04:00:08 [WARN]  auth-service response time 8,200ms — circuit breaker approaching",
                "2026-03-27 04:00:05 [WARN]  auth-service response time 6,400ms — degrading",
                "2026-03-27 03:59:58 [INFO]  auth-service healthy — p99: 12ms",
                "2026-03-27 03:59:55 [INFO]  All upstreams healthy",
            ],
            "summary": "RED HERRING: api-gateway errors caused entirely by auth-service slowness. api-gateway itself is healthy. Fix auth-service and errors clear immediately.",
            "reveals_category": None, "reveals_specific": None,
        },
        "order-service":        {"entries": ["2026-03-27 04:00:00 [INFO]  order-service healthy — 340 orders/min", "2026-03-27 03:59:00 [INFO]  db pool: 2/10 — normal"], "summary": "Fully healthy. No involvement.", "reveals_category": None, "reveals_specific": None},
        "payment-service":      {"entries": ["2026-03-27 04:00:00 [INFO]  payment-service healthy — 0 payment failures", "2026-03-27 03:59:00 [INFO]  db pool: 1/10 — normal"], "summary": "Fully healthy. No involvement.", "reveals_category": None, "reveals_specific": None},
        "notification-service": {"entries": ["2026-03-27 04:00:00 [INFO]  notification-service healthy — email queue: 8"], "summary": "Fully healthy.", "reveals_category": None, "reveals_specific": None},
    },
    "metrics": {
        "auth-service": {
            "latency":     {"values": [11, 12, 13, 12, 14, 4200, 6400, 8200], "unit": "ms", "summary": "Was 12ms, spiked to 8,200ms at 03:59:58 — matches feature flag change exactly.", "reveals_category": "feature_flag", "reveals_specific": None},
            "error_rate":  {"values": [0, 0, 0, 0, 0, 0.1, 18.0, 34.0], "unit": "%", "summary": "Error rate jumped 0%→34% in under 10 seconds — thundering herd onset.", "reveals_category": None, "reveals_specific": None},
            "connections": {"values": [1, 1, 2, 2, 3, 4, 8, 10, 10], "unit": "count", "summary": "DB connections grew from 1-3 (normal, cache handles 96%) to 10/10 maxed within 10 seconds of cache being disabled.", "reveals_category": "feature_flag", "reveals_specific": "token_cache_disabled_thundering_herd"},
        },
        "db-primary": {
            "cpu":         {"values": [24, 25, 26, 25, 87, 89, 91, 88], "unit": "%", "summary": "CPU jumped 25%→87-91% at 04:00. Two causes: backup (+25%) and auth herd (+62%). Backup alone would cause only 45%.", "reveals_category": None, "reveals_specific": None},
            "connections": {"values": [22, 24, 25, 22, 82, 95, 98, 95], "unit": "count", "summary": "Connections jumped from ~24 to 98 — auth-service consuming all 10 dedicated connections.", "reveals_category": None, "reveals_specific": None},
        },
        "api-gateway":     {"error_rate": {"values": [0, 0, 0, 0, 0.2, 18.0, 34.0], "unit": "%", "summary": "Error rate mirrors auth-service spike — confirms api-gateway is victim not cause.", "reveals_category": None, "reveals_specific": None}},
        "order-service":   {"cpu": {"values": [12, 13, 12, 13], "unit": "%", "summary": "Normal. Unaffected.", "reveals_category": None, "reveals_specific": None}},
        "payment-service": {"cpu": {"values": [8, 9, 8, 9], "unit": "%", "summary": "Normal. Unaffected.", "reveals_category": None, "reveals_specific": None}},
        "notification-service": {"cpu": {"values": [3, 3, 4], "unit": "%", "summary": "Normal. Unaffected.", "reveals_category": None, "reveals_specific": None}},
    },
    "deps": DEPS,
    "fix_outcomes": {
        "auth-service": {
            "disable_feature_flag": {"success": True,  "message": "Flag 'disable_token_cache' set FALSE. Token cache restored immediately. DB auth queries: 1,187/sec → 12/sec. Connection pool freed (10→2). auth-service p99: 12ms. api-gateway errors clearing. All services recovering.", "resolves": True,  "destructive": False},
            "restart":              {"success": False, "message": "auth-service restarted — BUT flag persists in config-service. Cache disabled again on startup. Thundering herd resumes in 5 seconds.", "resolves": False, "destructive": False},
            "rollback_deployment":  {"success": False, "message": "No recent auth-service deployment. Flag was changed by config-service, not a release. Rollback has no effect.", "resolves": False, "destructive": False},
            "increase_memory":      {"success": False, "message": "Memory is not the bottleneck — DB connections are. Thundering herd continues.", "resolves": False, "destructive": False},
        },
        "db-primary": {
            "restart":  {"success": False, "message": "DB restarted — backup stops (+25% CPU gone). But auth herd resumes on reconnect. CPU goes 87%→62% briefly then back to 87%.", "resolves": False, "destructive": True},
            "scale_up": {"success": False, "message": "Added read replicas. auth-service still hits primary for token validation. Herd unchanged.", "resolves": False, "destructive": False},
        },
        "default": {"success": False, "message": "Fix applied to wrong service. Feature flag still active. Thundering herd continues.", "resolves": False, "destructive": False},
    },
}

INCIDENTS = {1: TASK1, 2: TASK2, 3: TASK3}