"""类脑工作记忆路由。"""

from typing import Optional

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel

from cloud.app.services.brain.brain_memory_service import BrainMemoryService
from shared.auth_scope import require_scope
from shared.base import PaginatedResponse, success

router = APIRouter(prefix="/brain-memory", tags=["Brain Memory"])


class WorkingMemorySet(BaseModel):
    session_id: str
    slot_key: str
    slot_value: str = ""
    slot_type: str = "string"
    ttl_seconds: int = 1800


class EpisodicStore(BaseModel):
    event_type: str
    title: str
    description: str = ""
    context: dict = {}
    outcome: str = ""
    valence: float = 0.0
    intensity: float = 0.5
    involved_agents: list[str] = []
    related_entity_type: str = ""
    related_entity_id: Optional[int] = None


class SemanticAbstract(BaseModel):
    source_type: str
    source_id: str
    abstraction_level: str = "medium"


class ProceduralLearn(BaseModel):
    pattern_name: str
    trigger_conditions: str = ""
    action_sequence: str = ""
    success_rate: float = 0.5


class ProceduralRecall(BaseModel):
    trigger_context: str = ""


class MemoryDecay(BaseModel):
    hours_threshold: int = 72


@router.post("/working/set", summary="设置工作记忆", description="设置工作记忆槽位值", tags=["Brain Memory"])
def working_set(body: WorkingMemorySet, service: BrainMemoryService = Depends()):
    """设置工作记忆槽位。Args: body (WorkingMemorySet) 工作记忆设置体; service (BrainMemoryService) 记忆服务。Returns: dict 成功响应"""
    result = service.working_set(
        session_id=body.session_id,
        slot_key=body.slot_key,
        slot_value=body.slot_value,
        slot_type=body.slot_type,
        ttl_seconds=body.ttl_seconds,
    )
    return success(data=result)


@router.get("/working/get", summary="获取工作记忆", description="获取指定会话的工作记忆数据", tags=["Brain Memory"])
def working_get(
    session_id: str = Query(...),
    slot_key: Optional[str] = Query(None),
    service: BrainMemoryService = Depends(),
):
    """获取工作记忆数据。Args: session_id (str) 会话ID; slot_key (Optional[str]) 槽位键; service BrainMemoryService。Returns: dict 成功响应"""
    result = service.working_get(session_id=session_id, slot_key=slot_key)
    return success(data=result["data"])


@router.delete("/working/clear/{session_id}", summary="清除工作记忆", description="清除指定会话的所有工作记忆", tags=["Brain Memory"])
def working_clear(session_id: str, service: BrainMemoryService = Depends()):
    """清除指定会话的工作记忆。Args: session_id (str) 会话ID; service (BrainMemoryService) 记忆服务。Returns: dict 成功响应"""
    message = service.working_clear(session_id)
    return success(message=message)


@router.post("/working/refresh/{session_id}", summary="刷新工作记忆", description="刷新会话工作记忆的TTL过期时间", tags=["Brain Memory"])
def working_refresh(session_id: str, service: BrainMemoryService = Depends()):
    """刷新会话工作记忆的TTL。Args: session_id (str) 会话ID; service (BrainMemoryService) 记忆服务。Returns: dict 成功响应"""
    result = service.working_refresh(session_id)
    return success(data=result)


@router.post("/episodic/store", status_code=201, summary="存储情景记忆", description="存储一条情景记忆记录", tags=["Brain Memory"])
def episodic_store(
    body: EpisodicStore,
    request: Request,
    current_user=Depends(require_scope("visit")),
    service: BrainMemoryService = Depends(),
):
    """存储情景记忆。
    Args: body (EpisodicStore) 情景记忆体; request (Request) HTTP请求; current_user 用户; service BrainMemoryService。
    Returns: dict 成功响应"""
    uid = str(current_user["sub"])
    result = service.episodic_store(
        event_type=body.event_type,
        title=body.title,
        description=body.description,
        context=body.context,
        outcome=body.outcome,
        valence=body.valence,
        intensity=body.intensity,
        involved_agents=body.involved_agents,
        related_entity_type=body.related_entity_type,
        related_entity_id=body.related_entity_id,
        uid=uid,
    )
    return success(data=result)


@router.get("/episodic/list", summary="情景记忆列表", description="分页查询情景记忆记录", tags=["Brain Memory"])
def episodic_list(
    event_type: Optional[str] = Query(None),
    outcome: Optional[str] = Query(None),
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    service: BrainMemoryService = Depends(),
):
    """分页查询情景记忆。Args: event_type/outcome/date_from/date_to 筛选; page/page_size 分页; service BrainMemoryService。Returns: dict 成功响应"""
    result = service.episodic_list(
        event_type=event_type,
        outcome=outcome,
        date_from=date_from,
        date_to=date_to,
        page=page,
        page_size=page_size,
    )
    return success(
        data=PaginatedResponse(
            items=result["items"],
            total=result["total"],
            page=result["page"],
            page_size=result["page_size"],
            total_pages=result["total_pages"],
        )
    )


