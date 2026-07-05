"""Agent 健康监控路由 — 暴露每个Agent的健康状态和聚合摘要。"""

from fastapi import APIRouter, Query

from cloud.app.services.agent_ops.agent_health_service import get_health_tracker
from shared.base import success

router = APIRouter(prefix="/agent", tags=["Agent Health"])


@router.get("/health")
def list_agent_health(agent_name: str | None = Query(None, description="Filter by agent name")):
    tracker = get_health_tracker()
    if agent_name:
        data = tracker.get_health(agent_name)
    else:
        agents = tracker.get_all_health()
        summary = tracker.get_summary()
        data = {"agents": agents, "summary": summary}
    return success(data=data)
