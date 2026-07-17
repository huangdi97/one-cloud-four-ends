"""Agent core — base class with identity, init, and simple insight methods."""

import logging
import os
from pathlib import Path

import yaml

from cloud.app.agent_runtime.core.model_router import ModelRouter
from cloud.app.agent_runtime.core.models import AgentIdentity, Insight
from cloud.app.agent_runtime.core.shared_state import SharedStateEntry, get_shared_state
from cloud.app.agent_runtime.memory.memory import Memory
from cloud.app.agent_runtime.safety.cost_governor import CostGovernor
from cloud.app.agent_runtime.safety.safety_guard import SafetyGuard
from cloud.app.agent_runtime.tools.tool_bridge import ToolBridge

logger = logging.getLogger(__name__)


class AgentCore:
    def __init__(self, identity: AgentIdentity, db=None):
        """Initialize agent core with identity, tools, memory, and safety guards."""
        self.identity = identity
        self.tools = ToolBridge()
        self.memory = Memory(db)
        self.cost_governor = CostGovernor(max_cost=identity.cost_budget)
        self.safety = SafetyGuard()
        self.model_router = ModelRouter(identity.model_preference)

    @classmethod
    def from_yaml(cls, path: str | os.PathLike) -> "AgentCore":
        """Create an AgentCore from a YAML config file."""
        path = Path(path)
        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f)
        identity = AgentIdentity(**data)
        return cls(identity)

    async def insights_for(self, page_id: str, user_id: str) -> list[Insight]:
        """Generate contextual insights based on agent type and page."""
        key = self.identity.key

        if key == "compliance_monitor":
            return await self._compliance_autonomous_cycle(page_id, user_id)
        elif key == "sales_suggestion":
            return await self._suggestion_insights(page_id, user_id)
        elif key == "anomaly_analysis":
            return await self._anomaly_autonomous_cycle(page_id, user_id)
        elif key == "knowledge_worker":
            return await self._knowledge_insights(page_id, user_id)
        elif key == "opportunity_scanner":
            return await self._opportunity_autonomous_cycle(page_id, user_id)
        else:
            return []

    async def execute_message(self, message: str, session_id: str = "", user_id: str = "") -> dict | None:
        """委托给专用 BaseAgent 实现执行消息（仅4个新Agent支持）。
        返回 None 表示不支持委托，调用方应走L4循环。
        返回 dict 包含 {reply, actions}。
        """
        try:
            key = self.identity.key
            if key == "competitor_crawler":
                from cloud.app.agents.competitor_crawler_agent import CompetitorCrawlerAgent

                agent = CompetitorCrawlerAgent(identity=self.identity)
            elif key == "knowledge_worker":
                from cloud.app.agents.knowledge_worker_agent import KnowledgeWorkerAgent

                agent = KnowledgeWorkerAgent(identity=self.identity)
            elif key == "opportunity_scanner":
                from cloud.app.agents.opportunity_scanner_agent import OpportunityScannerAgent

                agent = OpportunityScannerAgent(identity=self.identity)
            elif key == "sales_coach_analyst":
                from cloud.app.agents.sales_coach_analyst_agent import SalesCoachAnalystAgent

                agent = SalesCoachAnalystAgent(identity=self.identity)
            else:
                return None
            from cloud.app.agents.base_agent import AgentContext

            ctx = AgentContext(message=message, session_id=session_id, user_id=user_id)
            response = await agent.execute(ctx)
            return {"reply": response.reply, "actions": response.actions}
        except Exception:
            logger.exception("execute_message failed for %s", self.identity.key)
            return None

    async def _compliance_insights(self, page_id: str, user_id: str) -> list[Insight]:
        """Query compliance data for real insights."""
        try:
            from cloud.app.services.compliance_svc.decision_intel_service import DecisionIntelService

            svc = DecisionIntelService()
            dashboard = svc.dashboard()
            total = dashboard.get("total_cases", 0)
            red_flags = dashboard.get("red_flag_count", 0) if isinstance(dashboard, dict) else 0
            insights = []
            if total > 0:
                insights.append(
                    Insight(
                        agent_key=self.identity.key,
                        page_id=page_id,
                        summary=f"合规监控中：{total} 个案件，{red_flags} 个红灯",
                        details={"total_cases": total, "red_flags": red_flags},
                        confidence=0.9,
                    )
                )
                ss = get_shared_state()
                evidence = [
                    "来源: DecisionIntelService.dashboard",
                    f"数据: total_cases={total}, red_flags={red_flags}",
                    f"计算: red_flag_rate={red_flags / max(total, 1):.1%}",
                ]
                ss.write(
                    SharedStateEntry(
                        namespace="compliance.result",
                        key=f"insights_{page_id}_{user_id}",
                        value={"summary": f"合规监控中：{total} 个案件，{red_flags} 个红灯", "total_cases": total, "red_flags": red_flags},
                        confidence=0.9,
                        agent_key=self.identity.key,
                        evidence=evidence,
                    ),
                    caller_agent_key=self.identity.key,
                )
            return insights
        except Exception:
            return []

    async def _suggestion_insights(self, page_id: str, user_id: str) -> list[Insight]:
        """Query visit/HCP data for suggestion insights."""
        try:
            from cloud.app.services.rep_workbench.visit_service import VisitService

            svc = VisitService()
            visits = svc.list_visits()
            count = len(visits) if isinstance(visits, list) else 0
            if count > 0:
                insights = [
                    Insight(
                        agent_key=self.identity.key,
                        page_id=page_id,
                        summary=f"近期 {count} 条拜访记录，可基于拜访历史生成策略建议",
                        details={"visit_count": count},
                        confidence=0.85,
                    )
                ]
                ss = get_shared_state()
                evidence = [
                    "来源: VisitService.list_visits",
                    f"数据: visit_count={count}",
                    "计算: 基于拜访记录完整性评估",
                ]
                ss.write(
                    SharedStateEntry(
                        namespace="suggestion.result",
                        key=f"insights_{page_id}_{user_id}",
                        value={"summary": f"近期 {count} 条拜访记录", "visit_count": count},
                        confidence=0.85,
                        agent_key=self.identity.key,
                        evidence=evidence,
                    ),
                    caller_agent_key=self.identity.key,
                )
                return insights
            return []
        except Exception:
            return []

    async def _anomaly_insights(self, page_id: str, user_id: str) -> list[Insight]:
        """Query anomaly/context data."""
        try:
            from cloud.app.services.platform_svc.anomaly_context_service import AnomalyContextService

            svc = AnomalyContextService()
            if hasattr(svc, "list_anomalies"):
                anomalies = svc.list_anomalies()
                count = len(anomalies) if isinstance(anomalies, list) else 0
                if count > 0:
                    insights = [
                        Insight(
                            agent_key=self.identity.key,
                            page_id=page_id,
                            summary=f"检测到 {count} 条异常模式，可展开根因分析",
                            details={"anomaly_count": count},
                            confidence=0.8,
                        )
                    ]
                    ss = get_shared_state()
                    evidence = [
                        "来源: AnomalyContextService.list_anomalies",
                        f"数据: anomaly_count={count}",
                        "计算: 基于异常模式数量评估",
                    ]
                    ss.write(
                        SharedStateEntry(
                            namespace="analysis.result",
                            key=f"insights_{page_id}_{user_id}",
                            value={"summary": f"检测到 {count} 条异常模式", "anomaly_count": count},
                            confidence=0.8,
                            agent_key=self.identity.key,
                            evidence=evidence,
                        ),
                        caller_agent_key=self.identity.key,
                    )
                return insights
            return []
        except Exception:
            return []

    async def _knowledge_insights(self, page_id: str, user_id: str) -> list[Insight]:
        """Query knowledge graph for entity insights."""
        try:
            from cloud.app.services.brain.kg_service import KGService

            svc = KGService()
            dashboard = svc.dashboard()
            entity_count = dashboard.get("entity_count", 0) if isinstance(dashboard, dict) else 0
            rel_count = dashboard.get("relation_count", 0) if isinstance(dashboard, dict) else 0
            if entity_count > 0:
                return [
                    Insight(
                        agent_key=self.identity.key,
                        page_id=page_id,
                        summary=f"知识图谱：{entity_count} 实体，{rel_count} 关系，可探索关联",
                        details={"entities": entity_count, "relations": rel_count},
                        confidence=0.85,
                    )
                ]
            return []
        except Exception:
            return []

    async def _opportunity_insights(self, page_id: str, user_id: str) -> list[Insight]:
        """Query pipeline/opportunity data."""
        try:
            from cloud.app.services.rep_workbench.opportunity_service import OpportunityService

            svc = OpportunityService()
            pipeline = svc.get_pipeline()
            total_value = pipeline.get("total_value", 0) if isinstance(pipeline, dict) else 0
            stage_count = pipeline.get("stage_count", 0) if isinstance(pipeline, dict) else 0
            if stage_count and stage_count > 0:
                insights = [
                    Insight(
                        agent_key=self.identity.key,
                        page_id=page_id,
                        summary=f"管线总额 ¥{total_value:,.0f}，{stage_count} 个商机待推进",
                        details={"total_value": total_value, "stage_count": stage_count},
                        confidence=0.9,
                    )
                ]
                ss = get_shared_state()
                evidence = [
                    "来源: OpportunityService.get_pipeline",
                    f"数据: total_value={total_value}, stage_count={stage_count}",
                    "计算: 基于管线数据完整度评估",
                ]
                ss.write(
                    SharedStateEntry(
                        namespace="opportunity.result",
                        key=f"insights_{page_id}_{user_id}",
                        value={
                            "summary": f"管线总额 ¥{total_value:,.0f}，{stage_count} 个商机",
                            "total_value": total_value,
                            "stage_count": stage_count,
                        },
                        confidence=0.9,
                        agent_key=self.identity.key,
                        evidence=evidence,
                    ),
                    caller_agent_key=self.identity.key,
                )
                return insights
            return []
        except Exception:
            return []
