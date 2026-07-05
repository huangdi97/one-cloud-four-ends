"""因果推理服务，支持因果图谱构建、反事实模拟与 HCP 处方归因。"""

import json

from fastapi import HTTPException
from starlette import status

from cloud.app.repositories import (
    EpisodicMemoryRepository,
    KgEntitiesRepository,
)
from cloud.app.services.brain.causal_graph import CausalGraphMixin
from shared.base_service import BaseService


class CausalService(CausalGraphMixin, BaseService):
    """因果服务，提供因果图谱管理、反事实推断与归因分析功能。"""

    def causal_infer(self, features: dict, target: str, method: str = "linear") -> dict:
        """对输入特征执行因果推断，计算各特征的归一化权重。

        Args:
            features: 特征名到权重的映射
            target: 目标变量名
            method: 推断方法，默认 "linear"

        Returns:
            包含 method、target、feature_weights 的字典
        """
        total_weight = sum(abs(v) for v in features.values()) if features else 1.0
        weights = {k: round(v / total_weight if total_weight else 0, 4) for k, v in features.items()}
        return {
            "method": method,
            "target": target,
            "feature_weights": weights,
        }

    def hcp_prescription_attribution(self, hcp_entity_id: str, factors: list[str], date_range: dict) -> dict:
        """对 HCP 实体进行处方归因分析，关联情景记忆活动。

        Args:
            hcp_entity_id: HCP 实体 ID
            factors: 活动事件类型列表，用于过滤相关活动
            date_range: 日期范围字典，含 start 和 end 键

        Returns:
            包含 HCP 信息、关联活动列表及聚合指标的归因字典

        Raises:
            HTTPException: HCP 实体不存在时返回 404
        """
        kg_repo = KgEntitiesRepository(self._connection())
        em_repo = EpisodicMemoryRepository(self._connection())
        hcp_row = kg_repo.db.execute(
            "SELECT * FROM kg_entities WHERE entity_id=? AND status='active'",
            (hcp_entity_id,),
        ).fetchone()
        if not hcp_row:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail="HCP entity not found in KG")

        kg_id = hcp_row["id"]
        where_parts = ["(related_entity_type='kg_entity' AND related_entity_id=?)"]
        em_params = [kg_id]
        if factors:
            placeholders = ",".join(["?"] * len(factors))
            where_parts.append(f"event_type IN ({placeholders})")
            em_params.extend(factors)
        if date_range and date_range.get("start") and date_range.get("end"):
            where_parts.append("created_at BETWEEN ? AND ?")
            em_params.extend([date_range["start"], date_range["end"]])
        em_where = " AND ".join(where_parts)
        em_rows = em_repo.db.execute(
            f"SELECT * FROM episodic_memory WHERE {em_where} ORDER BY created_at DESC LIMIT 50",
            em_params,
        ).fetchall()

        activities = []
        for em in em_rows:
            ctx = json.loads(em["context"]) if isinstance(em["context"], str) and em["context"] else {}
            activities.append(
                {
                    "event_type": em["event_type"],
                    "title": em["title"],
                    "outcome": em["outcome"],
                    "valence": em["valence"],
                    "intensity": em["intensity"],
                    "context": ctx,
                    "created_at": em["created_at"],
                }
            )

        hcp_props = (
            json.loads(hcp_row.get("properties", "{}") or "{}")
            if isinstance(hcp_row.get("properties", "{}"), str)
            else (hcp_row.get("properties") or {})
        )
        attribution = {
            "hcp": {
                "entity_id": hcp_row["entity_id"],
                "name": hcp_row["name"],
                "entity_type": hcp_row["entity_type"],
                "properties": hcp_props,
            },
            "related_activities": activities,
            "activity_count": len(activities),
            "attribution_summary": f"{hcp_row['name']} 关联 {len(activities)} 条活动记录",
        }
        if activities:
            avg_valence = sum(a["valence"] for a in activities) / len(activities)
            avg_intensity = sum(a["intensity"] for a in activities) / len(activities)
            attribution["aggregated_metrics"] = {
                "avg_valence": round(avg_valence, 4),
                "avg_intensity": round(avg_intensity, 4),
            }
        return attribution
