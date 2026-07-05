"""推荐引擎路由。"""

from typing import Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from starlette import status

from cloud.app.services.rep_workbench.recommend_service import RecommendService
from shared.auth_scope import require_scope
from shared.base import success

router = APIRouter(prefix="/recommend", tags=["Recommendation Engine"])


class ProfileCreate(BaseModel):
    user_id: int
    persona_type: str = ""
    specialization: str = ""
    experience_level: str = "mid"
    preferred_content_types: list[str] = []
    custom_tags: list[str] = []


class ProfileUpdate(BaseModel):
    persona_type: Optional[str] = None
    specialization: Optional[str] = None
    experience_level: Optional[str] = None
    preferred_content_types: Optional[list[str]] = None
    custom_tags: Optional[list[str]] = None


class BehaviorLog(BaseModel):
    user_id: int
    action_type: str
    target_type: str = ""
    target_id: str = ""
    metadata: dict = {}
    session_id: str = ""
    duration_seconds: int = 0


class RecGenerate(BaseModel):
    user_id: int
    rec_types: list[str] = ["content", "strategy", "action"]
    limit: int = 5


@router.post("/profile/create", status_code=status.HTTP_201_CREATED, tags=["Recommendation Engine"])
def create_profile(
    body: ProfileCreate,
    current_user: dict = Depends(require_scope("visit")),
    service: RecommendService = Depends(),
):
    """创建推荐画像。
    Args: body 画像信息. Returns: 创建的画像.
    """
    row = service.create_profile(
        body.user_id,
        body.persona_type,
        body.specialization,
        body.experience_level,
        body.preferred_content_types,
        body.custom_tags,
    )
    return success(data=row)


@router.get("/profile/{user_id}", tags=["Recommendation Engine"])
def get_profile(
    user_id: int,
    current_user: dict = Depends(require_scope("visit")),
    service: RecommendService = Depends(),
):
    """获取用户推荐画像。
    Args: user_id 用户ID. Returns: 画像数据.
    """
    return success(data=service.get_profile(user_id))


@router.patch("/profile/{user_id}", tags=["Recommendation Engine"])
def update_profile(
    user_id: int,
    body: ProfileUpdate,
    current_user: dict = Depends(require_scope("visit")),
    service: RecommendService = Depends(),
):
    """更新用户推荐画像。
    Args: user_id 用户ID; body 更新字段. Returns: 更新后的画像.
    """
    row = service.update_profile(
        user_id,
        body.persona_type,
        body.specialization,
        body.experience_level,
        body.preferred_content_types,
        body.custom_tags,
    )
    return success(data=row)


@router.post("/behavior/log", status_code=status.HTTP_201_CREATED, tags=["Recommendation Engine"])
def log_behavior(
    body: BehaviorLog,
    current_user: dict = Depends(require_scope("visit")),
    service: RecommendService = Depends(),
):
    """记录用户行为。
    Args: body 行为数据. Returns: 记录的行.
    """
    row = service.log_behavior(
        body.user_id,
        body.action_type,
        body.target_type,
        body.target_id,
        body.metadata,
        body.session_id,
        body.duration_seconds,
    )
    return success(data=row)


@router.get("/behavior/history", tags=["Recommendation Engine"])
def behavior_history(
    user_id: Optional[int] = Query(None),
    action_type: Optional[str] = Query(None),
    target_type: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    current_user: dict = Depends(require_scope("visit")),
    service: RecommendService = Depends(),
):
    """查询行为历史。
    Args: 按用户/动作/目标筛选, 分页. Returns: 行为记录列表.
    """
    return success(
        data=service.behavior_history(
            user_id=user_id,
            action_type=action_type,
            target_type=target_type,
            limit=limit,
            offset=offset,
        )
    )


@router.post("/generate", status_code=status.HTTP_201_CREATED, tags=["Recommendation Engine"])
def generate_recommendations(
    body: RecGenerate,
    current_user: dict = Depends(require_scope("visit")),
    service: RecommendService = Depends(),
):
    """生成推荐结果。
    Args: body 推荐请求参数. Returns: 推荐列表.
    """
    results = service.generate_recommendations(body.user_id, body.rec_types, body.limit)
    return success(data=results)


@router.get("/list", tags=["Recommendation Engine"])
def list_recommendations(
    user_id: Optional[int] = Query(None),
    rec_type: Optional[str] = Query(None),
    clicked: Optional[int] = Query(None),
    dismissed: Optional[int] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    current_user: dict = Depends(require_scope("visit")),
    service: RecommendService = Depends(),
):
    """查询推荐记录。
    Args: 按用户/类型/点击/关闭筛选, 分页. Returns: 推荐记录列表.
    """
    return success(
        data=service.list_recommendations(
            user_id=user_id,
            rec_type=rec_type,
            clicked=clicked,
            dismissed=dismissed,
            limit=limit,
            offset=offset,
        )
    )


@router.post("/{rec_id}/click", tags=["Recommendation Engine"])
def mark_clicked(
    rec_id: int,
    current_user: dict = Depends(require_scope("visit")),
    service: RecommendService = Depends(),
):
    """标记推荐为已点击。
    Args: rec_id 推荐ID.
    """
    service.mark_clicked(rec_id)
    return success()


@router.post("/{rec_id}/dismiss", tags=["Recommendation Engine"])
def mark_dismissed(
    rec_id: int,
    current_user: dict = Depends(require_scope("visit")),
    service: RecommendService = Depends(),
):
    """标记推荐为已忽略。
    Args: rec_id 推荐ID.
    """
    service.mark_dismissed(rec_id)
    return success()


@router.get("/dashboard", tags=["Recommendation Engine"])
def dashboard(
    current_user: dict = Depends(require_scope("visit")),
    service: RecommendService = Depends(),
):
    """获取推荐仪表盘数据。Returns: 仪表盘数据."""
    return success(data=service.dashboard())
