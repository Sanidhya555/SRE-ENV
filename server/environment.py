import uuid
import copy
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from models import SREAction, SREObservation, SREState, Alert
from server.incidents import INCIDENTS
from server.grader import step_reward, episode_score

MAX_STEPS = 20


class SREEnvironment:

    def __init__(self):
        self._state: SREState | None = None

    def reset(self, task_id: int = 1) -> SREObservation:
        task_id = int(task_id)
        if task_id not in INCIDENTS:
            task_id = 1

        incident = INCIDENTS[task_id]
        gt = incident["ground_truth"]

        self._state = SREState(
            episode_id             = str(uuid.uuid4()),
            step_count             = 0,
            task_id                = task_id,
            done                   = False,
            root_cause_service     = gt["root_cause_service"],
            root_cause_category    = gt["root_cause_category"],
            root_cause_specific    = gt["root_cause_specific"],
            correct_fix            = gt["correct_fix"],
        )

        alerts = [Alert(**a) for a in incident["initial_alerts"]]
        return SREObservation(
            active_alerts         = alerts,
            service_health        = copy.deepcopy(incident["service_health"]),
            last_tool_result      = None,
            last_action_status    = "none",
            investigation_history = [],
            slo_countdown         = MAX_STEPS,
            step_count            = 0,
            done                  = False,
            task_description      = incident["description"],
        )

    def step(self, action: SREAction):
        if self._state is None:
            raise RuntimeError("Call reset() before step()")
        if self._state.done:
            raise RuntimeError("Episode is already done. Call reset().")

        self._state.step_count += 1
        incident = INCIDENTS[self._state.task_id]

        tool_result, action_status, history_entry = self._execute_action(action, incident)
        reward = step_reward(self._state, action, tool_result)

        done = False
        if action.action_type == "close_incident":
            done = True
        if self._state.step_count >= MAX_STEPS:
            done = True
        self._state.done = done

        service_health = self._updated_service_health(incident, tool_result)

        observation = SREObservation(
            active_alerts         = self._current_alerts(incident, tool_result),
            service_health        = service_health,
            last_tool_result      = tool_result,
            last_action_status    = action_status,
            investigation_history = list(self._state.query_cache) + [history_entry],
            slo_countdown         = MAX_STEPS - self._state.step_count,
            step_count            = self._state.step_count,
            done                  = done,
            task_description      = incident["description"],
        )

        info = {
            "episode_score": episode_score(self._state) if done else None,
            "step_reward":   reward,
            "step_count":    self._state.step_count,
            "task_id":       self._state.task_id,
        }

        return observation, reward, done, info

    @property
    def state(self) -> SREState:
        if self._state is None:
            raise RuntimeError("Call reset() first.")
        return self._state

    # ── Private helpers ──────────────────────────────────────────

    def _execute_action(self, action: SREAction, incident: dict):
        atype   = action.action_type
        service = action.service_name or ""

        if atype == "query_logs":
            if service not in incident["logs"]:
                return {"error": f"Unknown service: {service}", "reveals_category": None, "reveals_specific": None}, "failed", f"query_logs({service}) → unknown service"
            log = incident["logs"][service]
            result = {
                "service":          service,
                "log_entries":      log["entries"],
                "summary":          log["summary"],
                "reveals_category": log.get("reveals_category"),
                "reveals_specific": log.get("reveals_specific"),
            }
            return result, "success", f"query_logs({service}) → {len(log['entries'])} entries"

        elif atype == "query_metrics":
            metric = action.metric_name or "cpu"
            if service not in incident["metrics"]:
                return {"error": f"No metrics for {service}", "reveals_category": None, "reveals_specific": None}, "failed", f"query_metrics({service}) → unknown service"
            svc_metrics = incident["metrics"][service]
            if metric not in svc_metrics:
                return {"error": f"No metric '{metric}' for {service}", "available_metrics": list(svc_metrics.keys()), "reveals_category": None, "reveals_specific": None}, "failed", f"query_metrics({service},{metric}) → not found"
            m = svc_metrics[metric]
            result = {
                "service":          service,
                "metric":           metric,
                "values":           m["values"],
                "unit":             m["unit"],
                "summary":          m["summary"],
                "reveals_category": m.get("reveals_category"),
                "reveals_specific": m.get("reveals_specific"),
            }
            return result, "success", f"query_metrics({service},{metric}) → {m['summary'][:60]}"

        elif atype == "check_deps":
            deps    = incident["deps"]
            if service not in deps:
                return {"error": f"Unknown service: {service}", "reveals_category": None, "reveals_specific": None}, "failed", f"check_deps({service}) → unknown"
            calls   = deps[service]
            callers = [s for s, d in deps.items() if service in d]
            result  = {"service": service, "calls": calls, "called_by": callers, "summary": f"{service} calls {calls}. Called by {callers}.", "reveals_category": None, "reveals_specific": None}
            return result, "success", f"check_deps({service}) → calls {calls}"

        elif atype == "apply_fix":
            fix_type = action.fix_type or "restart"
            outcomes = incident["fix_outcomes"]
            svc_out  = outcomes.get(service, outcomes.get("default", {}))
            outcome  = svc_out.get(fix_type, outcomes.get("default", {}))
            if not outcome:
                outcome = {"success": False, "message": "Unknown fix type.", "resolves": False, "destructive": False}
            result = {
                "service":          service,
                "fix_type":         fix_type,
                "success":          outcome["success"],
                "message":          outcome["message"],
                "resolves":         outcome.get("resolves", False),
                "destructive":      outcome.get("destructive", False),
                "reveals_category": None,
                "reveals_specific": None,
            }
            return result, "success", f"apply_fix({fix_type},{service}) → {outcome['message'][:60]}"

        elif atype == "close_incident":
            result = {
                "message":          "Incident closed.",
                "summary":          action.resolution_summary or "No summary provided.",
                "resolved":         self._state.correct_fix_applied,
                "reveals_category": None,
                "reveals_specific": None,
            }
            return result, "success", f"close_incident → resolved={self._state.correct_fix_applied}"

        else:
            return {"error": f"Unknown action_type: {atype}", "reveals_category": None, "reveals_specific": None}, "failed", f"Unknown action: {atype}"

    def _current_alerts(self, incident: dict, tool_result: dict) -> list[Alert]:
        if tool_result.get("resolves", False):
            return []
        return [Alert(**a) for a in incident["initial_alerts"]]

    def _updated_service_health(self, incident: dict, tool_result: dict) -> dict:
        health = copy.deepcopy(incident["service_health"])
        if tool_result.get("resolves", False):
            for svc in health:
                health[svc] = "healthy"
        return health