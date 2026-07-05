"""拜访交互记录路由。"""

from typing import Any, Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from starlette import status

from cloud.app.services.rep_workbench.interaction_service import InteractionService
from shared.auth_scope import require_scope
from shared.base import success

router = APIRouter(prefix="/api", tags=["interactions"])


class InteractionCreate(BaseModel):
    type: str = "visit"
    summary: str = ""
    outcome: str = ""
    conducted_by: Optional[int] = None
    conducted_at: Optional[str] = None


class InteractionUpdate(BaseModel):
    type: Optional[str] = None
    summary: Optional[str] = None
    outcome: Optional[str] = None
    conducted_by: Optional[int] = None
    conducted_at: Optional[str] = None


@router.post(
    "/customers/{customer_id}/interactions",
    tags=["interactions"],
    status_code=status.HTTP_201_CREATED,
    summary="创建互动",
    description="为客户创建一条新的互动记录",
)
def create_interaction(
    customer_id: int,
    body: InteractionCreate,
    current_user: dict = Depends(require_scope("visit")),
    service: InteractionService = Depends(),
) -> Any:
    """为客户创建一条互动记录。

    Args:
        customer_id: 客户 ID。
        body: 互动创建请求体。
        current_user: 当前认证用户。
        service: 互动服务实例。

    Returns:
        包含新互动数据的响应。
    """
    user_id = int(current_user["sub"])
    result = service.create_interaction(
        customer_id=customer_id,
        type_=body.type,
        summary=body.summary,
        outcome=body.outcome,
        conducted_by=body.conducted_by,
        conducted_at=body.conducted_at,
        user_id=user_id,
    )
    return success(data=result)


@router.get("/customers/{customer_id}/interactions", summary="客户互动列表", description="获取指定客户的所有互动记录", tags=["interactions"])
def list_customer_interactions(
    customer_id: int,
    current_user: dict = Depends(require_scope("visit")),
    service: InteractionService = Depends(),
) -> Any:
    """获取指定客户的所有互动记录。

    Args:
        customer_id: 客户 ID。
        current_user: 当前认证用户。
        service: 互动服务实例。

    Returns:
        包含互动记录列表的响应。
    """
    rows = service.list_customer_interactions(customer_id)
    return success(data=rows)


@router.get("/interactions", summary="互动列表", description="分页查询所有互动记录，支持按类型和执行人筛选", tags=["interactions"])
def list_interactions(
    type: str = Query(None),
    conducted_by: int = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: dict = Depends(require_scope("visit")),
    service: InteractionService = Depends(),
) -> Any:
    """分页查询互动记录列表。

    Args:
        type: 互动类型筛选。
        conducted_by: 执行人筛选。
        page: 页码，从1开始。
        page_size: 每页数量。
        current_user: 当前认证用户。
        service: 互动服务实例。

    Returns:
        包含互动列表的响应。
    """
    result = service.list_interactions(
        type_=type,
        conducted_by=conducted_by,
        page=page,
        page_size=page_size,
    )
    return success(data=result)


@router.patch("/interactions/{interaction_id}", summary="更新互动", description="更新指定互动的部分信息", tags=["interactions"])
def update_interaction(
    interaction_id: int,
    body: InteractionUpdate,
    current_user: dict = Depends(require_scope("visit")),
    service: InteractionService = Depends(),
) -> Any:
    """更新指定互动的信息。

    Args:
        interaction_id: 互动 ID。
        body: 互动更新请求体。
        current_user: 当前认证用户。
        service: 互动服务实例。

    Returns:
        包含更新后互动数据的响应。
    """
    updates = {
        k: v
        for k, v in {
            "type": body.type,
            "summary": body.summary,
            "outcome": body.outcome,
            "conducted_by": body.conducted_by,
            "conducted_at": body.conducted_at,
        }.items()
        if v is not None
    }
    result = service.update_interaction(interaction_id, updates)
    return success(data=result)


@router.delete("/interactions/{interaction_id}", summary="删除互动", description="删除指定的互动记录", tags=["interactions"])
def delete_interaction(
    interaction_id: int,
    current_user: dict = Depends(require_scope("visit")),
    service: InteractionService = Depends(),
) -> Any:
    """删除指定的互动记录。

    Args:
        interaction_id: 互动 ID。
        current_user: 当前认证用户。
        service: 互动服务实例。

    Returns:
        删除成功的响应。
    """
    service.delete_interaction(interaction_id)
    return success()
