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
  - agent
  - real-world
---

# SRE Incident Response Environment

An [OpenEnv](https://github.com/meta-pytorch/OpenEnv)-spec reinforcement learning environment where an AI agent practices diagnosing and resolving production incidents in a simulated 6-service microservices company.

> Built for the **OpenEnv Hackathon — Meta × Hugging Face × PyTorch**

---

## Why this environment?

Every company running software (Flipkart, Swiggy, Amazon) employs engineers called SREs whose job is to wake up at 3am, look at broken dashboards, and fix things before customers notice. Training an AI agent for this requires multi-step causal reasoning, tool use, and partial-progress rewards — making it a perfect RL challenge.

**No such open-source OpenEnv environment existed. This fills that gap.**

---

## Environment Description

**ProductionSim** simulates a company's microservices stack with 6 services:

| Service | Role |
|---|---|
| `api-gateway` | Entry point for all user requests |
| `auth-service` | Handles login and token validation |
| `order-service` | Manages customer orders |
| `payment-service` | Processes payments |
| `db-primary` | Central database |
| `notification-service` | Sends emails and SMS |

At the start of each episode a fault is secretly injected. The agent must investigate using tools, identify the root cause, apply the correct fix, and close the incident — all within 20 steps.

---

## Action Space

| action_type | Required fields | What it does |
|---|---|---|
| `query_logs` | `service_name` | Read error logs for a service |
| `query_metrics` | `service_name`, `metric_name` | Check CPU/memory/latency/error_rate/connections |
| `check_deps` | `service_name` | See which services call which |
| `apply_fix` | `service_name`, `fix_type` | Apply remediation |
| `close_incident` | `resolution_summary` | Declare incident resolved |

---

## Observation Space

| Field | Type | Description |
|---|---|---|
| `active_alerts` | list | Services currently alarming |
| `service_health` | dict | Health of all 6 services |
| `last_tool_result` | dict | Data from last query |
| `last_action_status` | str | success / failed / redundant |
| `investigation_history` | list | Breadcrumb of actions taken |
| `slo_countdown` | int | Steps before SLO breach |
| `step_count` | int | Current step number |
| `task_description` | str | Plain English incident description |

---

## The 3 Tasks

### Task 1 — Easy: Memory Leak
`order-service` repeatedly crashing. Root cause: OOM memory leak. Correct fix: `restart`.
Expected agent score: **~0.70**

### Task 2 — Medium: Cascading Failure
Slow checkout. Alert fires on `api-gateway` but root cause is 3 hops away — a bad DB query in `payment-service` v2.4.1 exhausting the connection pool. Correct fix: `rollback_deployment`.
Expected agent score: **~0.40**

### Task 3 — Hard: Red Herring Storm
Three alerts fire simultaneously. Two are distractions (scheduled DB backup, gateway errors). Real cause: a feature flag disabled token caching in `auth-service`, creating a thundering herd. Correct fix: `disable_feature_flag`.
Expected agent score: **~0.15**

---

## Reward Function

Rewards given step-by-step (not just at the end):

| Milestone | Reward |
|---|---|
| Investigated alerting service | +0.10 |
| Narrowed to root cause service | +0.15 |
| Identified root cause category | +0.20 |
| Identified specific root cause | +0.25 |
| Applied correct fix | +0.20 |
| Efficiency bonus (≤8 steps) | +0.10 |
| Destructive action | −0.20 |
| Redundant query | −0.05 |

**Final score always in [0.0, 1.0]**

---

## Baseline Scores

| Agent | Task 1 | Task 2 | Task 3 | Average |
|---|---|---|---|---|
| Rule-based (deterministic) | 0.85 | 0.85 | 0.85 | 0.85 |
| LLM — Llama 3.1 8B (approximate) | ~0.70 | ~0.40 | ~0.15 | ~0.42 |

---

## Setup & Usage

### Run locally

```bash
git clone https://huggingface.co/spaces/YOUR_USERNAME/sre-env
cd sre-env
pip install -r server/requirements.txt
uvicorn server.app:app --host 0.0.0.0 --port 8000
```

### Run with Docker

```bash
docker build -t sre-env .
docker run -p 8000:8000 sre-env
```

### Test it

```bash
# Health check
curl http://localhost:8000/health

# See all tasks
curl http://localhost:8000/tasks

# Start Task 1
curl -X POST http://localhost:8000/reset -H "Content-Type: application/json" -d '{"task_id": 1}'

# Take an action
curl -X POST http://localhost:8000/step -H "Content-Type: application/json" -d '{"action_type": "query_logs", "service_name": "order-service"}'

# Check score
curl http://localhost:8000/grader
```

### Run baseline

```bash
# Rule-based (no API key needed)
python baseline.py --mode rule

# LLM via HF Inference API
export HF_TOKEN=hf_your_token_here
python baseline.py --mode llm
```

### Use the client

```python
from client import SREEnvClient

with SREEnvClient(base_url="https://YOUR_SPACE.hf.space") as env:
    obs = env.reset(task_id=1)
    result = env.step({"action_type": "query_logs", "service_name": "order-service"})
    print(f"Reward: {result['reward']}")
```

---

## API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| GET | `/health` | Liveness check |
| POST | `/reset` | Start new episode |
| POST | `/step` | Take one action |
| GET | `/state` | Internal state |
| GET | `/tasks` | List tasks + schema |
| GET | `/grader` | Current score |
| POST | `/baseline` | Run baseline agent |
| WS | `/ws` | WebSocket interface |

Interactive docs: `http://localhost:8000/docs`

---

## License

BSD 3-Clause License