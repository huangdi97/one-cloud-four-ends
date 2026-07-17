"""CompetitorCrawlerAgent 单元测试 — 使用 fake/mock 不依赖真实 LLM。"""

from __future__ import annotations

import pytest

from cloud.app.agent_runtime.core.models import AgentIdentity, AgentTier, ModelPreference
from cloud.app.agents.base_agent import AgentContext
from cloud.app.agents.competitor_crawler_agent import CompetitorCrawlerAgent

SAMPLE_IDENTITY = AgentIdentity(
    key="crawler_test",
    name="爬虫测试",
    role="竞品情报",
    goal="测试",
    allowed_tools=["crawler", "news_monitoring"],
    model_preference=ModelPreference(provider="deepseek", level=AgentTier.cloud_normal),
)


class TestCompetitorCrawlerAgent:
    @pytest.mark.asyncio
    async def test_execute_no_tools_returns_empty_prompt_async(self) -> None:
        agent = CompetitorCrawlerAgent()
        context = AgentContext(message="查询竞品")
        response = await agent.execute(context)
        assert "当前无竞品情报数据" in response.reply

    @pytest.mark.asyncio
    async def test_classify_update_new_approval(self) -> None:
        agent = CompetitorCrawlerAgent()
        result = await agent._classify_update("新药获批上市")
        assert result == "new_approval"

    @pytest.mark.asyncio
    async def test_classify_update_trial_result(self) -> None:
        agent = CompetitorCrawlerAgent()
        result = await agent._classify_update("临床III期结果")
        assert result == "trial_result"

    def test_score_urgency_mapping(self) -> None:
        agent = CompetitorCrawlerAgent()
        assert agent._score_urgency("new_approval", {}) == 5
        assert agent._score_urgency("pipeline_change", {}) == 2

    def test_capabilities_from_identity(self) -> None:
        agent = CompetitorCrawlerAgent(identity=SAMPLE_IDENTITY)
        assert agent.capabilities() == ["crawler", "news_monitoring"]

    def test_capabilities_fallback(self) -> None:
        agent = CompetitorCrawlerAgent()
        assert agent.capabilities() == ["competitor_intel", "crawler", "news_monitoring"]

    @pytest.mark.asyncio
    async def test_execute_empty_raw_data(self) -> None:
        agent = CompetitorCrawlerAgent()
        context = AgentContext(message="爬取竞品")
        response = await agent.execute(context)
        assert "当前无竞品情报数据" in response.reply
