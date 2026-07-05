"""Manage holographic memory association workflows across memory entries."""

import json
import logging

from fastapi import HTTPException
from starlette import status

from cloud.app.repositories.holographic_repository import MemoryAssociationsRepository
from cloud.app.repositories.memory_entry_repo import MemoryEntriesRepository
from cloud.app.services.compliance_svc.holographic_association import _n404
from shared.base_service import BaseService
from shared.datetime_utils import now as _now

logger = logging.getLogger(__name__)


class HolographicService(BaseService):
    """全息记忆关联服务，管理记忆条目之间的关联与图谱查询。"""

    def __init__(self, db):
        """初始化 HolographicService。

        参数:
            db: 数据库连接对象。
        """
        super().__init__(db)

    def create_association(self, memory_id_a: int, memory_id_b: int, relation_type: str = "related", weight: float = 1.0) -> dict:
        """在两个记忆条目之间创建关联。

        参数:
            memory_id_a: 记忆条目 A 的 ID。
            memory_id_b: 记忆条目 B 的 ID。
            relation_type: 关联类型，默认为 "related"。
            weight: 关联权重，默认为 1.0。

        返回:
            包含关联信息的字典。

        异常:
            HTTPException 400: 不允许自身关联。
            HTTPException 404: 任一记忆条目不存在。
        """
        if memory_id_a == memory_id_b:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot associate a memory with itself")
        me_repo = MemoryEntriesRepository(self._connection())
        if not me_repo.get_by_id(memory_id_a):
            raise _n404(f"Memory entry {memory_id_a}")
        if not me_repo.get_by_id(memory_id_b):
            raise _n404(f"Memory entry {memory_id_b}")
        repo = MemoryAssociationsRepository(self._connection())
        assoc_id = repo.upsert_pair(memory_id_a, memory_id_b, relation_type, weight)
        a, b = (memory_id_a, memory_id_b) if memory_id_a < memory_id_b else (memory_id_b, memory_id_a)
        return {"id": assoc_id, "memory_id_a": a, "memory_id_b": b, "relation_type": relation_type, "weight": weight}

    def get_associations(self, memory_id: int, limit: int = 50) -> list:
        """获取指定记忆条目的关联列表。

        参数:
            memory_id: 记忆条目 ID。
            limit: 返回结果数量上限，默认为 50。

        返回:
            关联信息字典列表，每个条目包含关联数据及关联的记忆条目。

        异常:
            HTTPException 404: 记忆条目不存在。
        """
        me_repo = MemoryEntriesRepository(self._connection())
        if not me_repo.get_by_id(memory_id):
            raise _n404(f"Memory entry {memory_id}")
        repo = MemoryAssociationsRepository(self._connection())
        rows = repo.find_by_memory_id(memory_id, limit)
        result = []
        for r in rows:
            other_id = r["memory_id_b"] if r["memory_id_a"] == memory_id else r["memory_id_a"]
            other = me_repo.get_by_id(other_id)
            result.append(
                {
                    "id": r["id"],
                    "memory_id_a": r["memory_id_a"],
                    "memory_id_b": r["memory_id_b"],
                    "relation_type": r["relation_type"],
                    "weight": r["weight"],
                    "related_memory": other,
                }
            )
        return result

    def holographic_graph(self, memory_id: int, depth: int = 3) -> dict:
        """获取全息关联图，从指定记忆开始递归遍历关联。

        参数:
            memory_id: 根记忆条目 ID。
            depth: 递归遍历深度，默认为 3。

        返回:
            包含根条目、深度和总节点数的字典。

        异常:
            HTTPException 404: 记忆条目不存在。
        """
        me_repo = MemoryEntriesRepository(self._connection())
        entry = me_repo.get_by_id(memory_id)
        if not entry:
            raise _n404(f"Memory entry {memory_id}")
        repo = MemoryAssociationsRepository(self._connection())
        visited = {memory_id}
        root = dict(entry)
        root["associations"] = self._traverse(memory_id, depth, visited, repo, me_repo)
        return {"entry": root, "depth": depth, "total_nodes": len(visited)}

    def _traverse(self, memory_id: int, depth: int, visited: set, repo, me_repo, max_per_level: int = 10) -> list:
        """递归遍历记忆关联图。

        参数:
            memory_id: 当前记忆条目 ID。
            depth: 剩余递归深度。
            visited: 已访问节点 ID 集合。
            repo: MemoryAssociationsRepository 实例。
            me_repo: MemoryEntriesRepository 实例。
            max_per_level: 每层最大返回节点数，默认为 10。

        返回:
            关联节点字典列表。
        """
        if depth <= 0:
            return []
        rows = repo.find_by_memory_id(memory_id, max_per_level * 2)
        result = []
        count = 0
        for r in rows:
            if count >= max_per_level:
                break
            other_id = r["memory_id_b"] if r["memory_id_a"] == memory_id else r["memory_id_a"]
            if other_id in visited:
                continue
            visited.add(other_id)
            other = me_repo.get_by_id(other_id)
            if not other:
                continue
            node = dict(other)
            node["relation_type"] = r["relation_type"]
            node["weight"] = r["weight"]
            node["associations"] = self._traverse(other_id, depth - 1, visited, repo, me_repo, max_per_level)
            result.append(node)
            count += 1
        return result

    def delete_association(self, association_id: int) -> dict:
        """删除指定关联记录。

        参数:
            association_id: 关联记录 ID。

        返回:
            包含被删除 ID 的字典。

        异常:
            HTTPException 404: 关联记录不存在。
        """
        repo = MemoryAssociationsRepository(self._connection())
        row = repo.get_by_id(association_id)
        if not row:
            raise _n404("Association")
        repo.delete_by_id(association_id)
        return {"deleted_id": association_id}

    def auto_associate(self, entry_id: int, entry: dict) -> list:
        """根据标签、来源和时间维度自动创建关联。

        参数:
            entry_id: 记忆条目 ID。
            entry: 记忆条目数据字典。

        返回:
            新创建的关联字典列表。
        """
        new_assocs = []
        for method in [self._associate_by_tags, self._associate_by_source, self._associate_by_temporal]:
            try:
                new_assocs.extend(method(entry_id, entry) or [])
            except HTTPException:
                logger.warning("Failed to auto associate memory entry %s", entry_id, exc_info=True)
        return new_assocs

    def _associate_by_tags(self, entry_id: int, entry: dict) -> list:
        """根据共享标签自动创建关联。

        参数:
            entry_id: 记忆条目 ID。
            entry: 记忆条目数据字典。

        返回:
            新创建的关联字典列表。
        """
        tags_raw = entry.get("context_tags", "[]")
        if isinstance(tags_raw, str):
            try:
                tags = json.loads(tags_raw)
            except (json.JSONDecodeError, TypeError):
                return []
        elif isinstance(tags_raw, list):
            tags = tags_raw
        else:
            return []
        if not tags:
            return []
        results = []
        me_repo = MemoryEntriesRepository(self._connection())
        for tag in tags:
            rows = me_repo.db.execute(
                "SELECT id FROM memory_entries WHERE id != ? AND is_active = 1 AND context_tags LIKE ?",
                (entry_id, f"%{tag}%"),
            ).fetchall()
            for row in rows:
                r = self.create_association(entry_id, row["id"], "shared_tag", 0.8)
                results.append(r)
        return results

    def _associate_by_source(self, entry_id: int, entry: dict) -> list:
        """根据相同来源自动创建关联。

        参数:
            entry_id: 记忆条目 ID。
            entry: 记忆条目数据字典。

        返回:
            新创建的关联字典列表。
        """
        source_id = entry.get("source_id", "")
        if not source_id:
            return []
        me_repo = MemoryEntriesRepository(self._connection())
        rows = me_repo.db.execute(
            "SELECT id FROM memory_entries WHERE id != ? AND is_active = 1 AND source_id = ?",
            (entry_id, source_id),
        ).fetchall()
        results = []
        for row in rows:
            r = self.create_association(entry_id, row["id"], "same_source", 0.6)
            results.append(r)
        return results

    def _associate_by_temporal(self, entry_id: int, entry: dict) -> list:
        """根据相同记忆类型和创建日期自动创建关联。

        参数:
            entry_id: 记忆条目 ID。
            entry: 记忆条目数据字典。

        返回:
            新创建的关联字典列表。
        """
        memory_type = entry.get("memory_type", "")
        if not memory_type:
            return []
        me_repo = MemoryEntriesRepository(self._connection())
        rows = me_repo.db.execute(
            "SELECT id FROM memory_entries WHERE id != ? AND is_active = 1 AND memory_type = ? AND date(created_at) = date(?) LIMIT 20",
            (entry_id, memory_type, entry.get("created_at", _now())),
        ).fetchall()
        results = []
        for row in rows:
            r = self.create_association(entry_id, row["id"], "temporal", 0.5)
            results.append(r)
        return results