@router.get("/episodic/{memory_id}", summary="情景记忆详情", description="获取指定情景记忆的详细信息", tags=["Brain Memory"])
def episodic_detail(memory_id: int, service: BrainMemoryService = Depends()):
    """获取情景记忆详情。Args: memory_id (int) 记忆ID; service (BrainMemoryService) 记忆服务。Returns: dict 成功响应"""
    row = service.episodic_detail(memory_id)
    return success(data=row)


@router.post("/episodic/{memory_id}/consolidate", summary="固话情景记忆", description="将情景记忆固化为语义记忆", tags=["Brain Memory"])
def episodic_consolidate(
    memory_id: int,
    request: Request,
    service: BrainMemoryService = Depends(),
):
    """固话情景记忆为语义记忆。
    Args: memory_id (int) 记忆ID; request (Request) HTTP请求; service (BrainMemoryService) 记忆服务。
    Returns: dict 成功响应"""
    auth_header = request.headers.get("Authorization", "")
    result = service.episodic_consolidate(memory_id, auth_header)
    return success(data=result)


@router.get("/dashboard", summary="记忆仪表盘", description="获取记忆系统仪表盘统计数据", tags=["Brain Memory"])
def dashboard(service: BrainMemoryService = Depends()):
    """获取记忆系统仪表盘统计。Args: service (BrainMemoryService) 记忆服务。Returns: dict 成功响应"""
    result = service.dashboard()
    return success(data=result)


@router.post("/semantic/abstract", summary="语义抽象", description="从源数据提取语义抽象知识", tags=["Brain Memory"])
def semantic_abstract(body: SemanticAbstract, request: Request, service: BrainMemoryService = Depends()):
    """从源数据提取语义抽象。
    Args: body (SemanticAbstract) 语义抽象体; request (Request) HTTP请求; service BrainMemoryService。
    Returns: dict 成功响应"""
    result = service.semantic_abstract(
        source_type=body.source_type,
        source_id=body.source_id,
        abstraction_level=body.abstraction_level,
        auth_header=request.headers.get("Authorization", ""),
    )
    return success(data=result)


@router.get("/semantic/search", summary="语义搜索", description="搜索语义记忆内容", tags=["Brain Memory"])
def semantic_search(
    query: str = Query(...),
    limit: int = Query(10, ge=1, le=100),
    service: BrainMemoryService = Depends(),
):
    """语义搜索记忆内容。Args: query (str) 搜索关键词; limit (int) 返回条数; service (BrainMemoryService) 记忆服务。Returns: dict 成功响应"""
    result = service.semantic_search(query=query, limit=limit)
    return success(data=result)


@router.post("/procedural/learn", status_code=201, summary="学习程序记忆", description="学习并存储程序性记忆模式", tags=["Brain Memory"])
def procedural_learn(body: ProceduralLearn, service: BrainMemoryService = Depends()):
    """学习程序性记忆模式。Args: body (ProceduralLearn) 程序学习体; service (BrainMemoryService) 记忆服务。Returns: dict 成功响应"""
    result = service.procedural_learn(
        pattern_name=body.pattern_name,
        trigger_conditions=body.trigger_conditions,
        action_sequence=body.action_sequence,
        success_rate=body.success_rate,
    )
    return success(data=result)


@router.post("/procedural/recall", summary="召回程序记忆", description="根据上下文召回程序性记忆", tags=["Brain Memory"])
def procedural_recall(body: ProceduralRecall, service: BrainMemoryService = Depends()):
    """根据上下文召回程序性记忆。Args: body (ProceduralRecall) 程序召回体; service (BrainMemoryService) 记忆服务。Returns: dict 成功响应"""
    result = service.procedural_recall(trigger_context=body.trigger_context)
    return success(data=result)


@router.post("/decay", summary="记忆衰减", description="对超过时间阈值的记忆执行衰减", tags=["Brain Memory"])
def memory_decay(body: MemoryDecay, service: BrainMemoryService = Depends()):
    """对超过阈值的记忆执行衰减。Args: body (MemoryDecay) 衰减设置体; service (BrainMemoryService) 记忆服务。Returns: dict 成功响应"""
    result = service.memory_decay(hours_threshold=body.hours_threshold)
    return success(data=result)
