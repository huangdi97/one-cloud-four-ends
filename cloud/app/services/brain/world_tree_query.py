"""世界树查询方法。"""

import json
from typing import Dict, List, Optional

from cloud.app.services.brain.world_tree_search import _build, _get_repos, _node_or_404


class WorldTreeQueryMixin:
    """世界树节点查询与记忆查询方法。"""

    def list_nodes(self, node_type: Optional[str] = None, parent_id: Optional[int] = None) -> List[dict]:
        nodes_repo, _, _, _ = _get_repos(self.db)
        conditions, params = [], []
        if node_type:
            conditions.append("node_type=?")
            params.append(node_type)
        if parent_id is not None:
            conditions.append("parent_id=?")
            params.append(parent_id)
        elif not node_type:
            conditions.append("parent_id IS NULL")
        rows = nodes_repo.list_all(
            conditions=conditions or None,
            params=params or None,
            order_by="sort_order, name",
        )
        return [_build(r) for r in rows]

    def get_node(self, node_id: int) -> dict:
        nodes_repo, _, nml_repo, _ = _get_repos(self.db)
        n = _node_or_404(self.db, node_id)
        d = _build(n)
        d["child_count"] = nodes_repo.count(conditions=["parent_id=?"], params=[node_id])
        d["memory_count"] = nml_repo.count_by_node(node_id)
        return d

    def get_children(self, node_id: int) -> List[dict]:
        nodes_repo, _, _, _ = _get_repos(self.db)
        _node_or_404(self.db, node_id)
        rows = nodes_repo.list_all(conditions=["parent_id=?"], params=[node_id], order_by="sort_order, name")
        return [_build(r) for r in rows]

    def get_ancestors(self, node_id: int) -> List[dict]:
        nodes_repo, _, _, _ = _get_repos(self.db)
        ancestors = []
        cur = _node_or_404(self.db, node_id)
        while cur["parent_id"] is not None:
            parent = nodes_repo.get_by_id(cur["parent_id"])
            if not parent:
                break
            ancestors.append(_build(parent))
            cur = parent
        return ancestors

    def get_node_memories(self, node_id: int) -> List[dict]:
        _node_or_404(self.db, node_id)
        rows = self.db.execute(
            "SELECT me.*, nml.relevance_score FROM memory_entries me "
            "JOIN node_memory_links nml ON me.id=nml.memory_entry_id "
            "WHERE nml.node_id=? AND me.is_active=1 "
            "ORDER BY nml.relevance_score DESC, me.importance DESC",
            (node_id,),
        ).fetchall()
        results = []
        for r in rows:
            d = dict(r)
            d["context_tags"] = json.loads(d.get("context_tags") or "[]")
            results.append(d)
        return results

    def get_full_tree(self) -> List[dict]:
        nodes_repo, _, nml_repo, _ = _get_repos(self.db)
        rows = nodes_repo.list_active_sorted()
        nodes = [_build(r) for r in rows]
        node_map: Dict[int, dict] = {n["id"]: n for n in nodes}
        for n in nodes:
            n["children"] = []
            n["memory_count"] = nml_repo.count_by_node(n["id"])
        roots = []
        for n in nodes:
            if n["parent_id"] is None:
                roots.append(n)
            elif n["parent_id"] in node_map:
                node_map[n["parent_id"]]["children"].append(n)
        return roots
