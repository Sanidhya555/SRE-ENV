from typing import Optional
from pydantic import BaseModel, Field


class SREAction(BaseModel):
    action_type: str = Field(..., description="query_logs | query_metrics | check_deps | apply_fix | close_incident")
    service_name: Optional[str] = Field(None)
    metric_name: Optional[str] = Field(None)
    fix_type: Optional[str] = Field(None)
    resolution_summary: Optional[str] = Field(None)


class Alert(BaseModel):
    service: str
    metric: str
    severity: str
    message: str


class SREObservation(BaseModel):
    active_alerts: list[Alert] = Field(default_factory=list)
    service_health: dict[str, str] = Field(default_factory=dict)
    last_tool_result: Optional[dict] = Field(None)
    last_action_status: str = Field("none")
    investigation_history: list[str] = Field(default_factory=list)
    slo_countdown: int = Field(20)
    step_count: int = Field(0)
    done: bool = Field(False)
    task_description: str = Field("")


class SREState(BaseModel):
    episode_id: str
    step_count: int = 0
    task_id: int = 1
    done: bool = False
    root_cause_service: str = ""
    root_cause_category: str = ""
    root_cause_specific: str = ""
    correct_fix: str = ""
    identified_alerting_service: bool = False
    narrowed_root_cause_service: bool = False
    correct_root_cause_category: bool = False
    correct_root_cause_specific: bool = False
    correct_fix_applied: bool = False
    destructive_actions: int = 0
    redundant_queries: int = 0
    query_cache: list[str] = Field(default_factory=list)