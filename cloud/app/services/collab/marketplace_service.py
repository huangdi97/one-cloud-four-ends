"""智能体市场服务，负责效果度量与基准测试管理。"""

import json
from datetime import datetime
from typing import Optional
from uuid import uuid4

from cloud.app.repositories import (
    AgentMarketplaceRepository,
    EffectMetricsRepository,
)
from cloud.app.services.collab.marketplace_benchmark import MarketplaceBenchmarkMixin
from shared.base_service import BaseService


class MarketplaceService(MarketplaceBenchmarkMixin, BaseService):
    """智能体市场服务，提供效果度量上报、基准测试与仪表盘统计。"""

    def log_metric(
        self,
        agent_role: str,
        metric_type: str,
        metric_value: float,
        metric_unit: str = "",
        period_start: str = "",
        period_end: str = "",
    ) -> dict:
        """上报效果度量数据点。

        Args:
            agent_role: Agent 角色
            metric_type: 指标类型
            metric_value: 指标值
            metric_unit: 单位
            period_start: 周期起始
            period_end: 周期结束

        Returns:
            含 metric_id 的确认信息
        """
        metrics_repo = EffectMetricsRepository(self._connection())
        metric_id = f"em:{uuid4().hex[:12]}"
        now = datetime.utcnow().isoformat()
        metrics_repo.create(
            {
                "metric_id": metric_id,
                "agent_role": agent_role,
                "metric_type": metric_type,
                "metric_value": metric_value,
                "metric_unit": metric_unit,
                "period_start": period_start or None,
                "period_end": period_end or None,
                "created_at": now,
            }
        )
        return {"metric_id": metric_id}

    def metrics_dashboard(self, agent_role: Optional[str] = None) -> list:
        """效果度量仪表盘汇总。

        Args:
            agent_role: 按 Agent 角色筛选

        Returns:
            按 agent_role+metric_type 分组的汇总数据
        """
        metrics_repo = EffectMetricsRepository(self._connection())
        rows = metrics_repo.dashboard(agent_role=agent_role)
        result = []
        for r in rows:
            result.append(
                {
                    "agent_role": r["agent_role"],
                    "metric_type": r["metric_type"],
                    "total": r["total"],
                    "avg_value": round(r["avg_value"], 4) if r["avg_value"] is not None else None,
                }
            )
        return result

    def publish_item(
        self,
        item_name: str,
        description: str,
        agent_config: dict,
        category: str,
        price_model: str,
        publisher_sub: str,
    ) -> dict:
        """发布市场模板。

        Args:
            item_name: 模板名称
            description: 描述
            agent_config: Agent 配置字典
            category: 类别
            price_model: 定价模式
            publisher_sub: 发布者标识

        Returns:
            含 item_id 的确认信息
        """
        marketplace_repo = AgentMarketplaceRepository(self._connection())
        item_id = f"mp:{uuid4().hex[:12]}"
        now = datetime.utcnow().isoformat()
        marketplace_repo.create(
            {
                "item_id": item_id,
                "item_name": item_name,
                "item_type": "template",
                "description": description or None,
                "agent_config": json.dumps(agent_config, ensure_ascii=False),
                "category": category or None,
                "price_model": price_model,
                "rating": 0.0,
                "download_count": 0,
                "enabled": 1,
                "publisher": str(publisher_sub),
                "created_at": now,
            }
        )
        return {"item_id": item_id}

    def discover_items(
        self,
        category: Optional[str] = None,
        price_model: Optional[str] = None,
        enabled: Optional[int] = None,
    ) -> list:
        """发现市场模板。

        Args:
            category: 按类别筛选
            price_model: 按定价模式筛选
            enabled: 按启用状态筛选

        Returns:
            模板列表
        """
        marketplace_repo = AgentMarketplaceRepository(self._connection())
        rows = marketplace_repo.list_filtered(category=category, price_model=price_model, enabled=enabled)
        result = []
        for r in rows:
            result.append(
                {
                    "item_id": r.get("item_id"),
                    "item_name": r.get("item_name"),
                    "item_type": r.get("item_type"),
                    "description": r.get("description"),
                    "agent_config": json.loads(r["agent_config"]) if r.get("agent_config") else {},
                    "category": r.get("category"),
                    "price_model": r.get("price_model"),
                    "rating": r.get("rating"),
                    "download_count": r.get("download_count"),
                    "enabled": bool(r.get("enabled")),
                    "publisher": r.get("publisher"),
                    "created_at": r.get("created_at"),
                }
            )
        return result
