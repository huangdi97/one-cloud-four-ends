"""记忆门控路由。"""

from typing import Optional

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel

from cloud.app.services.brain.memory_gate_service import MemoryGateService
from shared.auth_scope import require_scope
from shared.base import PaginatedResponse, success

router = APIRouter(prefix="/memory", tags=["记忆系统"])


class GateCreate(BaseModel):
    name: str
    source_type: str
    importance_threshold: float = 0.5
    ttl_days: int = 90
    retention_policy: str = "normal"


class EntryCreate(BaseModel):
    title: str
    content: str
    memory_type: str = "insight"
    source_type: str = ""
    source_id: Optional[str] = None
    importance: float = 0.5
    context_tags: list[str] = []


class RecallRequest(BaseModel):
    query: str
    memory_types: list[str] = []
    min_importance: float = 0.5
    max_results: int = 10


@router.post("/gates", status_code=201, tags=["记忆系统"])
def create_gate(
    body: GateCreate,
    request: Request,
    current_user=Depends(require_scope("visit")),
    service: MemoryGateService = Depends(),
):
    """创建新的记忆门。

    Args:
        body: 门创建参数（名称、来源类型、重要性阈值等）

    Returns: 创建成功的门信息
    """
    result = service.create_gate(
        name=body.name,
        source_type=body.source_type,
        importance_threshold=body.importance_threshold,
        ttl_days=body.ttl_days,
        retention_policy=body.retention_policy,
    )
    return success(data=result)


@router.get("/gates", tags=["记忆系统"])
def list_gates(service: MemoryGateService = Depends()):
    """获取所有记忆门列表。

    Args:
        service: 记忆门服务

    Returns: 门列表
    """
    return success(data=service.list_gates())


@router.post("/entries", status_code=201, tags=["记忆系统"])
def create_entry(
    body: EntryCreate,
    request: Request,
    current_user=Depends(require_scope("visit")),
    service: MemoryGateService = Depends(),
):
    """创建新的记忆条目。

    Args:
        body: 条目创建参数（标题、内容、记忆类型等）

    Returns: 创建成功的条目信息
    """
    uid = int(current_user["sub"])
    result = service.create_entry(
        title=body.title,
        content=body.content,
        memory_type=body.memory_type,
        source_type=body.source_type,
        source_id=body.source_id,
        importance=body.importance,
        context_tags=body.context_tags,
        uid=uid,
    )
    return success(data=result)


@router.get("/entries", tags=["记忆系统"])
def list_entries(
    memory_type: Optional[str] = Query(None),
    importance_min: Optional[float] = Query(None),
    keyword: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    service: MemoryGateService = Depends(),
):
    """分页查询记忆条目，支持按类型、重要性和关键词过滤。

    Args:
        memory_type:   记忆类型筛选
        importance_min: 最小重要性阈值
        keyword:       关键词搜索
        page:          页码（从1开始）
        page_size:     每页数量

    Returns: 分页结果（含条目列表、总数、总页数）
    """
    total, total_pages, items = service.list_entries(
        memory_type=memory_type,
        importance_min=importance_min,
        keyword=keyword,
        page=page,
        page_size=page_size,
    )
    return success(
        data=PaginatedResponse(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
        )
    )


@router.get("/entries/{entry_id}", tags=["记忆系统"])
def get_entry(entry_id: int, service: MemoryGateService = Depends()):
    """根据 ID 获取单条记忆条目。

    Args:
        entry_id: 条目 ID

    Returns: 条目详情
    """
    return success(data=service.get_entry(entry_id))


@router.post("/recall", tags=["记忆系统"])
def recall(
    body: RecallRequest,
    request: Request,
    current_user=Depends(require_scope("visit")),
    service: MemoryGateService = Depends(),
):
    """通过语义查询召回相关记忆。

    Args:
        body: 召回请求（查询文本、记忆类型、最小重要性等）

    Returns: 匹配的记忆条目列表
    """
    result = service.recall(
        query=body.query,
        memory_types=body.memory_types,
        min_importance=body.min_importance,
        max_results=body.max_results,
    )
    return success(data=result)


@router.post("/auto-store/{source_type}/{source_id}", status_code=201, tags=["记忆系统"])
def auto_store(
    source_type: str,
    source_id: str,
    request: Request,
    current_user=Depends(require_scope("visit")),
    service: MemoryGateService = Depends(),
):
    """根据来源类型和 ID 自动提取并存储记忆。

    Args:
        source_type: 来源类型
        source_id:   来源 ID

    Returns: 自动存储结果
    """
    uid = int(current_user["sub"])
    auth = request.headers.get("Authorization", "")
    return success(
        data=service.auto_store(
            source_type=source_type,
            source_id=source_id,
            uid=uid,
            auth_header=auth,
        )
    )


@router.get("/dashboard", tags=["记忆系统"])
def dashboard(service: MemoryGateService = Depends()):
    """获取记忆系统仪表盘统计数据。

    Args:
        service: 记忆门服务

    Returns: 仪表盘统计信息
    """
    return success(data=service.dashboard())
