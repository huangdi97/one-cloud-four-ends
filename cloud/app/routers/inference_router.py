from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from cloud.app.services.platform_svc.inference_pipeline import InferencePipeline
from shared.auth_scope import require_scope
from shared.base import success

router = APIRouter(prefix="/api/v1/inference", tags=["推演"])


class InferenceRequest(BaseModel):
    scenario: str = Field(..., min_length=1, description="推演场景描述")
    domain: str = Field(..., description="推演领域")
    horizon_days: int = Field(90, ge=1, le=365)


class ScenarioItem(BaseModel):
    id: str
    scenario: str
    domain: str
    reason: str


_PRESET_SCENARIOS: list[dict] = [
    {"id": "s1", "scenario": "如果张代表继续当前拜访模式", "domain": "sales", "reason": "费用趋势异常上升"},
    {"id": "s2", "scenario": "如果陈主任流失", "domain": "compliance", "reason": "关键HCP稳定性下降"},
    {"id": "s3", "scenario": "竞品在华东降价", "domain": "opportunity", "reason": "竞品活跃度上升"},
    {"id": "s4", "scenario": "砍生物线20%预算", "domain": "sales", "reason": "预算分配变化"},
    {"id": "s5", "scenario": "缩减学术会议场次", "domain": "compliance", "reason": "合规成本压力"},
]


@router.post("/run", tags=["推演"])
async def run_inference(
    body: InferenceRequest,
    current_user: dict = Depends(require_scope("visit")),
    pipeline=Depends(),
) -> Any:
    pipeline = pipeline or InferencePipeline()
    result = await pipeline.run(
        scenario=body.scenario,
        domain=body.domain,
        user_id=str(current_user.get("sub", "")),
        horizon_days=body.horizon_days,
    )
    return success(data=result.__dict__ if hasattr(result, "__dict__") else result)


@router.get("/scenarios", tags=["推演"])
async def list_scenarios(
    domain: str | None = None,
    current_user: dict = Depends(require_scope("visit")),
) -> Any:
    items = [s for s in _PRESET_SCENARIOS if not domain or s["domain"] == domain]
    return success(data=items)
