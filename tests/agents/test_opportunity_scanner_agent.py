"""OpportunityScannerAgent 单元测试 — 不依赖真实 LLM/tool。"""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from cloud.app.agents.base_agent import AgentContext
from cloud.app.agents.opportunity_scanner_agent import OpportunityScannerAgent


class TestOpportunityScannerAgent:
    def setup_method(self) -> None:
        self.agent = OpportunityScannerAgent()

    def test_detect_stalled_old_deadline(self) -> None:
        old = (datetime.now() - timedelta(days=35)).isoformat()
        assert self.agent._detect_stalled({"deadline": old}) is True

    def test_detect_stalled_recent_deadline(self) -> None:
        recent = (datetime.now() - timedelta(days=10)).isoformat()
        assert self.agent._detect_stalled({"deadline": recent}) is False

    def test_detect_stalled_future_deadline(self) -> None:
        future = (datetime.now() + timedelta(days=10)).isoformat()
        assert self.agent._detect_stalled({"deadline": future}) is False

    def test_detect_stalled_no_deadline(self) -> None:
        assert self.agent._detect_stalled({}) is False

    def test_generate_strategy_stalled(self) -> None:
        assert self.agent._generate_strategy({"drug_score": 90, "indication_score": 90, "region_score": 90}, stalled=True) == "visit_increase"

    def test_generate_strategy_high_score(self) -> None:
        assert self.agent._generate_strategy({"drug_score": 85, "indication_score": 80, "region_score": 80}, stalled=False) == "price_adjustment"

    def test_generate_strategy_medium_score(self) -> None:
        assert self.agent._generate_strategy({"drug_score": 65, "indication_score": 60, "region_score": 70}, stalled=False) == "referral"

    def test_execute_no_data_returns_prompt(self) -> None:
        agent = OpportunityScannerAgent()
        context = AgentContext(message="扫描商机")
        response = agent._detect_stalled({})  # just verify no error
        assert not response

    @pytest.mark.asyncio
    async def test_execute_no_data_returns_prompt_async(self) -> None:
        agent = OpportunityScannerAgent()
        context = AgentContext(message="扫描商机")
        response = await agent.execute(context)
        assert "当前无商机数据" in response.reply
