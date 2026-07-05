"""脑记忆服务，统一接口封装工作记忆、情景记忆、语义记忆与程序记忆操作。"""

from typing import Optional

from cloud.app.services.brain.memory_episodic_writer import EpisodicMemoryWriter
from cloud.app.services.brain.memory_procedural_writer import ProceduralMemoryWriter
from cloud.app.services.brain.memory_retriever import MemoryRetriever
from cloud.app.services.brain.memory_working_writer import WorkingMemoryWriter
from cloud.app.services.compliance_svc.holographic_service import HolographicService
from shared.base_service import BaseService


class BrainMemoryService(BaseService):
    """脑记忆门面服务，聚合写入组件和 MemoryRetriever 提供多类型记忆读写。"""

    def __init__(self, db):
        super().__init__(db)
        self._holographic_service = None
        self._working_writer = WorkingMemoryWriter(self.db)
        self._episodic_writer = EpisodicMemoryWriter(self.db, self._auto_associate)
        self._procedural_writer = ProceduralMemoryWriter(self.db, self._auto_associate)
        self._retriever = MemoryRetriever(self.db)

    @property
    def holographic_service(self):
        if self._holographic_service is None:
            self._holographic_service = HolographicService(self.db)
        return self._holographic_service

    def working_set(
        self,
        session_id: str,
        slot_key: str,
        slot_value: str,
        slot_type: str,
        ttl_seconds: int,
    ) -> dict:
        """设置工作记忆的槽位值并指定 TTL。"""
        return self._working_writer.working_set(session_id, slot_key, slot_value, slot_type, ttl_seconds)

    def working_get(self, session_id: str, slot_key: Optional[str] = None) -> dict:
        """获取工作记忆中指定 session 的槽位值。"""
        return self._retriever.working_get(session_id, slot_key)

    def working_clear(self, session_id: str) -> str:
        """清除指定 session 的工作记忆。"""
        return self._working_writer.working_clear(session_id)

    def working_refresh(self, session_id: str) -> dict:
        """刷新工作记忆的 TTL，防止过期。"""
        return self._working_writer.working_refresh(session_id)

    def episodic_store(
        self,
        event_type: str,
        title: str,
        description: str,
        context: dict,
        outcome: str,
        valence: float,
        intensity: float,
        involved_agents: list[str],
        related_entity_type: str,
        related_entity_id: Optional[int],
        uid: str,
    ) -> dict:
        """存储一条情景记忆，包含事件属性与参与 Agent。"""
        return self._episodic_writer.episodic_store(
            event_type,
            title,
            description,
            context,
            outcome,
            valence,
            intensity,
            involved_agents,
            related_entity_type,
            related_entity_id,
            uid,
        )

    def episodic_list(
        self,
        event_type: Optional[str] = None,
        outcome: Optional[str] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> dict:
        """分页查询情景记忆，支持按事件类型和日期筛选。"""
        return self._retriever.episodic_list(event_type, outcome, date_from, date_to, page, page_size)

    def episodic_detail(self, memory_id: int) -> dict:
        """获取单条情景记忆的详细信息。"""
        return self._retriever.episodic_detail(memory_id)

    def episodic_consolidate(self, memory_id: int, auth_header: str) -> dict:
        """将情景记忆巩固为长期语义记忆。"""
        return self._episodic_writer.episodic_consolidate(memory_id, auth_header)

    def dashboard(self) -> dict:
        """获取记忆系统概览仪表盘数据。"""
        return self._retriever.dashboard()

    def semantic_abstract(
        self,
        source_type: str,
        source_id: str,
        abstraction_level: str,
        auth_header: str = "",
    ) -> dict:
        """从源数据中提取抽象语义记忆。"""
        return self._episodic_writer.semantic_abstract(source_type, source_id, abstraction_level, auth_header)

    def semantic_search(self, query: str, limit: int = 10) -> dict:
        """语义搜索记忆库，返回最匹配的结果。"""
        return self._retriever.semantic_search(query, limit)

    def procedural_learn(
        self,
        pattern_name: str,
        trigger_conditions: str,
        action_sequence: str,
        success_rate: float,
    ) -> dict:
        """学习一个程序记忆模式，记录触发条件与动作序列。"""
        return self._procedural_writer.procedural_learn(pattern_name, trigger_conditions, action_sequence, success_rate)

    def procedural_recall(self, trigger_context: str) -> dict:
        """根据触发上下文召回匹配的程序记忆。"""
        return self._retriever.procedural_recall(trigger_context)

    def memory_decay(self, hours_threshold: int = 72) -> dict:
        """对超过阈值的记忆执行衰减清理。"""
        return self._procedural_writer.memory_decay(hours_threshold)

    def holographic_get(self, memory_id: int, depth: int = 3) -> dict:
        """获取指定记忆的全息关联网络。"""
        return self._retriever.holographic_get(memory_id, depth)

    def _auto_associate(self, entry_id: int, entry: dict):
        self.holographic_service.auto_associate(entry_id, entry)
