"""RL 路由服务，整合 RouteOptimizer 与 RouterLearner，提供统一路由与帕累托优化入口。"""

from cloud.app.services.brain.rl_route_optimizer import RouteOptimizer
from cloud.app.services.brain.rl_router_learner import RouterLearner
from shared.base_service import BaseService


class RLRoutingService(BaseService):
    """RLRouting 服务类。"""

    def __init__(self, db=None):
        super().__init__(db=db)
        self._learner = RouterLearner(db=db)
        self._optimizer = RouteOptimizer(db=db)

    def route_task(self, task_type: str, task_content: str, source: str) -> dict:
        """route_task 操作。

        Args:
            task_type: 描述
            task_content: 描述
            source: 描述

        Returns:
            描述
        """
        return self._learner.route_task(task_type=task_type, task_content=task_content, source=source)

    def log_result(
        self,
        task_id: str,
        task_type: str,
        source: str,
        strategy_used: str,
        routed_to: str,
        duration_ms: int,
        success: int,
    ) -> dict:
        """log_result 操作。

        Args:
            task_id: 描述
            task_type: 描述
            source: 描述
            strategy_used: 描述
            routed_to: 描述
            duration_ms: 描述
            success: 描述

        Returns:
            描述
        """
        return self._learner.log_result(
            task_id=task_id,
            task_type=task_type,
            source=source,
            strategy_used=strategy_used,
            routed_to=routed_to,
            duration_ms=duration_ms,
            success=success,
        )

    def get_stats(self, task_type: str = None) -> dict:
        """获取统计。

        Args:
            task_type: 描述

        Returns:
            描述
        """
        return self._learner.get_stats(task_type=task_type)

    def get_strategies(self, task_type: str = None) -> list:
        """get_strategies 操作。

        Args:
            task_type: 描述

        Returns:
            描述
        """
        return self._learner.get_strategies(task_type=task_type)

    def get_strategy(self, strategy_id: int) -> dict:
        """获取策略。

        Args:
            strategy_id: 描述

        Returns:
            描述
        """
        return self._learner.get_strategy(strategy_id=strategy_id)

    def _load_pareto_objectives(self) -> dict:
        """从配置加载帕累托优化目标定义，并校验方向合法性。

        Returns:
            dict: 以目标名称为键，值为 {"direction": "maximize"/"minimize", "weight": float} 的字典。
        """
        return self._optimizer._load_pareto_objectives()

    def _dominates(self, a: dict, b: dict, objectives: dict) -> bool:
        """判断解 a 是否帕累托支配解 b（a 在所有目标上不差于 b，且至少在一个目标上严格优于 b）。"""
        return self._optimizer._dominates(a=a, b=b, objectives=objectives)

    def pareto_route(self, task_type: str, task_content: str, constraints: dict = None) -> dict:
        """基于帕累托最优的多目标路由选择。

        从活跃路由策略中计算 success_rate、avg_duration_ms、load 等目标值，
        应用约束过滤器后生成非支配解集，并返回帕累托前沿。

        Args:
            task_type: 任务类型标识，用于匹配策略的 task_type_pattern。
            task_content: 任务内容文本，可用于基于关键字的约束过滤。
            constraints: 可选约束字典，支持 min_success_rate、max_duration_ms、max_load
                （以及任意与目标名称匹配的 min_<obj> / max_<obj> 约束）。

        Returns:
            dict: 包含以下键的字典：
                - pareto_front (list): 帕累托前沿（非支配解集），按权重综合得分降序排列。
                - non_dominated_solutions (list): 全部候选解，含支配状态标记。
                - total_strategies (int): 候选策略总数。
                - pareto_count (int): 帕累托前沿中的解数量。
                - filtered (bool): 约束过滤后是否无解（仅在过滤后为空时出现）。
                - objectives (dict): 使用的帕累托目标定义。
        """
        return self._optimizer.pareto_route(task_type=task_type, task_content=task_content, constraints=constraints)
