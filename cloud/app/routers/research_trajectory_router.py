from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from cloud.app.services.intel.research_trajectory_service import ResearchTrajectoryService
from shared.auth import get_current_user
from shared.auth_scope import require_scope
from shared.base import success

trajectory_router = APIRouter(
    prefix="/api/research/trajectory",
    tags=["Research Trajectory"],
    dependencies=[Depends(require_scope("research"))],
)


class PredictRequest(BaseModel):
    horizon_days: int = 90


@trajectory_router.get("/pi/{pi_id}/trajectory", summary="Get Pi Trajectory by ID", description="根据PI ID获取科研轨迹", tags=["Research Trajectory"])
def get_pi_trajectory(
    pi_id: int,
    current_user: dict = Depends(get_current_user),
):
    service = ResearchTrajectoryService()
    data = service.get_trajectory(pi_id)
    return success(data)


@trajectory_router.post(
    "/pi/{pi_id}/predict", summary="Predict Pi Trajectory", description="预测PI未来指定天数的科研轨迹", tags=["Research Trajectory"]
)
def predict_pi_trajectory(
    pi_id: int,
    body: PredictRequest = None,
    current_user: dict = Depends(get_current_user),
):
    horizon_days = body.horizon_days if body else 90
    service = ResearchTrajectoryService()
    data = service.predict_trajectory(pi_id, horizon_days)
    return success(data)


@trajectory_router.get("/trends", summary="Get Trends by ID", description="获取科研趋势数据", tags=["Research Trajectory"])
def get_trends(
    days: int = Query(90, description="天数范围"),
    current_user: dict = Depends(get_current_user),
):
    service = ResearchTrajectoryService()
    data = service.get_trends(days)
    return success(data)


__all__ = ["trajectory_router", "PredictRequest"]
