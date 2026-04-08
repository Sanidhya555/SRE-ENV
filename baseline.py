"""
baseline.py — The baseline agent

Two agents:
  1. RuleBasedAgent — a hardcoded script that knows the right answers.
     Used for the /baseline endpoint to prove reproducible scores.

  2. run_openai_baseline() — uses the OpenAI API client to run a real
     LLM against all 3 tasks. Reads OPENAI_API_KEY from environment.

Expected baseline scores (rule-based):
  Task 1 (easy):   ~0.85  (correct, small efficiency bonus)
  Task 2 (medium): ~0.85
  Task 3 (hard):   ~0.85

Expected LLM baseline scores (GPT-4o, approximate):
  Task 1 (easy):   ~0.70
  Task 2 (medium): ~0.40
  Task 3 (hard):   ~0.15
"""

import os
import json
import requests

BASE_URL = os.getenv("ENV_BASE_URL", "http://localhost:8000")


# ─────────────────────────────────────────────────────────────────
# Rule-based agent (hardcoded correct paths)
# ─────────────────────────────────────────────────────────────────

RULE_BASED_SCRIPTS = {

    1: [   # Easy — Memory Leak
        {"action_type": "query_logs",    "service_name": "order-service"},
        {"action_type": "query_metrics", "service_name": "order-service", "metric_name": "memory"},
        {"action_type": "apply_fix",     "service_name": "order-service", "fix_type": "restart"},
        {"action_type": "close_incident","resolution_summary": "order-service had a memory leak causing OOMKill. Restarted the pod."}
    ],

    2: [   # Medium — Cascading Failure
        {"action_type": "query_logs",    "service_name": "api-gateway"},
        {"action_type": "check_deps",    "service_name": "api-gateway"},
        {"action_type": "query_logs",    "service_name": "payment-service"},
        {"action_type": "query_metrics", "service_name": "payment-service", "metric_name": "connections"},
        {"action_type": "query_logs",    "service_name": "db-primary"},
        {"action_type": "apply_fix",     "service_name": "payment-service", "fix_type": "rollback_deployment"},
        {"action_type": "close_incident","resolution_summary": "payment-service v2.4.1 introduced slow unindexed query exhausting DB pool. Rolled back."}
    ],

    3: [   # Hard — Red Herring Storm
        {"action_type": "query_logs",    "service_name": "db-primary"},
        {"action_type": "query_logs",    "service_name": "auth-service"},
        {"action_type": "query_metrics", "service_name": "auth-service", "metric_name": "connections"},
        {"action_type": "check_deps",    "service_name": "auth-service"},
        {"action_type": "apply_fix",     "service_name": "auth-service", "fix_type": "disable_feature_flag"},
        {"action_type": "close_incident","resolution_summary": "Feature flag 'disable_token_cache' caused thundering herd on db-primary. DB CPU spike was a red herring (backup). Disabled flag."}
    ]
}


def run_baseline() -> list[dict]:
    """
    Runs the rule-based agent on all 3 tasks.
    Returns list of result dicts, one per task.
    """
    results = []

    for task_id in [1, 2, 3]:
        # Start fresh
        reset_resp = requests.post(
            f"{BASE_URL}/reset",
            json={"task_id": task_id},
            timeout=10
        )
        reset_resp.raise_for_status()

        script = RULE_BASED_SCRIPTS[task_id]
        step_rewards = []
        final_info   = {}

        for action in script:
            step_resp = requests.post(
                f"{BASE_URL}/step",
                json=action,
                timeout=10
            )
            step_resp.raise_for_status()
            data = step_resp.json()
            step_rewards.append(data["reward"])
            final_info = data["info"]

            if data["done"]:
                break

        # Get grader score
        grader_resp = requests.get(f"{BASE_URL}/grader", timeout=10)
        grader_data = grader_resp.json()

        results.append({
            "task_id":       task_id,
            "difficulty":    ["", "easy", "medium", "hard"][task_id],
            "score":         grader_data.get("score", 0.0),
            "step_count":    grader_data.get("step_count", 0),
            "step_rewards":  step_rewards,
            "breakdown":     grader_data.get("breakdown", {}),
        })

    return results


# ─────────────────────────────────────────────────────────────────
# OpenAI LLM agent (for real baseline inference)
# ─────────────────────────────────────────────────────────────────

