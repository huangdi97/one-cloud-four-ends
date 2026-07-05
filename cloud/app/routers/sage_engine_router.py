"""Sage 记忆引擎路由：评分查询、演化触发、自动链接与状态。"""

from fastapi import APIRouter, Depends

from cloud.app.services.brain.sage_engine_service import SageEngineService
from shared.auth_scope import require_scope
from shared.base import success

router = APIRouter(prefix="/sage", tags=["记忆系统"], dependencies=[Depends(require_scope("research"))])


@router.get("/score", summary="评分查询", description="查询所有记忆的评分", tags=["记忆系统"])
def get_all_scores(service: SageEngineService = Depends()):
    return success(data=service.score_all_memories())


@router.get("/score/{memory_type}/{memory_id}", summary="评分详情", description="查询指定记忆类型的评分详情", tags=["记忆系统"])
def get_score_detail(memory_type: str, memory_id: int, service: SageEngineService = Depends()):
    return success(data=service.score_detail(memory_type, memory_id))


@router.post("/evolve", summary="触发演化", description="手动触发记忆系统的演化过程", tags=["记忆系统"])
def evolve(service: SageEngineService = Depends()):
    return success(data=service.evolve(triggered_by="manual"))


@router.post("/auto-link", summary="自动链接", description="触发记忆的自动链接操作", tags=["记忆系统"])
def auto_link(service: SageEngineService = Depends()):
    return success(data=service.linking.auto_link())


@router.get("/status", summary="引擎状态", description="查询记忆引擎的当前状态", tags=["记忆系统"])
def get_status(service: SageEngineService = Depends()):
    return success(data=service.linking.get_status())
