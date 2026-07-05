from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from cloud.app.services.rep_workbench.scheduling_service import SchedulingService
from shared.auth_scope import require_scope
from shared.base import success

router = APIRouter(prefix="/api/v1/schedule", tags=["AI排程引擎"])


class OptimizeRequest(BaseModel):
    rep_id: int
    date_range: str = "today"


@router.post("/optimize", summary="AI排程优化", tags=["AI排程引擎"])
def optimize(body: OptimizeRequest, service: SchedulingService = Depends(), _: dict = Depends(require_scope("visit"))):
    result = service.optimize_route(body.rep_id, body.date_range)
    return success(data=result)


@router.get("/plan", summary="查看当前排程计划", tags=["AI排程引擎"])
def get_plan(rep_id: int = Query(1), service: SchedulingService = Depends()):
    result = service.get_plan(rep_id)
    return success(data=result)
