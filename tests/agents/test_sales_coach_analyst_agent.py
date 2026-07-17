"""SalesCoachAnalystAgent 单元测试 — 不依赖真实 LLM/tool。"""

from __future__ import annotations

import pytest

from cloud.app.agents.base_agent import AgentContext
from cloud.app.agents.sales_coach_analyst_agent import SalesCoachAnalystAgent


class TestSalesCoachAnalystAgent:
    def setup_method(self) -> None:
        self.agent = SalesCoachAnalystAgent()

    def test_parse_rep_id_standard_format(self) -> None:
        assert self.agent._parse_rep_id("分析REP-001的训练数据") == "REP-001"

    def test_parse_rep_id_underscore_format(self) -> None:
        assert self.agent._parse_rep_id("查看rep_zhangwei的成绩") == "rep_zhangwei"

    def test_parse_rep_id_no_match(self) -> None:
        assert self.agent._parse_rep_id("帮我看看训练数据") is None

    def test_execute_no_rep_id_returns_prompt(self) -> None:
        context = AgentContext(message="帮我看看训练数据")

    @pytest.mark.asyncio
    async def test_execute_no_rep_id_returns_prompt_async(self) -> None:
        agent = SalesCoachAnalystAgent()
        context = AgentContext(message="帮我看看训练数据")
        response = await agent.execute(context)
        assert "无法从消息中解析代表ID" in response.reply

    @pytest.mark.asyncio
    async def test_execute_no_training_data_returns_prompt(self) -> None:
        agent = SalesCoachAnalystAgent()
        context = AgentContext(message="分析REP-001")
        response = await agent.execute(context)
        assert "暂无训练数据" in response.reply

    def test_generate_suggestions_low_product_knowledge(self) -> None:
        analysis = {"product_knowledge": 60, "visit_skill": 90, "compliance_awareness": 90, "objection_handling": 90}
        suggestions = self.agent._generate_suggestions(analysis)
        assert any("产品知识" in s for s in suggestions)

    def test_generate_suggestions_all_high(self) -> None:
        analysis = {"product_knowledge": 85, "visit_skill": 80, "compliance_awareness": 90, "objection_handling": 85}
        suggestions = self.agent._generate_suggestions(analysis)
        assert any("维持当前水平" in s for s in suggestions)
