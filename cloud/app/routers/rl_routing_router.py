"""强化学习路由分发。"""

from typing import Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from starlette import status

from cloud.app.services.brain.rl_routing_service import RLRoutingService
from shared.auth_scope import require_scope
from shared.base import success

router = APIRouter(prefix="/routing", tags=["RL路由"])


class RouteRequest(BaseModel):
    """RouteRequest 服务类。"""

    task_type: str = Field(..., min_length=1, max_length=100)
    task_content: str = ""
    source: str = "api"


class ParetoRouteRequest(BaseModel):
    """ParetoRouteRequest 服务类。"""

    task_type: str = Field(..., min_length=1, max_length=100)
    task_content: str = ""
    constraints: dict = {}


class LogRequest(BaseModel):
    """LogRequest 服务类。"""

    task_id: str = Field(..., min_length=1, max_length=100)
    task_type: str = ""
    source: str = ""
    strategy_used: str = ""
    routed_to: str = ""
    duration_ms: int = 0
    success: int = 0


@router.post("/route", summary="Route Task", tags=["RL路由"])
def route_task(
    body: RouteRequest,
    current_user: dict = Depends(require_scope("visit")),
    service: RLRoutingService = Depends(),
) -> Any:
    """route_task 操作。

    Args:
        current_user: 描述
        service: 描述

    Returns:
        描述
    """
    result = service.route_task(
        task_type=body.task_type,
        task_content=body.task_content,
        source=body.source,
    )
    return success(data=result)


@router.post("/pareto-route", summary="Pareto Route", tags=["RL路由"])
def pareto_route(
    body: ParetoRouteRequest,
    current_user: dict = Depends(require_scope("visit")),
    service: RLRoutingService = Depends(),
) -> Any:
    """pareto_route 操作。

    Args:
        current_user: 描述
        service: 描述

    Returns:
        描述
    """
    result = service.pareto_route(
        task_type=body.task_type,
        task_content=body.task_content,
        constraints=body.constraints or None,
    )
    return success(data=result)


@router.post("/log", status_code=status.HTTP_201_CREATED, summary="Log Result", tags=["RL路由"])
def log_result(
    body: LogRequest,
    current_user: dict = Depends(require_scope("visit")),
    service: RLRoutingService = Depends(),
) -> Any:
    """log_result 操作。

    Args:
        current_user: 描述
        service: 描述

    Returns:
        描述
    """
    result = service.log_result(
        task_id=body.task_id,
        task_type=body.task_type,
        source=body.source,
        strategy_used=body.strategy_used,
        routed_to=body.routed_to,
        duration_ms=body.duration_ms,
        success=body.success,
    )
    return success(data=result)


@router.get("/stats", summary="Get Stats by ID", tags=["RL路由"])
def get_stats(
    task_type: str = Query(None),
    current_user: dict = Depends(require_scope("visit")),
    service: RLRoutingService = Depends(),
) -> Any:
    """获取统计。

    Args:
        task_type: 描述
        current_user: 描述
        service: 描述

    Returns:
        描述
    """
    result = service.get_stats(task_type=task_type)
    return success(data=result)


@router.get("/strategies", summary="List all Strategies", tags=["RL路由"])
def list_strategies(
    task_type: str = Query(None),
    current_user: dict = Depends(require_scope("visit")),
    service: RLRoutingService = Depends(),
) -> Any:
    """获取策略列表。

    Args:
        task_type: 描述
        current_user: 描述
        service: 描述

    Returns:
        描述
    """
    result = service.get_strategies(task_type=task_type)
    return success(data=result)


@router.get("/strategies/{strategy_id}", summary="Get Strategy by ID", tags=["RL路由"])
def get_strategy(
    strategy_id: int,
    current_user: dict = Depends(require_scope("visit")),
    service: RLRoutingService = Depends(),
) -> Any:
    """获取策略。

    Args:
        strategy_id: 描述
        current_user: 描述
        service: 描述

    Returns:
        描述
    """
    row = service.get_strategy(strategy_id=strategy_id)
    return success(data=row)
