import json
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional

from models import SREAction, SREObservation, SREState
from server.environment import SREEnvironment
from server.grader import episode_score

app = FastAPI(title="SRE Incident Response Environment", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

env = SREEnvironment()


class ResetRequest(BaseModel):
    task_id: int = 1


class StepRequest(BaseModel):
    action_type: str
    service_name: Optional[str] = None
    metric_name: Optional[str] = None
    fix_type: Optional[str] = None
    resolution_summary: Optional[str] = None


@app.get("/")
def root():
    return {"message": "SRE Environment API is running"}

@app.get("/health")
def health():
    return {"status": "ok", "environment": "sre_env", "version": "1.0.0"}


@app.post("/reset")
def reset(req: ResetRequest = None):
    task_id = req.task_id if req else 1
    obs = env.reset(task_id=task_id)
    return obs.model_dump()


@app.post("/step")
def step(req: StepRequest):
    action = SREAction(
        action_type        = req.action_type,
        service_name       = req.service_name,
        metric_name        = req.metric_name,
        fix_type           = req.fix_type,
        resolution_summary = req.resolution_summary,
    )
    observation, reward, done, info = env.step(action)
    return {
        "observation": observation.model_dump(),
        "reward": reward,
        "done": done,
        "info": info,
    }


@app.get("/state")
def state():
    try:
        return env.state.model_dump()
    except RuntimeError:
        return {"error": "No active episode. Call /reset first."}


@app.get("/tasks")
def tasks():
    return {
        "tasks": [
            {"task_id": 1, "difficulty": "easy",   "name": "Memory Leak",         "description": "order-service crashing due to OOM memory leak."},
            {"task_id": 2, "difficulty": "medium",  "name": "Cascading Failure",   "description": "Slow checkout caused by bad DB query in recent deployment."},
            {"task_id": 3, "difficulty": "hard",    "name": "Red Herring Storm",   "description": "Multiple alerts — 2 fake, 1 real hidden feature flag issue."},
        ],
        "action_schema": {
            "action_type":        {"type": "string", "required": True, "options": ["query_logs", "query_metrics", "check_deps", "apply_fix", "close_incident"]},
            "service_name":       {"type": "string", "options": ["api-gateway", "auth-service", "order-service", "payment-service", "db-primary", "notification-service"]},
            "metric_name":        {"type": "string", "options": ["cpu", "memory", "latency", "error_rate", "connections"]},
            "fix_type":           {"type": "string", "options": ["restart", "rollback_deployment", "increase_memory", "disable_feature_flag", "scale_up", "clear_cache"]},
            "resolution_summary": {"type": "string"},
        },
    }


@app.get("/grader")
def grader():
    try:
        s = env.state
        score = episode_score(s)
        return {
            "episode_id": s.episode_id,
            "task_id":    s.task_id,
            "score":      score,
            "done":       s.done,
            "step_count": s.step_count,
            "breakdown": {
                "identified_alerting_service": s.identified_alerting_service,
                "narrowed_root_cause_service": s.narrowed_root_cause_service,
                "correct_root_cause_category": s.correct_root_cause_category,
                "correct_root_cause_specific": s.correct_root_cause_specific,
                "correct_fix_applied":         s.correct_fix_applied,
                "efficiency_bonus":            s.correct_fix_applied and s.step_count <= 8,
                "destructive_actions":         s.destructive_actions,
                "redundant_queries":           s.redundant_queries,
            },
        }
    except RuntimeError:
        return {"error": "No active episode. Call /reset first."}


@app.post("/baseline")
def baseline():
    sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
    from baseline import run_baseline
    results = run_baseline()
    return {"baseline_results": results}


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            raw = await websocket.receive_text()
            msg = json.loads(raw)
            method = msg.get("method")
            params = msg.get("params", {})

            if method == "reset":
                obs = env.reset(task_id=params.get("task_id", 1))
                await websocket.send_text(json.dumps({"type": "reset", "observation": obs.model_dump()}))

            elif method == "step":
                action = SREAction(**params)
                observation, reward, done, info = env.step(action)
                await websocket.send_text(json.dumps({"type": "step", "observation": observation.model_dump(), "reward": reward, "done": done, "info": info}))

            elif method == "state":
                try:
                    await websocket.send_text(json.dumps({"type": "state", "state": env.state.model_dump()}))
                except RuntimeError as e:
                    await websocket.send_text(json.dumps({"type": "error", "message": str(e)}))

            else:
                await websocket.send_text(json.dumps({"type": "error", "message": f"Unknown method: {method}"}))

    except WebSocketDisconnect:
        pass
    except Exception as e:
        try:
            await websocket.send_text(json.dumps({"type": "error", "message": str(e)}))
        except Exception:
            pass

def main():
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

if __name__ == "__main__":
    main()