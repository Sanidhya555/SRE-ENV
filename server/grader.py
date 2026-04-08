import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from models import SREState, SREAction


def step_reward(state: SREState, action: SREAction, action_result: dict) -> float:
    reward = 0.0

    # Redundancy penalty
    cache_key = f"{action.action_type}:{action.service_name}"
    if cache_key in state.query_cache and action.action_type != "close_incident":
        state.redundant_queries += 1
        return -0.05

    if action.action_type != "close_incident":
        state.query_cache.append(cache_key)

    # Destructive action penalty
    if action_result.get("destructive", False):
        state.destructive_actions += 1
        return -0.20

    # +0.10 investigated the alerting service
    alerting = {1: "order-service", 2: "api-gateway", 3: "api-gateway"}
    if (
        not state.identified_alerting_service
        and action.action_type in ("query_logs", "query_metrics")
        and action.service_name == alerting.get(state.task_id, "")
    ):
        state.identified_alerting_service = True
        reward += 0.10

    # +0.15 narrowed to root cause service
    if (
        not state.narrowed_root_cause_service
        and action.action_type in ("query_logs", "query_metrics", "check_deps")
        and action.service_name == state.root_cause_service
    ):
        state.narrowed_root_cause_service = True
        reward += 0.15

    # +0.20 identified root cause category
    if (
        not state.correct_root_cause_category
        and action_result.get("reveals_category") == state.root_cause_category
        and action_result.get("reveals_category") is not None
    ):
        state.correct_root_cause_category = True
        reward += 0.20

    # +0.25 identified specific root cause
    if (
        not state.correct_root_cause_specific
        and action_result.get("reveals_specific") == state.root_cause_specific
        and action_result.get("reveals_specific") is not None
    ):
        state.correct_root_cause_specific = True
        reward += 0.25

    # +0.20 correct fix applied
    if (
        not state.correct_fix_applied
        and action.action_type == "apply_fix"
        and action.service_name == state.root_cause_service
        and action.fix_type == state.correct_fix
    ):
        state.correct_fix_applied = True
        reward += 0.20

    return round(reward, 3)


def episode_score(state: SREState) -> float:
    score = 0.0
    if state.identified_alerting_service:   score += 0.10
    if state.narrowed_root_cause_service:   score += 0.15
    if state.correct_root_cause_category:   score += 0.20
    if state.correct_root_cause_specific:   score += 0.25
    if state.correct_fix_applied:           score += 0.20
    if state.correct_fix_applied and state.step_count <= 8:
        score += 0.10

    score -= min(state.destructive_actions * 0.20, 0.40)
    score -= min(state.redundant_queries   * 0.05, 0.20)
    return round(max(0.0, min(1.0, score)), 3)