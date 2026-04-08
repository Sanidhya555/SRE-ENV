"""
baseline.py — Baseline inference script

Uses the OpenAI-compatible Hugging Face Inference API.
Reads HF_TOKEN from environment variables (as required by the hackathon spec).

Usage:
  # Rule-based agent (deterministic, no API key needed)
  python baseline.py --mode rule

  # LLM agent via HF Inference API
  export HF_TOKEN=hf_your_token_here
  python baseline.py --mode llm
"""

import os
import json
import requests

BASE_URL = os.getenv("ENV_BASE_URL", "http://localhost:8000")

SCRIPTS = {
    1: [
        {"action_type": "query_logs",    "service_name": "order-service"},
        {"action_type": "query_metrics", "service_name": "order-service",  "metric_name": "memory"},
        {"action_type": "apply_fix",     "service_name": "order-service",  "fix_type": "restart"},
        {"action_type": "close_incident","resolution_summary": "OOM memory leak in order-service — restarted pod."},
    ],
    2: [
        {"action_type": "query_logs",    "service_name": "api-gateway"},
        {"action_type": "check_deps",    "service_name": "api-gateway"},
        {"action_type": "query_logs",    "service_name": "payment-service"},
        {"action_type": "query_metrics", "service_name": "payment-service", "metric_name": "connections"},
        {"action_type": "apply_fix",     "service_name": "payment-service", "fix_type": "rollback_deployment"},
        {"action_type": "close_incident","resolution_summary": "payment-service v2.4.1 bad query exhausted DB pool — rolled back."},
    ],
    3: [
        {"action_type": "query_logs",    "service_name": "db-primary"},
        {"action_type": "query_logs",    "service_name": "auth-service"},
        {"action_type": "query_metrics", "service_name": "auth-service",   "metric_name": "connections"},
        {"action_type": "apply_fix",     "service_name": "auth-service",   "fix_type": "disable_feature_flag"},
        {"action_type": "close_incident","resolution_summary": "disable_token_cache flag caused thundering herd. Disabled flag."},
    ],
}


def run_baseline() -> list[dict]:
    """Rule-based deterministic agent. Same result every run."""
    results = []
    for task_id in [1, 2, 3]:
        requests.post(f"{BASE_URL}/reset", json={"task_id": task_id}, timeout=10).raise_for_status()
        step_rewards = []
        for action in SCRIPTS[task_id]:
            resp = requests.post(f"{BASE_URL}/step", json=action, timeout=10)
            resp.raise_for_status()
            data = resp.json()
            step_rewards.append(data["reward"])
            if data["done"]:
                break
        grader = requests.get(f"{BASE_URL}/grader", timeout=10).json()
        results.append({
            "task_id":      task_id,
            "difficulty":   ["", "easy", "medium", "hard"][task_id],
            "agent":        "rule-based",
            "score":        grader.get("score", 0.0),
            "step_count":   grader.get("step_count", 0),
            "step_rewards": step_rewards,
            "breakdown":    grader.get("breakdown", {}),
        })
    return results


def run_llm_baseline(model: str = "meta-llama/Llama-3.1-8B-Instruct") -> list[dict]:
    """LLM agent via HF Inference API. Reads HF_TOKEN from environment."""
    hf_token = os.environ.get("HF_TOKEN")
    if not hf_token:
        raise ValueError("HF_TOKEN not set. Run: export HF_TOKEN=hf_...")

    from openai import OpenAI
    client = OpenAI(
        base_url="https://api-inference.huggingface.co/v1/",
        api_key=hf_token,
    )

    SYSTEM = """You are an expert SRE responding to production incidents.
Respond ONLY with a valid JSON action object. Available actions:
  {"action_type": "query_logs",    "service_name": "<service>"}
  {"action_type": "query_metrics", "service_name": "<service>", "metric_name": "<metric>"}
  {"action_type": "check_deps",    "service_name": "<service>"}
  {"action_type": "apply_fix",     "service_name": "<service>", "fix_type": "<fix>"}
  {"action_type": "close_incident","resolution_summary": "<text>"}
Services: api-gateway, auth-service, order-service, payment-service, db-primary, notification-service
Metrics:  cpu, memory, latency, error_rate, connections
Fixes:    restart, rollback_deployment, increase_memory, disable_feature_flag, scale_up, clear_cache"""

    results = []
    for task_id in [1, 2, 3]:
        obs = requests.post(f"{BASE_URL}/reset", json={"task_id": task_id}, timeout=10).json()
        messages = [
            {"role": "system", "content": SYSTEM},
            {"role": "user",   "content": f"INCIDENT: {obs['task_description']}\nAlerts: {json.dumps(obs['active_alerts'])}\nHealth: {json.dumps(obs['service_health'])}\nRespond with JSON action."},
        ]
        step_rewards = []
        for _ in range(15):
            raw = client.chat.completions.create(model=model, messages=messages, temperature=0.2, max_tokens=150).choices[0].message.content.strip()
            try:
                action_json = json.loads(raw[raw.find("{"):raw.rfind("}")+1])
            except Exception:
                action_json = {"action_type": "close_incident", "resolution_summary": "parse error"}
            data = requests.post(f"{BASE_URL}/step", json=action_json, timeout=10).json()
            step_rewards.append(data["reward"])
            messages += [
                {"role": "assistant", "content": raw},
                {"role": "user",      "content": f"Result: {json.dumps(data['observation']['last_tool_result'])}\nHealth: {json.dumps(data['observation']['service_health'])}\nReward: {data['reward']} Steps left: {data['observation']['slo_countdown']}\nNext action?"},
            ]
            if data["done"]:
                break
        grader = requests.get(f"{BASE_URL}/grader", timeout=10).json()
        results.append({"task_id": task_id, "difficulty": ["","easy","medium","hard"][task_id], "agent": model, "score": grader.get("score", 0.0), "step_count": grader.get("step_count", 0), "step_rewards": step_rewards, "breakdown": grader.get("breakdown", {})})
    return results


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode",  choices=["rule", "llm"], default="rule")
    parser.add_argument("--model", default="meta-llama/Llama-3.1-8B-Instruct")
    args = parser.parse_args()

    results = run_llm_baseline(args.model) if args.mode == "llm" else run_baseline()

    print("\n" + "━"*50)
    for r in results:
        print(f"  Task {r['task_id']} ({r['difficulty']:<6}): score={r['score']:.3f}  steps={r['step_count']}")
    print(f"  Average: {sum(r['score'] for r in results)/len(results):.3f}")
    print("━"*50)