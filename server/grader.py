"""
grader.py — Reward and scoring system

Reward breakdown (maximum total = 1.0):
  +0.05  investigated the initial alerting service
  +0.05  used check_deps to understand service topology
  +0.10  narrowed investigation to root cause service
  +0.15  identified root cause service via logs or metrics
  +0.20  identified root cause category (memory/database/feature_flag)
  +0.20  identified specific root cause
  +0.15  applied correct fix
  +0.05  efficiency bonus (resolved in <= 8 steps)
  +0.05  wrote a meaningful resolution summary
  ─────────────────────────────────────────────
  Maximum                                = 1.0

Penalties:
  -0.20  destructive action (made things worse)
  -0.05  redundant query (same action repeated)
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from models import SREState, SREAction


# ── Alerting service per task ────────────────────────────────────
ALERTING_SERVICE = {1: "order-service", 2: "api-gateway", 3: "api-gateway"}


def step_reward(state: SREState, action: SREAction, action_result: dict) -> float:
    """
    Called after every step.
    Awards partial credit for meaningful investigative actions.
    Returns reward float.
    """
    reward = 0.0

    # ── Redundancy penalty ────────────────────────────────────────
    cache_key = f"{action.action_type}:{action.service_name}:{action.metric_name}"
    if cache_key in state.query_cache and action.action_type not in ("close_incident", "apply_fix"):
        state.redundant_queries += 1
        return -0.05

    if action.action_type not in ("close_incident",):
        state.query_cache.append(cache_key)

    # ── Destructive action penalty ────────────────────────────────
    if action_result.get("destructive", False):
        state.destructive_actions += 1
        return -0.20

    # ── +0.05 investigated alerting service ──────────────────────
    if (
        not state.identified_alerting_service
        and action.action_type in ("query_logs", "query_metrics")
        and action.service_name == ALERTING_SERVICE.get(state.task_id, "")
    ):
        state.identified_alerting_service = True
        reward += 0.05

    # ── +0.05 used check_deps (shows topology understanding) ──────
    if (
        not getattr(state, "used_check_deps", False)
        and action.action_type == "check_deps"
    ):
        object.__setattr__(state, "used_check_deps", True) if hasattr(state, "__setattr__") else None
        try:
            state.query_cache.append("check_deps_bonus_claimed")
        except Exception:
            pass
        if "check_deps_bonus_claimed" not in state.query_cache[:-1]:
            reward += 0.05

    # ── +0.10 narrowed to root cause service ─────────────────────
    if (
        not state.narrowed_root_cause_service
        and action.action_type in ("query_logs", "query_metrics", "check_deps")
        and action.service_name == state.root_cause_service
    ):
        state.narrowed_root_cause_service = True
        reward += 0.10

    # ── +0.15 identified root cause service via its logs/metrics ─
    if (
        not state.correct_root_cause_category
        and action_result.get("reveals_category") == state.root_cause_category
        and action_result.get("reveals_category") is not None
        and action.service_name == state.root_cause_service
    ):
        state.correct_root_cause_category = True
        reward += 0.20

    # ── +0.20 identified specific root cause ─────────────────────
    if (
        not state.correct_root_cause_specific
        and action_result.get("reveals_specific") == state.root_cause_specific
        and action_result.get("reveals_specific") is not None
    ):
        state.correct_root_cause_specific = True
        reward += 0.20

    # ── +0.15 applied correct fix ────────────────────────────────
    if (
        not state.correct_fix_applied
        and action.action_type == "apply_fix"
        and action.service_name == state.root_cause_service
        and action.fix_type == state.correct_fix
    ):
        state.correct_fix_applied = True
        reward += 0.15

    # ── Near-miss partial credit for fix (+0.05) ─────────────────
    # Agent gets correct service but wrong fix type
    elif (
        not state.correct_fix_applied
        and action.action_type == "apply_fix"
        and action.service_name == state.root_cause_service
        and action.fix_type != state.correct_fix
        and "near_miss_fix_claimed" not in state.query_cache
    ):
        state.query_cache.append("near_miss_fix_claimed")
        reward += 0.03  # Small credit for finding correct service

    return round(reward, 3)


def episode_score(state: SREState) -> float:
    """
    Final episode score: 0.0 – 1.0

    Milestone scores:
      identified_alerting_service     = 0.05
      narrowed_root_cause_service     = 0.10
      correct_root_cause_category     = 0.20
      correct_root_cause_specific     = 0.20
      correct_fix_applied             = 0.15
      efficiency_bonus (<=8 steps)    = 0.05
      good_resolution_summary         = 0.05
      check_deps_used                 = 0.05
      ─────────────────────────────────────────
      max without penalties           = 0.85
      (remaining 0.15 from step rewards above)

    Penalties:
      destructive_action              = -0.20 each (max -0.40)
      redundant_query                 = -0.05 each (max -0.20)
    """
    score = 0.0

    if state.identified_alerting_service:    score += 0.05
    if state.narrowed_root_cause_service:    score += 0.10
    if state.correct_root_cause_category:    score += 0.20
    if state.correct_root_cause_specific:    score += 0.20
    if state.correct_fix_applied:            score += 0.15

    # Efficiency bonus
    if state.correct_fix_applied and state.step_count <= 8:
        score += 0.05

    # Good resolution summary bonus
    if state.done and state.correct_fix_applied:
        # Check if a non-trivial summary was provided (tracked via query_cache)
        if "good_summary_claimed" in state.query_cache:
            score += 0.05

    # check_deps usage bonus
    if "check_deps_bonus_claimed" in state.query_cache:
        score += 0.05

    # Near-miss fix credit
    if "near_miss_fix_claimed" in state.query_cache and not state.correct_fix_applied:
        score += 0.03

    # Penalties
    score -= min(state.destructive_actions * 0.20, 0.40)
    score -= min(state.redundant_queries   * 0.05, 0.20)

    return round(max(0.0, min(1.0, score)), 3)


def award_summary_bonus(state: SREState, summary: str) -> float:
    """
    Called when close_incident is invoked.
    Awards +0.05 if the resolution summary is meaningful (>20 chars and mentions service).
    """
    if (
        summary
        and len(summary) > 20
        and state.root_cause_service in summary.lower()
        and "good_summary_claimed" not in state.query_cache
    ):
        state.query_cache.append("good_summary_claimed")
        return 0.05
    return 0.0