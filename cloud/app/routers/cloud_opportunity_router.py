"""商机管理路由。"""

from typing import Any, Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from starlette import status

from cloud.app.services.rep_workbench.opportunity_service import OpportunityService
from shared.auth_scope import require_scope
from shared.base import success

router = APIRouter(prefix="/opportunities", tags=["商机"])

opportunity_v2_router = APIRouter(prefix="/opportunity", tags=["opportunity"])


class OpportunityCreate(BaseModel):
    customer_id: int
    name: str = Field(..., min_length=1, max_length=200)
    description: str = ""
    stage: str = "lead"
    estimated_value: float = 0.0
    actual_value: float = 0.0
    assigned_to: Optional[int] = None
    close_date: Optional[str] = None
    notes: str = ""


class OpportunityUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    stage: Optional[str] = None
    estimated_value: Optional[float] = None
    actual_value: Optional[float] = None
    assigned_to: Optional[int] = None
    close_date: Optional[str] = None
    notes: Optional[str] = None


class StageTransition(BaseModel):
    stage: str
    actual_value: Optional[float] = None


@router.post("/", status_code=status.HTTP_201_CREATED, tags=["商机"])
def create_opportunity(
    body: OpportunityCreate,
    current_user: dict = Depends(require_scope("visit")),
    service: OpportunityService = Depends(),
) -> Any:
    """创建商机。
    Args: body 商机信息. Returns: 创建的商机.
    """
    user_id = int(current_user["sub"])
    row = service.create_opportunity(
        customer_id=body.customer_id,
        name=body.name,
        description=body.description,
        stage=body.stage,
        estimated_value=body.estimated_value,
        actual_value=body.actual_value,
        assigned_to=body.assigned_to,
        close_date=body.close_date,
        notes=body.notes,
        user_id=user_id,
    )
    return success(data=row)


@router.get("/", tags=["商机"])
def list_opportunities(
    stage: str = Query(None),
    assigned_to: int = Query(None),
    customer_id: int = Query(None),
    search: str = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: dict = Depends(require_scope("visit")),
    service: OpportunityService = Depends(),
) -> Any:
    """查询商机列表。
    Args: 按阶段/负责人/客户/关键词筛选, 分页. Returns: 商机列表.
    """
    result = service.list_opportunities(
        stage=stage,
        assigned_to=assigned_to,
        customer_id=customer_id,
        search=search,
        page=page,
        page_size=page_size,
    )
    return success(data=result)


@router.get("/pipeline", tags=["商机"])
def get_pipeline(
    current_user: dict = Depends(require_scope("visit")),
    service: OpportunityService = Depends(),
) -> Any:
    """获取商机管道概览。Returns: 管道数据."""
    result = service.get_pipeline()
    return success(data=result)


@router.get("/{opp_id}", tags=["商机"])
def get_opportunity(
    opp_id: int,
    current_user: dict = Depends(require_scope("visit")),
    service: OpportunityService = Depends(),
) -> Any:
    """获取商机详情。
    Args: opp_id 商机ID. Returns: 商机详情.
    """
    row = service.get_opportunity(opp_id)
    return success(data=row)


@router.patch("/{opp_id}", tags=["商机"])
def update_opportunity(
    opp_id: int,
    body: OpportunityUpdate,
    current_user: dict = Depends(require_scope("visit")),
    service: OpportunityService = Depends(),
) -> Any:
    """更新商机信息。
    Args: opp_id 商机ID; body 更新字段. Returns: 更新后的商机.
    """
    row = service.update_opportunity(
        opp_id=opp_id,
        name=body.name,
        description=body.description,
        stage=body.stage,
        estimated_value=body.estimated_value,
        actual_value=body.actual_value,
        assigned_to=body.assigned_to,
        close_date=body.close_date,
        notes=body.notes,
    )
    return success(data=row)


@router.delete("/{opp_id}", tags=["商机"])
def delete_opportunity(
    opp_id: int,
    current_user: dict = Depends(require_scope("visit")),
    service: OpportunityService = Depends(),
) -> Any:
    """删除商机。
    Args: opp_id 商机ID.
    """
    service.delete_opportunity(opp_id)
    return success()


@router.patch("/{opp_id}/stage", tags=["商机"])
def transition_stage(
    opp_id: int,
    body: StageTransition,
    current_user: dict = Depends(require_scope("visit")),
    service: OpportunityService = Depends(),
) -> Any:
    """推进商机阶段。
    Args: opp_id 商机ID; body 目标阶段. Returns: 更新后的商机.
    """
    row = service.transition_stage(
        opp_id=opp_id,
        stage=body.stage,
        actual_value=body.actual_value,
    )
    return success(data=row)


@opportunity_v2_router.get("/list")
def list_opportunities_v2(
    current_user: dict = Depends(require_scope("visit")),
) -> Any:
    return success(data=[])
