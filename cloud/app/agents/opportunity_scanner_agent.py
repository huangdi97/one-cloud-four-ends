"""OpportunityScannerAgent — 商机扫描与评分Agent。"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any

from cloud.app.agent_runtime.core.models import AgentIdentity
from cloud.app.agents.base_agent import AgentContext, AgentResponse, BaseAgent

logger = logging.getLogger(__name__)

__all__ = ["OpportunityScannerAgent"]

_PRICE_ADJUST_THRESHOLD = 80
_REFERRAL_THRESHOLD = 60
_DEFAULT_SCORE = 50


class OpportunityScannerAgent(BaseAgent):
    """商机扫描Agent，分析招标/商机数据，三维度评分并生成策略。"""

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
        biddings = []
        opportunities = []
        if self._tools is not None:
            try:
                biddings = await self._tools.call("query_bidding", {"query": msg}, "", "")
                opportunities = await self._tools.call("query_opportunity", {"query": msg}, "", "")
            except Exception:
                logger.exception("Tool calls failed")

        if not biddings and not opportunities:
            return AgentResponse(
                reply="当前无商机数据。请稍后再试或联系管理员导入商机数据。",
                actions=[{"agent": "opportunity_scanner", "scored_count": 0, "notification": False}],
            )

        scored = []
        for item in biddings + opportunities:
            scores = await self._score_opportunity(item)
            stalled = self._detect_stalled(item)
            strategy = self._generate_strategy(scores, stalled)
            scored.append({**item, "scores": scores, "stalled": stalled, "strategy": strategy})

        output_lines = ["商机扫描结果："]
        for s in scored:
            output_lines.append(
                f"药品:{s.get('drug', '')} 适应症:{s.get('indication', '')} 区域:{s.get('region', '')} "
                f"药品评分:{s.get('scores', {}).get('drug_score', '-')} "
                f"适应症评分:{s.get('scores', {}).get('indication_score', '-')} "
                f"区域评分:{s.get('scores', {}).get('region_score', '-')} "
                f"停滞:{'是' if s.get('stalled') else '否'} 策略:{s.get('strategy', '')}"
            )
        reply = "\n".join(output_lines)

        notification = None
        if self._tools is not None:
            try:
                notification = await self._tools.call(
                    "create_notification",
                    {"title": "商机扫描报告", "content": reply, "type": "opportunity_scan"},
                    "",
                    "",
                )
            except Exception:
                logger.exception("Notification failed")

        return AgentResponse(
            reply=reply,
            actions=[{"agent": "opportunity_scanner", "scored_count": len(scored), "notification": notification is not None}],
        )

    def _default_capabilities(self) -> list[str]:
        return ["opportunity_scan", "bidding_analysis", "strategy_generation"]

    async def _score_opportunity(self, item: dict) -> dict:
        """用LLM对商机从药品竞争力、市场潜力、区域覆盖三维度评分。"""
        if self._llm is not None:
            try:
                prompt = (
                    f"对以下商机从三个维度打分(0-100)：药品竞争力、适应症市场潜力、区域覆盖度。"
                    f"药品:{item.get('drug', '')} 适应症:{item.get('indication', '')} 区域:{item.get('region', '')}\n"
                    f'返回JSON: {{"drug_score":N,"indication_score":N,"region_score":N}}'
                )
                result = await self._llm.generate(prompt)
                scores = json.loads(result)
                if not isinstance(scores, dict):
                    raise ValueError("LLM response is not a dict")
                required = {"drug_score", "indication_score", "region_score"}
                if not required.issubset(scores.keys()):
                    logger.warning("LLM score missing required keys, got: %s", list(scores.keys()))
                    return {"drug_score": _DEFAULT_SCORE, "indication_score": _DEFAULT_SCORE, "region_score": _DEFAULT_SCORE}
                return scores
            except json.JSONDecodeError:
                logger.warning("LLM returned non-JSON: %s", result)
            except Exception:
                logger.exception("LLM scoring failed")
        return {"drug_score": _DEFAULT_SCORE, "indication_score": _DEFAULT_SCORE, "region_score": _DEFAULT_SCORE}

    def _detect_stalled(self, item: dict) -> bool:
        """根据截止日期判断商机是否已停滞（超期30天以上）。"""
        deadline = item.get("deadline", "")
        if deadline:
            try:
                dt = datetime.fromisoformat(deadline)
                return (datetime.now() - dt).days >= 30
            except Exception:
                pass
        return False

    def _generate_strategy(self, scores: dict, stalled: bool) -> str:
        """根据评分和停滞状态生成提价/转介绍/加大拜访频率策略。"""
        avg_score = sum(scores.values()) / len(scores) if scores else 0
        if stalled:
            return "visit_increase"
        if avg_score >= _PRICE_ADJUST_THRESHOLD:
            return "price_adjustment"
        if avg_score >= _REFERRAL_THRESHOLD:
            return "referral"
        return "visit_increase"
