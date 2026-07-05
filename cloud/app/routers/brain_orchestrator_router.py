"""类脑记忆编排路由。"""

from typing import Optional

from fastapi import APIRouter, Depends, Query

from cloud.app.brain_orchestrator_handlers import (
    CreateProcedural,
    EvolveMemory,
    FoldMemories,
    InvokeProcedural,
    Orchestrate,
    SensoryIngest,
)
from cloud.app.services.brain.brain_evolution_service import BrainEvolutionService
from cloud.app.services.brain.brain_orchestrator_service import BrainOrchestratorService
from cloud.app.services.brain.brain_search_service import BrainSearchService
from shared.auth_scope import require_scope
from shared.base import success

router = APIRouter(prefix="/memory/brain", tags=["类脑记忆"])


@router.post("/sensory/ingest", summary="感官输入", description="接收并处理感官输入数据", tags=["类脑记忆"])
def sensory_ingest(
    body: SensoryIngest,
    service: BrainOrchestratorService = Depends(),
    _user=Depends(require_scope("pharma")),
):
    """sensory_ingest 操作。

    Args:
        service: 描述
        _user: 描述
    """
    result = service.ingest_sensory(
        input_type=body.input_type,
        raw_content=body.raw_content,
        source=body.source,
    )
    return success(data=result)


@router.get("/sensory/buffer", summary="感官缓存", description="获取感官输入缓冲区数据", tags=["类脑记忆"])
def sensory_buffer(
    limit: int = Query(50, ge=1, le=200),
    service: BrainOrchestratorService = Depends(),
    _user=Depends(require_scope("pharma")),
):
    """sensory_buffer 操作。

    Args:
        limit: 描述
        service: 描述
        _user: 描述
    """
    result = service.get_sensory_buffer(limit=limit)
    return success(data=result)


@router.get("/procedural", summary="程序记忆列表", description="按触发事件筛选程序性记忆列表", tags=["类脑记忆"])
def procedural_list(
    trigger_event: Optional[str] = Query(None),
    service: BrainOrchestratorService = Depends(),
    _user=Depends(require_scope("pharma")),
):
    """procedural_list 操作。

    Args:
        trigger_event: 描述
        service: 描述
        _user: 描述
    """
    result = service.list_procedural(trigger_event=trigger_event)
    return success(data=result)


@router.post("/procedural", status_code=201, summary="创建程序记忆", description="创建一条程序性记忆", tags=["类脑记忆"])
def procedural_create(
    body: CreateProcedural,
    service: BrainOrchestratorService = Depends(),
    _user=Depends(require_scope("pharma")),
):
    """procedural_create 操作。

    Args:
        service: 描述
        _user: 描述
    """
    result = service.create_procedural(
        procedure_key=body.procedure_key,
        name=body.name,
        description=body.description,
        steps=body.steps,
        trigger_conditions=body.trigger_conditions,
    )
    return success(data=result)


@router.post("/procedural/{procedure_key}/invoke", summary="调用程序记忆", description="根据上下文调用指定的程序性记忆", tags=["类脑记忆"])
def procedural_invoke(
    procedure_key: str,
    body: InvokeProcedural,
    service: BrainOrchestratorService = Depends(),
    _user=Depends(require_scope("pharma")),
):
    """procedural_invoke 操作。

    Args:
        procedure_key: 描述
        service: 描述
        _user: 描述
    """
    result = service.invoke_procedural(procedure_key=procedure_key, context=body.context)
    return success(data=result)


@router.post("/orchestrate", summary="编排处理", description="编排多脑区协同处理输入数据", tags=["类脑记忆"])
def orchestrate(
    body: Orchestrate,
    service: BrainOrchestratorService = Depends(),
    _user=Depends(require_scope("pharma")),
):
    """orchestrate 操作。

    Args:
        service: 描述
        _user: 描述
    """
    result = service.orchestrate(
        input_text=body.input_text,
        input_type=body.input_type,
        source=body.source,
    )
    return success(data=result)


@router.post("/evolve", summary="进化记忆", description="基于新证据进化已有的记忆", tags=["类脑记忆"])
def evolve_memory(
    body: EvolveMemory,
    service: BrainEvolutionService = Depends(),
    _user=Depends(require_scope("pharma")),
):
    """evolve_memory 操作。

    Args:
        service: 描述
        _user: 描述
    """
    result = service.evolve_memory(
        memory_id=body.memory_id,
        new_evidence=body.new_evidence,
        memory_type=body.memory_type,
    )
    return success(data=result)


@router.get("/evolve/history/{memory_id}", summary="进化历史", description="获取指定记忆的进化历史记录", tags=["类脑记忆"])
def evolution_history(
    memory_id: int,
    service: BrainEvolutionService = Depends(),
    _user=Depends(require_scope("pharma")),
):
    """evolution_history 操作。

    Args:
        memory_id: 描述
        service: 描述
        _user: 描述
    """
    result = service.get_evolution_history(memory_id=memory_id)
    return success(data=result)


@router.post("/fold", summary="折叠记忆", description="将多条记忆折叠合并为一条", tags=["类脑记忆"])
def fold_memories(
    body: FoldMemories,
    service: BrainEvolutionService = Depends(),
    _user=Depends(require_scope("pharma")),
):
    """fold_memories 操作。

    Args:
        service: 描述
        _user: 描述
    """
    result = service.fold_memories(memory_ids=body.memory_ids)
    return success(data=result)


@router.get("/search", summary="统一搜索", description="跨脑区统一搜索所有类型的记忆", tags=["类脑记忆"])
def unified_search(
    q: str = Query(..., min_length=1),
    types: Optional[str] = Query(None, description="Comma-separated memory types"),
    limit: int = Query(20, ge=1, le=200),
    service: BrainSearchService = Depends(),
    _user=Depends(require_scope("pharma")),
):
    """unified_search 操作。

    Args:
        q: 描述
        types: 描述
        limit: 描述
        service: 描述
        _user: 描述
    """
    memory_types = types.split(",") if types else None
    result = service.unified_search(query=q, memory_types=memory_types, limit=limit)
    return success(data=result)


@router.get("/fold/{memory_id}", summary="查询折叠记忆", description="根据memory_id获取折叠后的记忆", tags=["类脑记忆"])
def get_folded(
    memory_id: int,
    service: BrainEvolutionService = Depends(),
    _user=Depends(require_scope("pharma")),
):
    """get_folded 操作。

    Args:
        memory_id: 描述
        service: 描述
        _user: 描述
    """
    result = service.get_folded(memory_id=memory_id)
    return success(data=result)
