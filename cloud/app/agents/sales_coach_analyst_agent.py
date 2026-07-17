"""SalesCoachAnalystAgent — 销售培训分析与辅导Agent。"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from cloud.app.agent_runtime.core.models import AgentIdentity
from cloud.app.agents.base_agent import AgentContext, AgentResponse, BaseAgent

logger = logging.getLogger(__name__)

_DEFAULT_SCORE = 50

_DIMENSIONS = ["product_knowledge", "visit_skill", "compliance_awareness", "objection_handling"]

__all__ = ["SalesCoachAnalystAgent"]


class SalesCoachAnalystAgent(BaseAgent):
    """销售培训分析师Agent，多维度评估并生成训练建议。"""

    def __init__(
        self,
        identity: AgentIdentity = None,
        llm_service: Any = None,
        tool_bridge: Any = None,
        memory_service: Any = None,
    ) -> None:
        self._identity = identity
        self._llm = llm_service
        self._tools = tool_bridge
        self._memory = memory_service

    async def execute(self, context: AgentContext) -> AgentResponse:
        agent_id = self._identity.key if self._identity else "unknown"
        logger.info("%s execute: %s", agent_id, context.message[:64])
        msg = context.message
        rep_id = self._parse_rep_id(msg)
        if rep_id is None:
            return AgentResponse(
                reply="无法从消息中解析代表ID，请提供格式如 REP-001 或 rep_xxx",
                actions=[{"agent": "sales_coach_analyst", "rep_id": None, "overall": 0}],
            )
        training_data = []
        if self._tools is not None:
            try:
                training_data = await self._tools.call("query_training_records", {"rep_id": rep_id}, "", "")
            except Exception:
                logger.exception("query_training_records failed")
        if not training_data:
            logger.info("No training data for rep %s, reporting empty result", rep_id)
            return AgentResponse(
                reply=f"销售代表 {rep_id} 暂无训练数据。请确认代表信息是否正确。",
                actions=[{"agent": "sales_coach_analyst", "rep_id": rep_id, "overall": 0}],
            )

        analysis = await self._analyze(rep_id, training_data)
        suggestions = self._generate_suggestions(analysis)

        output = [
            f"销售代表 {rep_id} 分析报告：",
            f"产品知识: {analysis.get('product_knowledge', 0)}/100",
            f"拜访技巧: {analysis.get('visit_skill', 0)}/100",
            f"合规意识: {analysis.get('compliance_awareness', 0)}/100",
            f"异议处理: {analysis.get('objection_handling', 0)}/100",
            f"综合评分: {analysis.get('overall', 0):.1f}/100",
            "训练建议：",
        ]
        for s in suggestions[:5]:
            output.append(f"  - {s}")
        reply = "\n".join(output)

        if self._tools is not None:
            try:
                await self._tools.call(
                    "create_notification",
                    {"title": f"销售培训分析-{rep_id}", "content": reply, "type": "coaching_alert"},
                    "",
                    "",
                )
            except Exception:
                logger.exception("Notification failed")

        if self._memory is not None:
            try:
                ns = self._memory.get_namespace(self._identity.key if self._identity else "sales_coach_analyst")
                ns.store(f"coach:{rep_id}", json.dumps({"analysis": analysis, "suggestions": suggestions}, ensure_ascii=False))
            except Exception:
                logger.exception("Memory write failed")

        return AgentResponse(
            reply=reply,
            actions=[{"agent": "sales_coach_analyst", "rep_id": rep_id, "overall": analysis.get("overall", 0)}],
        )

    def _default_capabilities(self) -> list[str]:
        return ["training_analysis", "coaching", "performance_evaluation"]

    def _parse_rep_id(self, msg: str) -> str | None:
        """从消息文本中提取销售代表ID（REP-001或rep_xxx格式）。"""
        match = re.search(r"(REP-\d+|rep_[a-zA-Z0-9_]+)", msg, re.IGNORECASE)
        return match.group(1) if match else None

    async def _analyze(self, rep_id: str, data: list) -> dict:
        """对代表训练数据做LLM多维度评分并计算综合分。"""
        scores = {}
        for d in data:
            dim = d.get("dimension", "")
            scores[dim] = d.get("score", _DEFAULT_SCORE)
        for dim in _DIMENSIONS:
            scores.setdefault(dim, _DEFAULT_SCORE)

        if self._llm is not None:
            try:
                data_json = json.dumps(data, ensure_ascii=False)
                prompt = (
                    f"分析销售代表{rep_id}的培训数据，从{_DIMENSIONS}四个维度打分(0-100)：\n{data_json}\n"
                    f'返回JSON: {{"product_knowledge":N,"visit_skill":N,"compliance_awareness":N,"objection_handling":N}}'
                )
                result = await self._llm.generate(prompt)
                scores.update(json.loads(result))
            except json.JSONDecodeError:
                logger.warning("LLM returned non-JSON for rep %s: %s", rep_id, result)
            except Exception:
                logger.exception("LLM analysis failed for rep %s", rep_id)

        valid_scores = [scores.get(d) for d in _DIMENSIONS if scores.get(d) is not None]
        if valid_scores:
            scores["overall"] = sum(valid_scores) / len(valid_scores)
        else:
            scores["overall"] = _DEFAULT_SCORE
        return scores

    def _generate_suggestions(self, analysis: dict) -> list:
        """根据各维度评分生成针对性训练建议（最多5条）。"""
        suggestions = []
        if analysis.get("product_knowledge", 100) < 70:
            suggestions.append("安排产品知识强化培训，重点掌握最新适应症和临床数据")
        if analysis.get("visit_skill", 100) < 70:
            suggestions.append("组织拜访技巧模拟训练，加强开场白和需求挖掘能力")
        if analysis.get("compliance_awareness", 100) < 80:
            suggestions.append("完成合规培训课程并考核，重点学习最新合规政策")
        if analysis.get("objection_handling", 100) < 70:
            suggestions.append("开展异议处理专项训练，建立常见异议应答话术库")
        if not suggestions:
            suggestions.append("维持当前水平，建议参加高级进阶培训")
        if len(suggestions) > 5:
            suggestions = suggestions[:5]
        return suggestions
