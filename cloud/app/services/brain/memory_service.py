"""MemoryService — 管理 Agent 粒度的记忆命名空间。"""

from __future__ import annotations

from cloud.app.services.brain.memory_namespace import MemoryNamespace

__all__ = ["MemoryService"]


class MemoryService:
    """记忆服务，管理多个 Agent 的 MemoryNamespace 和跨Agent向量记忆检索。"""

    def __init__(self, vector_memory: object = None) -> None:
        self._namespaces: dict[str, MemoryNamespace] = {}
        self._vector_memory = vector_memory

    def set_vector_memory(self, vm: object) -> None:
        self._vector_memory = vm

    def get_namespace(self, agent_id: str) -> MemoryNamespace:
        if agent_id not in self._namespaces:
            self._namespaces[agent_id] = MemoryNamespace(namespace=agent_id)
        return self._namespaces[agent_id]

    def search_across_namespaces(self, query: str, agent_id: str, top_k: int = 3) -> list[dict]:
        """跨Agent命名空间搜索向量记忆。"""
        if self._vector_memory is None:
            return []
        try:
            results = self._vector_memory.search(agent_id, query, top_k=top_k, cross_agent=True)
            return results
        except Exception:
            return []
