"""因果图谱构建与持久化方法。"""

import json
import uuid
from typing import Optional

from fastapi import HTTPException
from starlette import status

from cloud.app.repositories import CausalGraphsRepository, CounterfactualScenariosRepository
from cloud.app.services.brain.causal_inference import CausalInferenceMixin


def _gen_graph_id() -> str:
    """生成因果图谱 ID，格式 cg:xxxxxxxx。"""
    return "cg:" + uuid.uuid4().hex[:8]


def _generate_template_graph(decision_id: str) -> dict:
    """生成包含默认节点和边的因果图谱模板。

    Args:
        decision_id: 决策 ID

    Returns:
        含 nodes 和 edges 的图谱数据字典
    """
    return {
        "nodes": [
            {"id": "factor_a", "label": "关键因子A", "weight": 0.5},
            {"id": "factor_b", "label": "关键因子B", "weight": 0.3},
            {"id": "outcome", "label": "目标结果", "weight": 0.0},
        ],
        "edges": [
            {"source": "factor_a", "target": "outcome", "strength": 0.5},
            {"source": "factor_b", "target": "outcome", "strength": 0.3},
        ],
    }


def _causal_graph_to_dict(row) -> dict:
    """将因果图谱数据库行转换为字典。

    Args:
        row: 数据库行或字典

    Returns:
        含解析后 graph_data 的图谱字典
    """
    return {
        "id": row["id"],
        "graph_id": row["graph_id"],
        "decision_id": row["decision_id"],
        "graph_data": json.loads(row["graph_data"]) if isinstance(row["graph_data"], str) else row["graph_data"],
        "summary": row["summary"],
        "node_count": row["node_count"],
        "edge_count": row["edge_count"],
        "created_by": row["created_by"],
        "created_at": row["created_at"],
    }


def _scenario_to_dict(row) -> dict:
    """将反事实场景数据库行转换为字典。

    Args:
        row: 数据库行或字典

    Returns:
        含解析后 variable_changes 和 predicted_outcome 的场景字典
    """
    return {
        "id": row["id"],
        "scenario_id": row["scenario_id"],
        "strategy_id": row["strategy_id"],
        "base_description": row["base_description"],
        "variable_changes": json.loads(row["variable_changes"]) if isinstance(row["variable_changes"], str) else row["variable_changes"],
        "predicted_outcome": json.loads(row["predicted_outcome"]) if isinstance(row["predicted_outcome"], str) else row["predicted_outcome"],
        "confidence": row["confidence"],
        "created_by": row["created_by"],
        "created_at": row["created_at"],
    }


class CausalGraphMixin(CausalInferenceMixin):
    """因果图谱持久化和反事实场景查询方法。"""

    def build_graph(self, decision_id: str, include_metrics: bool, user_id: int) -> dict:
        """构建因果图谱并持久化。"""
        cg_repo = CausalGraphsRepository(self._connection())
        graph_id = _gen_graph_id()
        graph_data = _generate_template_graph(decision_id)
        node_count = len(graph_data["nodes"])
        edge_count = len(graph_data["edges"])
        row_id = cg_repo.create(
            {
                "graph_id": graph_id,
                "decision_id": decision_id,
                "graph_data": json.dumps(graph_data, ensure_ascii=False),
                "node_count": node_count,
                "edge_count": edge_count,
                "created_by": user_id,
            }
        )
        row = cg_repo.get_by_id(row_id)
        return _causal_graph_to_dict(row)

    def get_graph(self, graph_id: str) -> dict:
        """获取指定因果图谱详情。

        Args:
            graph_id: 图谱 ID

        Returns:
            因果图谱记录字典

        Raises:
            HTTPException: 图谱不存在时返回 404
        """
        cg_repo = CausalGraphsRepository(self._connection())
        row = cg_repo.db.execute("SELECT * FROM causal_graphs WHERE graph_id=?", (graph_id,)).fetchone()
        if not row:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Causal graph not found")
        return _causal_graph_to_dict(row)

    def list_counterfactuals(self, strategy_id: Optional[str] = None, page: int = 1, page_size: int = 20) -> dict:
        """分页查询反事实模拟场景列表。

        Args:
            strategy_id: 可选，按策略 ID 过滤
            page: 页码，默认 1
            page_size: 每页条数，默认 20

        Returns:
            包含 items、total、page、page_size 的字典
        """
        cs_repo = CounterfactualScenariosRepository(self._connection())
        conditions = []
        params: list = []
        if strategy_id:
            conditions.append("strategy_id=?")
            params.append(strategy_id)
        total, total_pages, items = cs_repo.paginate(
            page=page,
            page_size=page_size,
            conditions=conditions or None,
            params=params or None,
            order_by="created_at DESC",
        )
        return {
            "items": [_scenario_to_dict(r) for r in items],
            "total": total,
            "page": page,
            "page_size": page_size,
        }
