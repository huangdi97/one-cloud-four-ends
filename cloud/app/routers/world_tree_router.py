"""世界树记忆路由。"""

from typing import Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from starlette import status

from cloud.app.services.brain.world_tree_service import WorldTreeService
from shared.auth_scope import require_scope
from shared.base import success

router = APIRouter(prefix="/world-tree", tags=["记忆系统"])


class NodeCreate(BaseModel):
    name: str
    description: str = ""
    parent_id: Optional[int] = None
    node_type: str = "tag"
    sort_order: int = 0
    metadata: dict = {}


class NodeUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    node_type: Optional[str] = None
    sort_order: Optional[int] = None
    metadata: Optional[dict] = None


# 1
@router.post("/nodes", status_code=status.HTTP_201_CREATED, tags=["记忆系统"])
def create_node(
    body: NodeCreate,
    current_user: dict = Depends(require_scope("visit")),
    service: WorldTreeService = Depends(),
):
    """创建新的世界树节点。

    Args:
        body: 节点创建请求体。
        current_user: 当前登录用户信息。
        service: 世界树服务。

    Returns:
        创建的节点对象。
    """
    uid = int(current_user["sub"])
    row = service.create_node(
        name=body.name,
        description=body.description,
        parent_id=body.parent_id,
        node_type=body.node_type,
        sort_order=body.sort_order,
        metadata=body.metadata,
        uid=uid,
    )
    return success(data=row)


# 2
@router.get("/nodes", tags=["记忆系统"])
def list_nodes(
    node_type: Optional[str] = Query(None),
    parent_id: Optional[int] = Query(None),
    service: WorldTreeService = Depends(),
):
    """查询世界树节点列表。

    Args:
        node_type: 可选的按节点类型筛选。
        parent_id: 可选的按父节点 ID 筛选。
        service: 世界树服务。

    Returns:
        节点列表。
    """
    rows = service.list_nodes(node_type=node_type, parent_id=parent_id)
    return success(data=rows)


# 3
@router.get("/nodes/{node_id}", tags=["记忆系统"])
def get_node(node_id: int, service: WorldTreeService = Depends()):
    """获取单个世界树节点的详情。

    Args:
        node_id: 节点 ID。
        service: 世界树服务。

    Returns:
        节点详情。
    """
    d = service.get_node(node_id)
    return success(data=d)


# 4
@router.patch("/nodes/{node_id}", tags=["记忆系统"])
def update_node(
    node_id: int,
    body: NodeUpdate,
    current_user: dict = Depends(require_scope("visit")),
    service: WorldTreeService = Depends(),
):
    """更新指定世界树节点的信息。

    Args:
        node_id: 节点 ID。
        body: 节点更新请求体。
        current_user: 当前登录用户信息。
        service: 世界树服务。

    Returns:
        更新后的节点对象。
    """
    row = service.update_node(
        node_id=node_id,
        name=body.name,
        description=body.description,
        node_type=body.node_type,
        sort_order=body.sort_order,
        metadata=body.metadata,
    )
    return success(data=row)


# 5
@router.delete("/nodes/{node_id}", tags=["记忆系统"])
def delete_node(node_id: int, service: WorldTreeService = Depends()):
    """删除指定的世界树节点。

    Args:
        node_id: 节点 ID。
        service: 世界树服务。

    Returns:
        删除结果消息。
    """
    message = service.delete_node(node_id)
    return success(message=message)


# 6
@router.get("/nodes/{node_id}/children", tags=["记忆系统"])
def get_children(node_id: int, service: WorldTreeService = Depends()):
    """获取指定节点的直接子节点列表。

    Args:
        node_id: 节点 ID。
        service: 世界树服务。

    Returns:
        子节点列表。
    """
    rows = service.get_children(node_id)
    return success(data=rows)


# 7
@router.get("/nodes/{node_id}/ancestors", tags=["记忆系统"])
def get_ancestors(node_id: int, service: WorldTreeService = Depends()):
    """获取指定节点的所有祖先节点路径。

    Args:
        node_id: 节点 ID。
        service: 世界树服务。

    Returns:
        祖先节点列表。
    """
    ancestors = service.get_ancestors(node_id)
    return success(data=ancestors)


# 8
@router.post("/nodes/{node_id}/link/{memory_id}", status_code=status.HTTP_201_CREATED, tags=["记忆系统"])
def link_memory(node_id: int, memory_id: int, service: WorldTreeService = Depends()):
    """将记忆关联到指定世界树节点。

    Args:
        node_id: 节点 ID。
        memory_id: 记忆 ID。
        service: 世界树服务。

    Returns:
        关联结果消息。
    """
    service.link_memory(node_id, memory_id)
    return success(message="Linked")


# 9
@router.delete("/nodes/{node_id}/link/{memory_id}", tags=["记忆系统"])
def unlink_memory(node_id: int, memory_id: int, service: WorldTreeService = Depends()):
    """解除记忆与指定世界树节点的关联。

    Args:
        node_id: 节点 ID。
        memory_id: 记忆 ID。
        service: 世界树服务。

    Returns:
        解除关联结果消息。
    """
    service.unlink_memory(node_id, memory_id)
    return success(message="Unlinked")


# 10
@router.get("/nodes/{node_id}/memories", tags=["记忆系统"])
def get_node_memories(node_id: int, service: WorldTreeService = Depends()):
    """获取指定节点关联的所有记忆。

    Args:
        node_id: 节点 ID。
        service: 世界树服务。

    Returns:
        关联的记忆列表。
    """
    results = service.get_node_memories(node_id)
    return success(data=results)


# 11
@router.get("/tree/full", tags=["记忆系统"])
def get_full_tree(service: WorldTreeService = Depends()):
    """获取完整的世界树（从根节点开始）。

    Args:
        service: 世界树服务。

    Returns:
        完整的树结构数据。
    """
    roots = service.get_full_tree()
    return success(data=roots)
