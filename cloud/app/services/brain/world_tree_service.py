"""世界树服务管理层级化知识树结构。"""

import json
from typing import Optional

from cloud.app.services.brain.world_tree_query import WorldTreeQueryMixin
from cloud.app.services.brain.world_tree_search import (
    _build,
    _get_repos,
    _n404,
    _node_or_404,
    _now,
    _refresh_children,
    _refresh_path,
)
from shared.base_service import BaseService


class WorldTreeService(WorldTreeQueryMixin, BaseService):
    """世界树服务，管理层级化知识树结构的增删改查与同步。"""

    def create_node(
        self,
        name: str,
        description: str,
        parent_id: Optional[int],
        node_type: str,
        sort_order: int,
        metadata: dict,
        uid: int,
    ) -> dict:
        """创建世界树节点并计算路径层级。

        Args:
            name: 节点名称。
            description: 节点描述。
            parent_id: 可选的父节点ID，None表示根节点。
            node_type: 节点类型。
            sort_order: 同级排序值。
            metadata: 节点元数据字典。
            uid: 创建人用户ID。

        Returns:
            新节点的结构化字典。

        Raises:
            HTTPException: 当父节点不存在时抛出404。
        """
        nodes_repo, _, _, _ = _get_repos(self.db)
        if parent_id is None:
            path, level = "/" + name, 0
        else:
            p = nodes_repo.get_by_id(parent_id)
            if not p:
                raise _n404("Parent")
            path, level = p["path"] + "/" + name, p["level"] + 1
        node_id = nodes_repo.create(
            {
                "name": name,
                "description": description,
                "parent_id": parent_id,
                "path": path,
                "level": level,
                "node_type": node_type,
                "sort_order": sort_order,
                "metadata": json.dumps(metadata, ensure_ascii=False),
                "created_by": uid,
                "created_at": _now(),
                "updated_at": _now(),
            }
        )
        return _build(nodes_repo.get_by_id(node_id))

    def update_node(
        self,
        node_id: int,
        name: Optional[str] = None,
        description: Optional[str] = None,
        node_type: Optional[str] = None,
        sort_order: Optional[int] = None,
        metadata: Optional[dict] = None,
    ) -> dict:
        """更新世界树节点属性并刷新路径索引。

        Args:
            node_id: 目标节点ID。
            name: 可选的新节点名称。
            description: 可选的新节点描述。
            node_type: 可选的新节点类型。
            sort_order: 可选的新排序值。
            metadata: 可选的新元数据字典。

        Returns:
            更新后的节点结构化字典。

        Raises:
            HTTPException: 当节点不存在时抛出404。
        """
        nodes_repo, _, _, _ = _get_repos(self.db)
        n = _node_or_404(self.db, node_id)
        old_pid = n["parent_id"]
        now = _now()
        renamed = False
        updates = {}
        if name is not None:
            updates["name"] = name
            renamed = True
        if description is not None:
            updates["description"] = description
        if node_type is not None:
            updates["node_type"] = node_type
        if sort_order is not None:
            updates["sort_order"] = sort_order
        if metadata is not None:
            updates["metadata"] = json.dumps(metadata, ensure_ascii=False)
        if updates:
            nodes_repo.update(node_id, updates)
        nodes_repo.update_path(node_id, n.get("path", ""), n.get("level", 0), now)
        if renamed or old_pid != n["parent_id"]:
            _refresh_path(self.db, node_id)
            _refresh_children(self.db, node_id)
        return _build(nodes_repo.get_by_id(node_id))

    def delete_node(self, node_id: int) -> str:
        """删除世界树节点及其所有后代。

        Args:
            node_id: 目标节点ID。

        Returns:
            描述删除节点和后代数量的消息。

        Raises:
            HTTPException: 当节点不存在时抛出404。
        """
        nodes_repo, snapshots_repo, nml_repo, _ = _get_repos(self.db)
        _node_or_404(self.db, node_id)
        ids = nodes_repo.descendant_ids(node_id)
        nml_repo.delete_by_nodes(ids)
        snapshots_repo.delete_by_nodes(ids)
        for nid in reversed(ids):
            nodes_repo.delete(nid)
        return f"Deleted node {node_id} and {len(ids) - 1} descendants"

    def link_memory(self, node_id: int, memory_id: int) -> None:
        """将记忆条目关联到世界树节点。

        Args:
            node_id: 世界树节点ID。
            memory_id: 记忆条目ID。

        Returns:
            None。

        Raises:
            HTTPException: 当节点或记忆条目不存在时抛出404。
        """
        nodes_repo, _, nml_repo, mem_repo = _get_repos(self.db)
        _node_or_404(self.db, node_id)
        if not mem_repo.find_active_by_id(memory_id):
            raise _n404("Memory entry")
        nml_repo.create(
            {
                "node_id": node_id,
                "memory_entry_id": memory_id,
                "created_at": _now(),
            }
        )

    def unlink_memory(self, node_id: int, memory_id: int) -> None:
        """解除世界树节点与记忆条目的关联。

        Args:
            node_id: 世界树节点ID。
            memory_id: 记忆条目ID。

        Returns:
            None。

        Raises:
            HTTPException: 当节点不存在时抛出404。
        """
        _node_or_404(self.db, node_id)
        self.db.execute(
            "DELETE FROM node_memory_links WHERE node_id=? AND memory_entry_id=?",
            (node_id, memory_id),
        )
        self.db.commit()
