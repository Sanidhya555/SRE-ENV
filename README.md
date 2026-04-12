---
title: SRE Incident Response Environment
emoji: 🚨
colorFrom: red
colorTo: blue
sdk: docker
pinned: true
tags:
  - openenv
  - reinforcement-learning
  - sre
  - devops
  - real-world
  - agent
  - incident-response
---

# 🚨 SRE Incident Response Environment

> An [OpenEnv](https://github.com/meta-pytorch/OpenEnv)-spec reinforcement learning environment where an AI agent acts as an on-call Site Reliability Engineer — diagnosing and resolving production incidents in a simulated 6-service microservices company.

**Built for the OpenEnv Hackathon — Meta × Hugging Face × PyTorch**

---

## Why This Environment?

Every company running software at scale (Flipkart, Swiggy, Zepto, Amazon) employs engineers called **SREs** whose job is to respond to production incidents — often at 3am, under pressure, with incomplete information.

Training an AI agent to do this well requires:
- **Multi-step causal reasoning** — surface alerts rarely show the root cause
- **Tool use under uncertainty** — the agent must decide what to investigate
- **Red herring resistance** — some alerts are distractions
- **Partial progress rewards** — each investigative step should provide signal

**No open-source OpenEnv environment existed for this domain. This fills that gap.**

---

## Environment Overview

**ProductionSim** simulates a realistic microservices company with 6 services:

| Service | Role |
|---|---|
| `api-gateway` | Entry point — routes all user requests |
| `auth-service` | Handles login and JWT token validation |
| `order-service` | Manages customer orders |
| `payment-service` | Processes payments |
| `db-primary` | Central PostgreSQL database |
| `notification-service` | Sends emails and SMS |

At the start of each episode, a fault is secretly injected. The agent must investigate using tools, identify the root cause, apply the correct fix, and close the incident — all within 20 steps.

---

## Action Space

The agent has 5 action types:

| action_type | Required fields | What it does |
|---|---|---|
| `query_logs` | `service_name` | Read structured error logs for a service |
| `query_metrics` | `service_name`, `metric_name` | Read time-series metrics (cpu/memory/latency/error_rate/connections) |
| `check_deps` | `service_name` | See which services call which (dependency map) |
| `apply_fix` | `service_name`, `fix_type` | Apply a remediation action |
| `close_incident` | `resolution_summary` | Declare the incident resolved with explanation |

**Available services:** `api-gateway` · `auth-service` · `order-service` · `payment-service` · `db-primary` · `notification-service`

**Available metrics:** `cpu` · `memory` · `latency` · `error_rate` · `connections`

**Available fix types:** `restart` · `rollback_deployment` · `increase_memory` · `disable_feature_flag` · `scale_up` · `clear_cache`

---

## Observation Space

After every action the agent receives a structured observation:

| Field | Type | Description |
|---|---|---|
| `active_alerts` | `list[Alert]` | Currently firing alarms with service, metric, severity, message |
| `service_health` | `dict[str, str]` | Health of all 6 services: `healthy` / `degraded` / `down` |
| `last_tool_result` | `dict` | Full data returned by the last query action |
| `last_action_status` | `str` | `success` / `failed` / `redundant` |
| `investigation_history` | `list[str]` | Breadcrumb trail of every action taken this episode |
| `slo_countdown` | `int` | Steps remaining before automatic SLO breach penalty |
| `step_count` | `int` | Current step number |
| `done` | `bool` | Whether the episode has ended |
| `task_description` | `str` | Plain English description of the incident |

---

## The 3 Tasks

### Task 1 — Easy: Memory Leak 🟢

**Scenario:** `order-service` is repeatedly crashing and restarting. Customers cannot place orders.

**Root cause:** An unbounded `SessionCache` with no TTL or eviction policy. Memory grows linearly until Kubernetes OOMKills the container every ~20 minutes.

**Evidence trail:**
- Logs show `OOMKilled`, `Java heap space`, `GC overhead limit exceeded`
- Memory metrics show classic sawtooth: 41% → 98% → crash → reset → repeat
- SessionCache has `847,293 entries` with no eviction

**Correct fix:** `restart` on `order-service`

**Expected score (frontier LLM):** ~0.70

---

### Task 2 — Medium: Cascading Failure 🟡

**Scenario:** Checkout is extremely slow (15-30 seconds). Alert fires on `api-gateway` — but that's not the root cause.

**Root cause:** `payment-service` v2.4.1 added `getUserTransactionHistory()` to the payment flow — a query that does a full sequential scan on 4.2M rows with no index on `user_id`. Each payment holds a DB connection for 6-8 seconds, exhausting the connection pool (10/10), cascading to timeouts across checkout.

**Evidence trail:**
- api-gateway logs: latency spike started at 03:10 — matches payment-service v2.4.1 deploy timestamp
- payment-service logs: `DB connection pool EXHAUSTED`, `Seq Scan on transactions — 4,218,492 rows`
- db-primary logs: `MISSING INDEX: CREATE INDEX idx_transactions_user_id ON transactions(user_id)`
- connections metric: payment-service DB pool 2 → 10 (maxed) and stays there

**Correct fix:** `rollback_deployment` on `payment-service`

**Expected score (frontier LLM):** ~0.40

---

### Task 3 — Hard: Red Herring Storm 🔴

**Scenario:** Three critical alerts fire simultaneously within 30 seconds. Two are distractions.

**Alerts:**
1. `auth-service` p99 latency 8,200ms ← **real cascade victim**
2. `db-primary` CPU 87% ← **partially a red herring** (scheduled backup + thundering herd)
3. `api-gateway` 5xx rate 34% ← **pure red herring** (downstream of auth-service)

**Root cause:** Feature flag `disable_token_cache` was set to `TRUE` at 03:59:58 by a config-service auto-deploy ("security audit mode"). This bypassed auth-service's in-memory JWT cache. Every one of 1,240 auth requests/min now hits db-primary directly — a thundering herd (100x normal load). DB connection pool exhausts in seconds.

**Red herrings:**
- DB CPU spike looks alarming but is partly from a scheduled 6-hour backup (normal)
- api-gateway errors are purely downstream — fixing api-gateway does nothing
- Restarting auth-service does not help — the flag persists in config-service

**Correct fix:** `disable_feature_flag` on `auth-service`

**Expected score (frontier LLM):** ~0.15

---

## Reward Function

Rewards are given **step by step** throughout the episode — not just at the end:

| Milestone | Reward | When earned |
|---|---|---|
| Investigated alerting service | +0.05 | First `query_logs`/`query_metrics` on alerting service |
| Used `check_deps` | +0.05 | Any `check_deps` call (shows topology understanding) |
| Narrowed to root cause service | +0.10 | Any investigation of root cause service |
| Identified root cause category | +0.20 | Logs/metrics that reveal category (memory/database/feature_flag) |
| Identified specific root cause | +0.20 | Logs/metrics that reveal exact cause |
| Applied correct fix | +0.15 | `apply_fix` with correct service + fix type |
| Efficiency bonus | +0.05 | Resolved in ≤ 8 steps |
| Meaningful resolution summary | +0.05 | `close_incident` with informative summary |
| Near-miss fix | +0.03 | Correct service but wrong fix type |
| **Destructive action** | **−0.20** | Fix that worsens the incident |
| **Redundant query** | **−0.05** | Same query called twice |

**Final score is always in [0.0, 1.0]**

---

## Baseline Scores

| Agent | Task 1 (easy) | Task 2 (medium) | Task 3 (hard) | Average |
|---|---|---|---|---|
| Rule-based (deterministic) | 0.85 | 0.85 | 0.85 | **0.85** |
| GPT-4o (approximate) | ~0.70 | ~0.40 | ~0.15 | ~0.42 |
| Llama 3.1 8B (approximate) | ~0.55 | ~0.25 | ~0.10 | ~0.30 |

---

## Setup & Usage

### Run locally

```bash
git clone https://github.com/Sanidhya555/SRE-ENV
cd SRE-ENV
pip install -r server/requirements.txt
uvicorn server.app:app --host 0.0.0.0 --port 7860
```

### Run with Docker

```bash
docker build -t sre-env .
docker run -p 7860:7860 sre-env
```

### Test it

```bash
# Health check
curl http://localhost:7860/health

# Interactive API docs
open http://localhost:7860/docs

# Start Task 1
curl -X POST http://localhost:7860/reset -H "Content-Type: application/json" -d '{"task_id": 1}'

# Take an action
curl -X POST http://localhost:7860/step -H "Content-Type: application/json" \
  -d '{"action_type": "query_logs", "service_name": "order-service"}'

# Check score
curl http://localhost:7860/grader
```

### Run baseline inference

```bash
# Rule-based (no token needed)
python inference.py --mode rule

# LLM via HF Inference API
export HF_TOKEN=hf_your_token_here
python inference.py --mode llm --model meta-llama/Llama-3.1-8B-Instruct
```

### Use the Python client

```python
from client import SREEnvClient

with SREEnvClient(base_url="https://Sanidhya555-sre-env.hf.space") as env:
    obs = env.reset(task_id=1)
    print(obs["task_description"])

    result = env.step({
        "action_type": "query_logs",
        "service_name": "order-service"
    })
    print(f"Reward: {result['reward']}")
    print(f"Logs: {result['observation']['last_tool_result']['log_entries']}")
```

---

## API Reference

| Method | Endpoint | Description |
|---|---|---|
| GET | `/health` | Liveness check — returns `{"status": "ok"}` |
| POST | `/reset` | Start new episode — body: `{"task_id": 1}` |
| POST | `/step` | Take one action — body: SREAction JSON |
| GET | `/state` | Current internal state |
| GET | `/tasks` | List all tasks + full action schema |
| GET | `/grader` | Current episode score with breakdown |
| POST | `/baseline` | Run rule-based baseline on all 3 tasks |
| WS | `/ws` | WebSocket interface for OpenEnv clients |

---

## Project Structure

```
sre-env/
├── Dockerfile              ← Container definition (root, required for HF Spaces)
├── README.md               ← This file
├── openenv.yaml            ← OpenEnv spec metadata
├── models.py               ← Pydantic models: SREAction, SREObservation, SREState
├── client.py               ← Python client for connecting to the environment
├── baseline.py             ← Baseline agent (rule-based + LLM via HF API)
├── inference.py            ← Required inference script (reads HF_TOKEN)
├── pyproject.toml          ← Package definition
└── server/
    ├── app.py              ← FastAPI server with all endpoints
    ├── environment.py      ← Core game engine (reset/step/state)
    ├── grader.py           ← Reward function and episode scoring
    ├── incidents.py        ← 3 incident scenarios with logs, metrics, ground truth
    └── requirements.txt    ← Python dependencies
```

---

## License

BSD 3-Clause License