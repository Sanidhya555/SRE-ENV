"""
client.py — OpenEnv client for SRE Incident Response Environment

Usage:
    from client import SREEnvClient

    with SREEnvClient(base_url="http://localhost:8000") as client:
        obs = client.reset(task_id=1)
        result = client.step({"action_type": "query_logs", "service_name": "order-service"})
        print(result["reward"])
"""

import json
import requests
from typing import Optional


class SREEnvClient:
    """
    Synchronous HTTP client for the SRE Incident Response Environment.
    Implements the OpenEnv interface: reset(), step(), state().
    """

    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url.rstrip("/")
        self._session = requests.Session()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self._session.close()

    def reset(self, task_id: int = 1) -> dict:
        """Start a new episode. Returns initial observation."""
        resp = self._session.post(
            f"{self.base_url}/reset",
            json={"task_id": task_id},
            timeout=10,
        )
        resp.raise_for_status()
        return resp.json()

    def step(self, action: dict) -> dict:
        """
        Take one action. Returns dict with keys:
          observation, reward, done, info
        """
        resp = self._session.post(
            f"{self.base_url}/step",
            json=action,
            timeout=10,
        )
        resp.raise_for_status()
        return resp.json()

    def state(self) -> dict:
        """Returns current internal state."""
        resp = self._session.get(f"{self.base_url}/state", timeout=10)
        resp.raise_for_status()
        return resp.json()

    def grader(self) -> dict:
        """Returns current episode score and breakdown."""
        resp = self._session.get(f"{self.base_url}/grader", timeout=10)
        resp.raise_for_status()
        return resp.json()

    def tasks(self) -> dict:
        """Returns list of all tasks and the action schema."""
        resp = self._session.get(f"{self.base_url}/tasks", timeout=10)
        resp.raise_for_status()
        return resp.json()

    def health(self) -> dict:
        """Liveness check."""
        resp = self._session.get(f"{self.base_url}/health", timeout=10)
        resp.raise_for_status()
        return resp.json()


# ── Quick demo ────────────────────────────────────────────────────

if __name__ == "__main__":
    print("Connecting to SRE environment...")
    with SREEnvClient() as client:

        print(f"Health: {client.health()}")
        print(f"Tasks available: {[t['name'] for t in client.tasks()['tasks']]}\n")

        for task_id in [1, 2, 3]:
            obs = client.reset(task_id=task_id)
            print(f"Task {task_id}: {obs['task_description'][:80]}...")
            print(f"  Alerts: {len(obs['active_alerts'])} | Health: {obs['service_health']}\n")

        print("Client working correctly.")