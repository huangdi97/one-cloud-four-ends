"""培训脚本路由。"""

from typing import Optional

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from starlette import status

from cloud.app.services.rep_workbench.training_scripts_service import TrainingScriptsService
from shared.auth_scope import require_scope
from shared.base import ApiResponse, PaginatedResponse, success

router = APIRouter(prefix="/training/scripts", tags=["Training Scripts"])


class ScriptExtract(BaseModel):
    source_agent_role: str
    min_score: float = 0.7


class RoiAnalyze(BaseModel):
    period_start: str
    period_end: str


class ScriptOut(BaseModel):
    id: int
    script_id: Optional[str] = None
    script_name: Optional[str] = None
    source_agent_role: Optional[str] = None
    source_collaboration_id: Optional[str] = None
    description: Optional[str] = None
    steps: Optional[str] = "[]"
    difficulty: Optional[str] = "mid"
    target_roles: Optional[str] = "[]"
    score: Optional[float] = None
    created_by: Optional[int] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class RoiOut(BaseModel):
    id: int
    analysis_id: Optional[str] = None
    period_start: Optional[str] = None
    period_end: Optional[str] = None
    training_hours: Optional[float] = None
    participants: Optional[int] = None
    behavior_change_score: Optional[float] = None
    sales_impact: Optional[float] = None
    cost_savings: Optional[float] = None
    roi: Optional[float] = None
    metadata: Optional[str] = "{}"
    created_at: Optional[str] = None


@router.post("/extract", status_code=status.HTTP_201_CREATED, tags=["Training Scripts"])
def extract_scripts(
    body: ScriptExtract,
    current_user=Depends(require_scope("visit")),
    service: TrainingScriptsService = Depends(),
) -> JSONResponse:
    """从指定角色的协作中提取培训脚本。

    Args:
        body: 脚本提取请求体。
        current_user: 当前登录用户信息。
        service: 培训脚本服务。

    Returns:
        提取结果。
    """
    result = service.extract_scripts(
        source_agent_role=body.source_agent_role,
        min_score=body.min_score,
        user_id=int(current_user["sub"]),
    )
    return JSONResponse(
        content=success(data=result).model_dump(),
        status_code=status.HTTP_201_CREATED,
    )


@router.get("/list", tags=["Training Scripts"])
def list_scripts(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    source_agent_role: Optional[str] = Query(None),
    difficulty: Optional[str] = Query(None),
    target_roles: Optional[str] = Query(None),
    current_user=Depends(require_scope("visit")),
    service: TrainingScriptsService = Depends(),
) -> ApiResponse[PaginatedResponse[ScriptOut]]:
    """分页查询培训脚本列表。

    Args:
        page: 页码。
        page_size: 每页条数（1-100）。
        source_agent_role: 可选的按来源角色筛选。
        difficulty: 可选的按难度筛选。
        target_roles: 可选的按目标角色筛选。
        current_user: 当前登录用户信息。
        service: 培训脚本服务。

    Returns:
        分页脚本列表。
    """
    result = service.list_scripts(
        page=page,
        page_size=page_size,
        source_agent_role=source_agent_role,
        difficulty=difficulty,
        target_roles=target_roles,
    )
    return success(
        data=PaginatedResponse(
            items=[ScriptOut(**r) for r in result["items"]],
            total=result["total"],
            page=result["page"],
            page_size=result["page_size"],
            total_pages=result["total_pages"],
        )
    )


@router.post("/roi/analyze", status_code=status.HTTP_201_CREATED, tags=["Training Scripts"])
def analyze_roi(
    body: RoiAnalyze,
    current_user=Depends(require_scope("visit")),
    service: TrainingScriptsService = Depends(),
) -> JSONResponse:
    """分析指定时间段内的培训投资回报率。

    Args:
        body: ROI 分析请求体（起止时间）。
        current_user: 当前登录用户信息。
        service: 培训脚本服务。

    Returns:
        ROI 分析结果。
    """
    result = service.analyze_roi(
        period_start=body.period_start,
        period_end=body.period_end,
    )
    return JSONResponse(
        content=success(data=result).model_dump(),
        status_code=status.HTTP_201_CREATED,
    )


@router.get("/roi/list", tags=["Training Scripts"])
def list_roi(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user=Depends(require_scope("visit")),
    service: TrainingScriptsService = Depends(),
) -> ApiResponse[PaginatedResponse[RoiOut]]:
    """分页查询 ROI 分析记录列表。

    Args:
        page: 页码。
        page_size: 每页条数（1-100）。
        current_user: 当前登录用户信息。
        service: 培训脚本服务。

    Returns:
        分页 ROI 记录列表。
    """
    result = service.list_roi(page=page, page_size=page_size)
    return success(
        data=PaginatedResponse(
            items=[RoiOut(**r) for r in result["items"]],
            total=result["total"],
            page=result["page"],
            page_size=result["page_size"],
            total_pages=result["total_pages"],
        )
    )
