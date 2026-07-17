"""CompetitorCrawlerAgent — 竞品情报爬取与分类Agent。"""

from __future__ import annotations

import json
import logging
from typing import Any

from cloud.app.agent_runtime.core.models import AgentIdentity
from cloud.app.agents.base_agent import AgentContext, AgentResponse, BaseAgent

logger = logging.getLogger(__name__)

_UPDATE_TYPES = ["new_approval", "pipeline_change", "pricing_update", "trial_result"]

__all__ = ["CompetitorCrawlerAgent"]


class CompetitorCrawlerAgent(BaseAgent):
    """竞品情报爬取与分类Agent，支持手动查询和定时爬取模式。"""

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
        mode = "manual" if "查询" in msg else "crawl"
        raw_data = []
        if self._tools is not None:
            try:
                if mode == "crawl":
                    raw_data = await self._tools.call("crawler_start", {"query": msg}, "", "")
                else:
                    raw_data = await self._tools.call("crawler_query", {"query": msg}, "", "")
            except Exception:
                logger.exception("Crawler tool failed")
                raw_data = []
        if not raw_data:
            logger.info("No raw data from crawler tool, reporting empty result")
            return AgentResponse(
                reply="当前无竞品情报数据。请稍后再试或手动触发爬取。",
                actions=[{"agent": "competitor_crawler", "mode": mode, "count": 0}],
            )

        classified = []
        for item in raw_data:
            utype = await self._classify_update(item.get("description", ""))
            urgency = self._score_urgency(utype, item)
            classified.append({**item, "update_type": utype, "urgency": urgency})

        classified.sort(key=lambda x: x.get("urgency", 0), reverse=True)
        output_lines = ["竞品情报汇总："]
        for c in classified:
            output_lines.append(
                f"药品:{c.get('drug_name', '')} 公司:{c.get('company', '')} "
                f"类型:{c.get('update_type', '')} 紧迫度:{c.get('urgency', '')} "
                f"来源:{c.get('source_url', '')}"
            )
        reply = "\n".join(output_lines)

        if self._memory is not None:
            try:
                ns = self._memory.get_namespace(self._identity.key if self._identity else "competitor_crawler")
                for c in classified:
                    ns.store(f"intel:{c.get('drug_name', '')}", json.dumps(c, ensure_ascii=False))
            except Exception:
                logger.exception("Failed to write memory")

        return AgentResponse(reply=reply, actions=[{"agent": "competitor_crawler", "mode": mode, "count": len(classified)}])

    def _default_capabilities(self) -> list[str]:
        return ["competitor_intel", "crawler", "news_monitoring"]

    async def _classify_update(self, description: str) -> str:
        """用LLM或关键词规则将竞品动态文本分类为更新类型。"""
        if self._llm is not None:
            try:
                prompt = f"分类以下竞品动态为{_UPDATE_TYPES}之一：{description}\n给出分类名称。"
                result = await self._llm.generate(prompt)
                for ut in _UPDATE_TYPES:
                    if ut in result:
                        return ut
            except Exception:
                logger.warning("LLM classify failed for: %s", description[:80])
        if any(kw in description for kw in ["批准", "上市", "获批"]):
            return "new_approval"
        if any(kw in description for kw in ["临床", "试验", "期"]):
            return "trial_result"
        if any(kw in description for kw in ["定价", "医保", "价格"]):
            return "pricing_update"
        return "pipeline_change"

    def _score_urgency(self, utype: str, item: dict) -> int:
        """根据更新类型映射紧迫度分值（5最高1最低）。"""
        urgency_map = {"new_approval": 5, "pricing_update": 4, "trial_result": 3, "pipeline_change": 2}
        return urgency_map.get(utype, 1)
