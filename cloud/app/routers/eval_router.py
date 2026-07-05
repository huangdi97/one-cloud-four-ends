"""评测与回归测试路由。

路由前缀：/eval
核心数据模型：EvalService 预设用例、回归结果与评测请求字典。
"""

from fastapi import APIRouter, Depends

from cloud.app.services.rep_workbench.eval_service import EvalService
from shared.auth_scope import require_scope
from shared.base import success

router = APIRouter(prefix="/eval", tags=["evaluation"])

_service = EvalService()


@router.post("/run", tags=["evaluation"])
async def run_eval(body: dict, _: dict = Depends(require_scope("visit"))):
    agent_key = body.get("agent_key", "")
    test_cases = body.get("test_cases")
    if test_cases:
        return success(data=_service.evaluate(agent_key, test_cases))
    return success(data=_service.run_regression(agent_key))


@router.get("/regression/{agent_key}", tags=["evaluation"])
async def regression(agent_key: str):
    return success(data=_service.run_regression(agent_key))


@router.get("/presets", tags=["evaluation"])
async def presets():
    return success(data=_service.PRESET_CASES)
