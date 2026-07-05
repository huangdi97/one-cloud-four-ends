"""Sage 记忆评分委托混入类。"""

from cloud.app.services.brain.sage_scoring_service import (
    determine_tier,
    normalize,
    score_episodic,
    score_procedural,
    score_semantic,
    score_world_tree,
    ts_to_epoch,
)


class SageScoringMixin:
    """Sage 记忆评分委托方法。"""

    def _normalize(self, value, min_val, max_val) -> float:
        """将值归一化到 [0, 1] 区间。

        Args:
            value: 原始值
            min_val: 最小值
            max_val: 最大值

        Returns:
            归一化后的浮点数
        """
        return normalize(value, min_val, max_val)

    @staticmethod
    def _ts_to_epoch(ts_str):
        """将时间戳字符串转换为 Unix epoch 秒数。

        Args:
            ts_str: 时间戳字符串

        Returns:
            Unix epoch 秒数
        """
        return ts_to_epoch(ts_str)

    @staticmethod
    def _determine_tier(score):
        """根据分数判定记忆分层（hot / warm / cold）。

        Args:
            score: 记忆评分

        Returns:
            分层标签字符串
        """
        return determine_tier(score)

    def _score_episodic(self, bms, tier_dist, comp):
        """对情景记忆进行评分。

        Args:
            bms: BrainMemoryService 实例
            tier_dist: 分层分布字典（hot / warm / cold 计数）
            comp: 组件计数字典

        Returns:
            评分的记忆数量
        """
        return score_episodic(self.repo, bms, tier_dist, comp)

    def _score_semantic(self, bms, tier_dist, comp):
        """对语义记忆进行评分。

        Args:
            bms: BrainMemoryService 实例
            tier_dist: 分层分布字典
            comp: 组件计数字典

        Returns:
            评分的记忆数量
        """
        return score_semantic(self.repo, bms, tier_dist, comp)

    def _score_procedural(self, bms, tier_dist, comp):
        """对程序性记忆进行评分。

        Args:
            bms: BrainMemoryService 实例
            tier_dist: 分层分布字典
            comp: 组件计数字典

        Returns:
            评分的记忆数量
        """
        return score_procedural(self.repo, bms, tier_dist, comp)

    def _score_world_tree(self, tier_dist, comp):
        """对世界树知识图谱进行评分。

        Args:
            tier_dist: 分层分布字典
            comp: 组件计数字典

        Returns:
            评分的实体数量
        """
        return score_world_tree(self.repo, self.db, tier_dist, comp)