def run_openai_baseline(model: str = "gpt-4o") -> list[dict]:
    """
    Runs an LLM agent using the OpenAI API against all 3 tasks.
    Reads OPENAI_API_KEY from environment variables.
    """
    from openai import OpenAI

    client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
    results = []

    SYSTEM_PROMPT = """You are an expert Site Reliability Engineer (SRE).
You are connected to a production incident simulation environment.

You have these tools (actions you can take):
  query_logs     {service_name}                         - Read error logs for a service
  query_metrics  {service_name} {metric_name}           - Check CPU/memory/latency/error_rate/connections
  check_deps     {service_name}                         - See which services depend on which
  apply_fix      {service_name} {fix_type}              - Apply a remediation
  close_incident {resolution_summary}                   - Declare the incident resolved

Services: api-gateway, auth-service, order-service, payment-service, db-primary, notification-service
Fix types: restart, rollback_deployment, increase_memory, disable_feature_flag, scale_up, clear_cache

Always respond with a JSON action object. Example:
{"action_type": "query_logs", "service_name": "order-service"}

Be systematic: investigate first, then fix, then close.
"""

    for task_id in [1, 2, 3]:
        reset_resp = requests.post(
            f"{BASE_URL}/reset",
            json={"task_id": task_id},
            timeout=10
        )
        reset_resp.raise_for_status()
        obs = reset_resp.json()

        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user",   "content": (
                f"INCIDENT: {obs['task_description']}\n\n"
                f"Active alerts: {json.dumps(obs['active_alerts'], indent=2)}\n"
                f"Service health: {json.dumps(obs['service_health'], indent=2)}\n\n"
                "Investigate and resolve this incident. Respond with a JSON action."
            )}
        ]

        step_rewards = []
        max_steps = 15

        for _ in range(max_steps):
            # Ask the LLM for the next action
            response = client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=0.2,
                max_tokens=300
            )
            raw = response.choices[0].message.content.strip()

            # Parse the action JSON
            try:
                action_start = raw.find("{")
                action_end   = raw.rfind("}") + 1
                action_json  = json.loads(raw[action_start:action_end])
            except Exception:
                action_json = {"action_type": "close_incident", "resolution_summary": "Parse error"}

            # Execute the action
            step_resp = requests.post(f"{BASE_URL}/step", json=action_json, timeout=10)
            step_data = step_resp.json()
            step_rewards.append(step_data["reward"])

            # Add result to conversation
            messages.append({"role": "assistant", "content": raw})
            messages.append({"role": "user", "content": (
                f"Action result:\n{json.dumps(step_data['observation']['last_tool_result'], indent=2)}\n\n"
                f"Service health: {json.dumps(step_data['observation']['service_health'], indent=2)}\n"
                f"Step reward: {step_data['reward']}\n"
                f"Steps remaining: {step_data['observation']['slo_countdown']}\n\n"
                "Continue investigating. Respond with next JSON action."
            )})

            if step_data["done"]:
                break

        # Get final score
        grader_resp = requests.get(f"{BASE_URL}/grader", timeout=10)
        grader_data = grader_resp.json()

        results.append({
            "task_id":      task_id,
            "difficulty":   ["", "easy", "medium", "hard"][task_id],
            "model":        model,
            "score":        grader_data.get("score", 0.0),
            "step_count":   grader_data.get("step_count", 0),
            "step_rewards": step_rewards,
            "breakdown":    grader_data.get("breakdown", {}),
        })

    return results


# ─────────────────────────────────────────────────────────────────
# CLI entry point
# ─────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["rule", "openai"], default="rule")
    parser.add_argument("--model", default="gpt-4o")
    args = parser.parse_args()

    if args.mode == "openai":
        print("Running OpenAI LLM baseline...")
        results = run_openai_baseline(model=args.model)
    else:
        print("Running rule-based baseline...")
        results = run_baseline()

    print("\n── Baseline Results ─────────────────────────")
    for r in results:
        print(f"  Task {r['task_id']} ({r['difficulty']:6s}): score={r['score']:.3f}  steps={r['step_count']}")
    overall = sum(r["score"] for r in results) / len(results)
    print(f"\n  Average score: {overall:.3f}")