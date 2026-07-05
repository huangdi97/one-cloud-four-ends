"""合并的记忆杂项路由：记忆整合、Token预算管理。"""

from typing import Any, Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from cloud.app.services.agent_ops.token_budget_service import TokenBudgetService
from cloud.app.services.brain.memory_consolidation_service import MemoryConsolidationService
from shared.auth_scope import require_scope
from shared.base import success

# ── memory_consolidation_router ───────────────────────────────────────

consolidation_router = APIRouter(prefix="/memory/consolidation", tags=["记忆系统"])


class MemoryEvaluateRequest(BaseModel):
    agent_id: str


@consolidation_router.post("/trigger", tags=["记忆系统"])
def trigger_consolidation(
    current_user=Depends(require_scope("visit")),
    service: MemoryConsolidationService = Depends(),
):
    result = service.trigger_consolidation(
        triggered_by=current_user.get("sub", ""),
    )
    return success(data=result)


@consolidation_router.get("/status", tags=["记忆系统"])
def consolidation_status(
    current_user=Depends(require_scope("visit")),
    service: MemoryConsolidationService = Depends(),
):
    return success(data=service.consolidation_status())


@consolidation_router.post("/evaluate", tags=["记忆系统"])
def evaluate_memory(
    body: MemoryEvaluateRequest,
    current_user=Depends(require_scope("visit")),
    service: MemoryConsolidationService = Depends(),
):
    return success(data=service.evaluate_memory(agent_id=body.agent_id))


@consolidation_router.get("/evaluate/trend", tags=["记忆系统"])
def evaluate_trend(
    current_user=Depends(require_scope("visit")),
    service: MemoryConsolidationService = Depends(),
):
    return success(data=service.evaluate_trend())


# ── token_budget_router ───────────────────────────────────────────────

token_budget_router = APIRouter(prefix="/admin/tokens", tags=["Token 管理"])


class UpdateBudgetRequest(BaseModel):
    model: str
    max_tokens_per_day: Optional[int] = None
    max_tokens_per_request: Optional[int] = None
    alert_threshold: Optional[float] = None


@token_budget_router.get("/budget/{user_id}", tags=["Token 管理"])
def get_budget(
    user_id: int,
    model: str = Query("deepseek-v4-pro", description="模型名称"),
    service: TokenBudgetService = Depends(),
) -> Any:
    return success(data=service.get_budget(user_id, model))


@token_budget_router.put("/budget/{user_id}", tags=["Token 管理"])
def update_budget(
    user_id: int,
    body: UpdateBudgetRequest,
    _: dict = Depends(require_scope("visit")),
    service: TokenBudgetService = Depends(),
) -> Any:
    data = service.update_budget(
        user_id=user_id,
        model=body.model,
        max_tokens_per_day=body.max_tokens_per_day,
        max_tokens_per_request=body.max_tokens_per_request,
        alert_threshold=body.alert_threshold,
    )
    return success(data=data)


@token_budget_router.get("/usage/{user_id}", tags=["Token 管理"])
def get_usage_report(
    user_id: int,
    days: int = Query(30, ge=1, le=365, description="回溯天数"),
    service: TokenBudgetService = Depends(),
) -> Any:
    return success(data=service.get_usage_report(user_id, days))


@token_budget_router.get("/alerts", tags=["Token 管理"])
def list_alerts(
    service: TokenBudgetService = Depends(),
) -> Any:
    return success(data=service.get_alerts())


# ── top-level aggregator router ───────────────────────────────────────

router = APIRouter()
router.include_router(consolidation_router)
router.include_router(token_budget_router)

__all__ = [
    "router",
    "consolidation_router",
    "token_budget_router",
    "MemoryEvaluateRequest",
    "UpdateBudgetRequest",
]
