"""培训教练路由。"""

from typing import Any, Optional

from fastapi import APIRouter, Depends, Request

from cloud.app.services.rep_workbench.training_coach_service import TrainingCoachService
from cloud.app.training_coach_handlers import AttributionCreate, ModuleCreate, SessionCreate
from shared.auth_scope import require_scope
from shared.base import PaginatedResponse, success

router = APIRouter(prefix="/training-coach", tags=["Training Coach"])


@router.post("/modules", status_code=201, tags=["Training Coach"])
def create_module(
    body: ModuleCreate,
    cu=Depends(require_scope("visit")),
    service: TrainingCoachService = Depends(),
) -> Any:
    """创建新的培训模块。

    Args:
        body: 模块创建请求体。
        cu: 当前登录用户信息。
        service: 培训教练服务。

    Returns:
        创建的模块对象。
    """
    row = service.create_module(
        title=body.title,
        category=body.category,
        difficulty=body.difficulty,
        content=body.content,
        prerequisites=body.prerequisites,
        passing_score=body.passing_score,
        estimated_minutes=body.estimated_minutes,
        created_by=cu["user_id"],
    )
    return success(row)


@router.get("/modules", tags=["Training Coach"])
def list_modules(
    category: Optional[str] = None,
    difficulty: Optional[str] = None,
    cu=Depends(require_scope("visit")),
    service: TrainingCoachService = Depends(),
) -> Any:
    """查询培训模块列表。

    Args:
        category: 可选的按分类筛选。
        difficulty: 可选的按难度筛选。
        cu: 当前登录用户信息。
        service: 培训教练服务。

    Returns:
        模块列表。
    """
    rows = service.list_modules(category=category, difficulty=difficulty)
    return success(rows)


@router.post("/sessions", status_code=201, tags=["Training Coach"])
def create_session(
    body: SessionCreate,
    cu=Depends(require_scope("visit")),
    service: TrainingCoachService = Depends(),
) -> Any:
    """创建培训会话记录。

    Args:
        body: 会话创建请求体。
        cu: 当前登录用户信息。
        service: 培训教练服务。

    Returns:
        创建的会话对象。
    """
    row = service.create_session(
        user_id=body.user_id,
        module_id=body.module_id,
        score=body.score,
        passed=body.passed,
        time_spent_seconds=body.time_spent_seconds,
        answers=body.answers,
        feedback=body.feedback,
        difficulty_used=body.difficulty_used,
    )
    return success(row)


@router.get("/sessions", tags=["Training Coach"])
def list_sessions(
    user_id: Optional[int] = None,
    module_id: Optional[int] = None,
    page: int = 1,
    page_size: int = 20,
    cu=Depends(require_scope("visit")),
    service: TrainingCoachService = Depends(),
) -> Any:
    """分页查询培训会话列表。

    Args:
        user_id: 可选的按用户筛选。
        module_id: 可选的按模块筛选。
        page: 页码。
        page_size: 每页条数。
        cu: 当前登录用户信息。
        service: 培训教练服务。

    Returns:
        分页会话列表。
    """
    result = service.list_sessions(
        user_id=user_id,
        module_id=module_id,
        page=page,
        page_size=page_size,
    )
    return success(data=PaginatedResponse(**result))


@router.get("/sessions/{session_id}", tags=["Training Coach"])
def get_session(
    session_id: int,
    cu=Depends(require_scope("visit")),
    service: TrainingCoachService = Depends(),
) -> Any:
    """获取单个培训会话的详情。

    Args:
        session_id: 会话 ID。
        cu: 当前登录用户信息。
        service: 培训教练服务。

    Returns:
        会话详情。
    """
    row = service.get_session(session_id)
    return success(row)


@router.post("/recommend", tags=["Training Coach"])
def recommend(
    body: Request,
    cu=Depends(require_scope("visit")),
    service: TrainingCoachService = Depends(),
) -> Any:
    """为当前用户推荐培训模块。

    Args:
        body: 请求对象（未使用）。
        cu: 当前登录用户信息。
        service: 培训教练服务。

    Returns:
        推荐结果。
    """
    result = service.recommend(cu["user_id"])
    return success(result)


@router.post("/attributions", status_code=201, tags=["Training Coach"])
def create_attribution(
    body: AttributionCreate,
    cu=Depends(require_scope("visit")),
    service: TrainingCoachService = Depends(),
) -> Any:
    """创建培训效果归因记录。

    Args:
        body: 归因创建请求体。
        cu: 当前登录用户信息。
        service: 培训教练服务。

    Returns:
        创建的归因对象。
    """
    row = service.create_attribution(
        user_id=body.user_id,
        metric_name=body.metric_name,
        metric_before=body.metric_before,
        metric_after=body.metric_after,
        period_days=body.period_days,
    )
    return success(row)


@router.get("/attributions", tags=["Training Coach"])
def list_attributions(
    user_id: Optional[int] = None,
    metric_name: Optional[str] = None,
    cu=Depends(require_scope("visit")),
    service: TrainingCoachService = Depends(),
) -> Any:
    """查询培训归因记录列表。

    Args:
        user_id: 可选的按用户筛选。
        metric_name: 可选的按指标名称筛选。
        cu: 当前登录用户信息。
        service: 培训教练服务。

    Returns:
        归因记录列表。
    """
    rows = service.list_attributions(user_id=user_id, metric_name=metric_name)
    return success(rows)


@router.post("/attributions/{att_id}/analyze", tags=["Training Coach"])
def analyze_attribution(
    att_id: int,
    cu=Depends(require_scope("visit")),
    service: TrainingCoachService = Depends(),
) -> Any:
    """分析指定培训归因记录的深层影响。

    Args:
        att_id: 归因记录 ID。
        cu: 当前登录用户信息。
        service: 培训教练服务。

    Returns:
        分析结果。
    """
    row = service.analyze_attribution(att_id)
    return success(row)


@router.get("/dashboard", tags=["Training Coach"])
def dashboard(
    cu=Depends(require_scope("visit")),
    service: TrainingCoachService = Depends(),
) -> Any:
    """获取培训教练仪表盘统计。

    Args:
        cu: 当前登录用户信息。
        service: 培训教练服务。

    Returns:
        仪表盘统计结果。
    """
    result = service.dashboard()
    return success(result)
