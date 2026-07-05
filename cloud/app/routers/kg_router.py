"""知识图谱路由。"""

from typing import Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from starlette import status

from cloud.app.services.brain.kg_service import KgService
from shared.auth_scope import require_scope
from shared.base import success

router = APIRouter(prefix="/kg", tags=["知识图谱"])


class KgEntityCreate(BaseModel):
    entity_id: Optional[str] = None
    entity_type: str
    name: str
    aliases: list[str] = []
    properties: dict = {}
    source_table: str = ""
    source_row_id: Optional[int] = None
    confidence: float = 1.0


class KgRelationCreate(BaseModel):
    source_entity_id: str
    target_entity_id: str
    relation_type: str
    weight: float = 1.0
    properties: dict = {}
    direction: str = "directed"
    confidence: float = 1.0


class KgSearch(BaseModel):
    query: str
    entity_types: list[str] = ["hcp"]
    max_depth: int = 2
    limit: int = 20


@router.post("/entities/create", status_code=status.HTTP_201_CREATED, tags=["知识图谱"])
def create_entity(
    data: KgEntityCreate,
    user: dict = Depends(require_scope("visit")),
    service: KgService = Depends(),
):
    """创建一个新的知识图谱实体。

    Args:
        data: 实体创建请求体。
        user: 当前认证用户。
        service: 知识图谱服务实例。

    Returns:
        包含新实体数据的响应。
    """
    return success(service.create_entity(data, user))


@router.get("/entities/list", tags=["知识图谱"])
def list_entities(
    entity_type: Optional[str] = Query(None),
    name: Optional[str] = Query(None),
    status_: str = Query("active", alias="status"),
    user: dict = Depends(require_scope("visit")),
    service: KgService = Depends(),
):
    """查询知识图谱实体列表。

    Args:
        entity_type: 实体类型筛选。
        name: 实体名称筛选。
        status_: 实体状态筛选。
        user: 当前认证用户。
        service: 知识图谱服务实例。

    Returns:
        包含实体列表的响应。
    """
    return success(service.list_entities(entity_type=entity_type, name=name, status_=status_))


@router.get("/entities/{entity_id}", tags=["知识图谱"])
def get_entity(
    entity_id: str,
    user: dict = Depends(require_scope("visit")),
    service: KgService = Depends(),
):
    """获取指定知识图谱实体的详情。

    Args:
        entity_id: 实体 ID。
        user: 当前认证用户。
        service: 知识图谱服务实例。

    Returns:
        包含实体数据的响应。
    """
    return success(service.get_entity(entity_id))


@router.delete("/entities/{entity_id}", tags=["知识图谱"])
def delete_entity(
    entity_id: str,
    user: dict = Depends(require_scope("visit")),
    service: KgService = Depends(),
):
    """删除指定的知识图谱实体。

    Args:
        entity_id: 实体 ID。
        user: 当前认证用户。
        service: 知识图谱服务实例。

    Returns:
        删除成功的响应。
    """
    return success(service.delete_entity(entity_id))


@router.post("/relations/create", status_code=status.HTTP_201_CREATED, tags=["知识图谱"])
def create_relation(
    data: KgRelationCreate,
    user: dict = Depends(require_scope("visit")),
    service: KgService = Depends(),
):
    """创建一条知识图谱关系。

    Args:
        data: 关系创建请求体。
        user: 当前认证用户。
        service: 知识图谱服务实例。

    Returns:
        包含新关系数据的响应。
    """
    return success(service.create_relation(data))


@router.get("/relations/list", tags=["知识图谱"])
def list_relations(
    source: Optional[str] = Query(None),
    target: Optional[str] = Query(None),
    relation_type: Optional[str] = Query(None),
    user: dict = Depends(require_scope("visit")),
    service: KgService = Depends(),
):
    """查询知识图谱关系列表。

    Args:
        source: 源实体 ID 筛选。
        target: 目标实体 ID 筛选。
        relation_type: 关系类型筛选。
        user: 当前认证用户。
        service: 知识图谱服务实例。

    Returns:
        包含关系列表的响应。
    """
    return success(service.list_relations(source=source, target=target, relation_type=relation_type))


@router.delete("/relations/{relation_id}", tags=["知识图谱"])
def delete_relation(
    relation_id: int,
    user: dict = Depends(require_scope("visit")),
    service: KgService = Depends(),
):
    """删除指定的知识图谱关系。

    Args:
        relation_id: 关系 ID。
        user: 当前认证用户。
        service: 知识图谱服务实例。

    Returns:
        删除成功的响应。
    """
    return success(service.delete_relation(relation_id))


@router.post("/search", tags=["知识图谱"])
def search_kg(
    data: KgSearch,
    user: dict = Depends(require_scope("visit")),
    service: KgService = Depends(),
):
    """搜索知识图谱，基于实体类型和深度进行查询。

    Args:
        data: 搜索请求体，包含查询文本和参数。
        user: 当前认证用户。
        service: 知识图谱服务实例。

    Returns:
        包含搜索结果的响应。
    """
    return success(service.search_kg(data))


@router.get("/graph/{entity_id}", tags=["知识图谱"])
def get_subgraph(
    entity_id: str,
    max_depth: int = Query(2),
    user: dict = Depends(require_scope("visit")),
    service: KgService = Depends(),
):
    """获取指定实体在知识图谱中的子图。

    Args:
        entity_id: 实体 ID。
        max_depth: 最大遍历深度。
        user: 当前认证用户。
        service: 知识图谱服务实例。

    Returns:
        包含子图数据的响应。
    """
    return success(service.get_subgraph(entity_id, max_depth))


@router.get("/dashboard", tags=["知识图谱"])
def dashboard(user: dict = Depends(require_scope("visit")), service: KgService = Depends()):
    """获取知识图谱仪表盘数据。

    Args:
        user: 当前认证用户。
        service: 知识图谱服务实例。

    Returns:
        包含仪表盘数据的响应。
    """
    return success(service.dashboard())
