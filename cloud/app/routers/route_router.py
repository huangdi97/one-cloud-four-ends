"""路由规则管理。"""

from typing import Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from starlette import status

from cloud.app.services.brain.route_service import RouteService
from shared.auth_scope import require_scope
from shared.base import success

router = APIRouter(prefix="/route", tags=["Route"])


class RuleCreate(BaseModel):
    name: str
    priority: int = 100
    condition_field: str = "keyword"
    condition_operator: str = "contains"
    condition_value: str
    target_role_id: int
    fallback_role_id: Optional[int] = None
    max_tokens: int = 2048
    temperature: float = 0.7


class RuleUpdate(BaseModel):
    name: Optional[str] = None
    priority: Optional[int] = None
    condition_value: Optional[str] = None
    target_role_id: Optional[int] = None
    is_active: Optional[int] = None


class RouteExecute(BaseModel):
    input: str
    context: dict = {}


@router.post("/rules", status_code=status.HTTP_201_CREATED, tags=["Route"])
def create_rule(
    body: RuleCreate,
    current_user=Depends(require_scope("visit")),
    service: RouteService = Depends(),
):
    """创建路由规则。
    Args: body 规则信息. Returns: 创建的规则.
    """
    row = service.create_rule(
        name=body.name,
        priority=body.priority,
        condition_field=body.condition_field,
        condition_operator=body.condition_operator,
        condition_value=body.condition_value,
        target_role_id=body.target_role_id,
        fallback_role_id=body.fallback_role_id,
        max_tokens=body.max_tokens,
        temperature=body.temperature,
        created_by=int(current_user["sub"]),
    )
    return success(data=row)


@router.get("/rules", tags=["Route"])
def list_rules(current_user=Depends(require_scope("visit")), service: RouteService = Depends()):
    """获取所有路由规则列表。Returns: 规则列表."""
    return success(data=service.list_rules())


@router.patch("/rules/{rule_id}", tags=["Route"])
def update_rule(
    rule_id: int,
    body: RuleUpdate,
    current_user=Depends(require_scope("visit")),
    service: RouteService = Depends(),
):
    """更新路由规则。
    Args: rule_id 规则ID; body 更新字段. Returns: 更新后的规则.
    """
    row = service.update_rule(
        rule_id=rule_id,
        name=body.name,
        priority=body.priority,
        condition_value=body.condition_value,
        target_role_id=body.target_role_id,
        is_active=body.is_active,
    )
    return success(data=row)


@router.delete("/rules/{rule_id}", tags=["Route"])
def delete_rule(
    rule_id: int,
    current_user=Depends(require_scope("visit")),
    service: RouteService = Depends(),
):
    """删除路由规则。
    Args: rule_id 规则ID.
    """
    service.delete_rule(rule_id)
    return success()


@router.post("/execute", tags=["Route"])
def execute_route(
    body: RouteExecute,
    current_user=Depends(require_scope("visit")),
    service: RouteService = Depends(),
):
    """执行路由分发。
    Args: body 输入文本和上下文. Returns: 路由执行结果.
    """
    result = service.execute_route(
        input_text=body.input,
        uid=int(current_user["sub"]),
        source=body.context.get("source", ""),
    )
    return success(data=result)


@router.get("/logs", tags=["Route"])
def list_logs(
    role_id: Optional[int] = Query(None),
    source: Optional[str] = Query(None),
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user=Depends(require_scope("visit")),
    service: RouteService = Depends(),
):
    """查询路由日志。
    Args: 按角色/来源/日期筛选, 分页. Returns: 日志列表.
    """
    return success(
        data=service.list_logs(
            role_id=role_id,
            source=source,
            date_from=date_from,
            date_to=date_to,
            page=page,
            page_size=page_size,
        )
    )


@router.get("/logs/{log_id}", tags=["Route"])
def get_log(
    log_id: int,
    current_user=Depends(require_scope("visit")),
    service: RouteService = Depends(),
):
    """获取路由日志详情。
    Args: log_id 日志ID. Returns: 日志详情.
    """
    return success(data=service.get_log(log_id))


@router.get("/stats", tags=["Route"])
def get_stats(current_user=Depends(require_scope("visit")), service: RouteService = Depends()):
    """获取路由统计信息。Returns: 统计数据."""
    return success(data=service.get_stats())


@router.get("/dashboard", tags=["Route"])
def get_dashboard(current_user=Depends(require_scope("visit")), service: RouteService = Depends()):
    """获取路由仪表盘数据。Returns: 仪表盘数据."""
    return success(data=service.get_dashboard())
