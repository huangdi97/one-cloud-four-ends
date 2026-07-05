"""脑记忆进化服务门面。"""

from fastapi import Depends

from cloud.app.database import get_db
from cloud.app.services.brain.brain_evolution_stage import MemoryEvolutionStage
from cloud.app.services.brain.brain_folding_stage import MemoryFoldingStage
from cloud.app.services.brain.brain_unfolding_stage import MemoryUnfoldingStage
from shared.base_service import BaseService


class BrainEvolutionService(BaseService):
    """按演化阶段聚合单条演化、折叠压缩与展开还原能力。"""

    def __init__(self, db=Depends(get_db)):
        super().__init__(db)
        self._evolution_stage = MemoryEvolutionStage(self.db)
        self._folding_stage = MemoryFoldingStage(self.db)
        self._unfolding_stage = MemoryUnfoldingStage(self.db)

    def _read_memory(self, memory_id: int, memory_type: str) -> dict | None:
        return self._evolution_stage.read_memory(memory_id, memory_type)

    def _update_memory_field(self, memory_id: int, memory_type: str, field: str, new_value: str) -> bool:
        return self._evolution_stage.update_memory_field(memory_id, memory_type, field, new_value)

    def evolve_memory(self, memory_id: int, new_evidence: str, memory_type: str = "episodic") -> dict:
        """合并新证据并记录演化日志。"""
        return self._evolution_stage.evolve_memory(memory_id, new_evidence, memory_type)

    def get_evolution_history(self, memory_id: int) -> list[dict]:
        """读取指定记忆的演化历史。"""
        return self._evolution_stage.get_evolution_history(memory_id)

    def fold_memories(self, memory_ids: list[int]) -> dict:
        """将多条记忆折叠压缩为一条摘要记忆。"""
        return self._folding_stage.fold_memories(memory_ids)

    def get_folded(self, memory_id: int) -> dict:
        """读取 cognitive_fold 记忆及其来源链。"""
        return self._unfolding_stage.get_folded(memory_id)

    def unfold_memory(self, pattern_id: int) -> list[dict]:
        """展开 cognitive_fold 记忆，返回原始来源记忆列表。"""
        return self._unfolding_stage.unfold_memory(pattern_id)
