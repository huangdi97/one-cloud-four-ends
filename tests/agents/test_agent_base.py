"""BaseAgent / SpecializedAgent 单元测试 — 使用 AgentIdentity。"""

from __future__ import annotations

from dataclasses import dataclass, field

import pytest

from cloud.app.agent_runtime.core.models import AgentIdentity, AgentTier, ModelPreference
from cloud.app.agents.base_agent import AgentContext, AgentResponse, BaseAgent
from cloud.app.agents.specialized_agent import SpecializedAgent


@dataclass
class FakeLLM:
    """模拟 LLM 服务，返回固定回复。"""

    reply: str = "模拟回复内容"

    async def generate(self, prompt: str) -> str:
        return self.reply


@dataclass
class FakeMemory:
    """模拟记忆服务。"""

    stored: dict = field(default_factory=dict)


@dataclass
class FakeToolBridge:
    """模拟工具桥接。"""

    pass


SAMPLE_IDENTITY = AgentIdentity(
    key="test_agent",
    name="测试代理",
    role="测试角色",
    goal="验证执行流程",
    allowed_tools=["tool_a", "tool_b", "tool_c"],
    model_preference=ModelPreference(provider="deepseek", level=AgentTier.cloud_normal),
)


class TestBaseAgent:
    def test_base_agent_cannot_instantiate(self) -> None:
        with pytest.raises(TypeError):
            BaseAgent()  # type: ignore[abstract]

    def test_concrete_subclass_must_implement_abstract_methods(self) -> None:
        class IncompleteAgent(BaseAgent):
            pass

        with pytest.raises(TypeError):
            IncompleteAgent()  # type: ignore[abstract]


class TestSpecializedAgentFromIdentity:
    def test_from_identity_without_services(self) -> None:
        agent = SpecializedAgent.from_identity(SAMPLE_IDENTITY)
        assert agent._identity is SAMPLE_IDENTITY
        assert agent._llm is None
        assert agent._memory is None
        assert agent._tools is None

    def test_from_identity_with_services(self) -> None:
        services = {
            "llm_service": FakeLLM(),
            "memory_service": FakeMemory(),
            "tool_bridge": FakeToolBridge(),
        }
        agent = SpecializedAgent.from_identity(SAMPLE_IDENTITY, services=services)
        assert agent._llm is not None
        assert agent._memory is not None
        assert agent._tools is not None

    def test_constructor_direct(self) -> None:
        llm = FakeLLM()
        agent = SpecializedAgent(
            identity=SAMPLE_IDENTITY,
            llm_service=llm,
        )
        assert agent._llm is llm


class TestSpecializedAgentCapabilities:
    def test_capabilities_returns_identity_tools(self) -> None:
        agent = SpecializedAgent.from_identity(SAMPLE_IDENTITY)
        caps = agent.capabilities()
        assert caps == ["tool_a", "tool_b", "tool_c"]

    def test_capabilities_returns_copy(self) -> None:
        agent = SpecializedAgent.from_identity(SAMPLE_IDENTITY)
        caps = agent.capabilities()
        caps.append("extra")
        assert agent.capabilities() == ["tool_a", "tool_b", "tool_c"]

    def test_capabilities_empty(self) -> None:
        identity = AgentIdentity(key="empty", name="空", role="无", goal="无能力")
        agent = SpecializedAgent.from_identity(identity)
        assert agent.capabilities() == []


class TestSpecializedAgentExecute:
    @pytest.mark.asyncio
    async def test_execute_with_llm_returns_reply(self) -> None:
        llm = FakeLLM(reply="这是 AI 回复")
        agent = SpecializedAgent(identity=SAMPLE_IDENTITY, llm_service=llm)
        context = AgentContext(message="你好")
        response = await agent.execute(context)
        assert isinstance(response, AgentResponse)
        assert response.reply == "这是 AI 回复"
        assert response.actions == []
        assert response.memory_updates == []

    @pytest.mark.asyncio
    async def test_execute_without_llm_echoes_message(self) -> None:
        agent = SpecializedAgent.from_identity(SAMPLE_IDENTITY)
        context = AgentContext(message="测试消息", session_id="s1", user_id="u1")
        response = await agent.execute(context)
        assert SAMPLE_IDENTITY.name in response.reply
        assert "测试消息" in response.reply

    @pytest.mark.asyncio
    async def test_execute_with_session_and_user_context(self) -> None:
        llm = FakeLLM()
        agent = SpecializedAgent(identity=SAMPLE_IDENTITY, llm_service=llm)
        context = AgentContext(
            message="帮我查一下",
            session_id="session_001",
            user_id="user_42",
        )
        response = await agent.execute(context)
        assert response.reply == "模拟回复内容"

    @pytest.mark.asyncio
    async def test_execute_handles_llm_exception(self) -> None:
        class BrokenLLM:
            async def generate(self, prompt: str) -> str:
                raise RuntimeError("LLM 故障")

        agent = SpecializedAgent(
            identity=SAMPLE_IDENTITY,
            llm_service=BrokenLLM(),
        )
        context = AgentContext(message="触发错误")
        response = await agent.execute(context)
        assert "出错" in response.reply or "错误" in response.reply

    @pytest.mark.asyncio
    async def test_execute_with_memory_service(self) -> None:
        memory = FakeMemory()
        agent = SpecializedAgent(
            identity=SAMPLE_IDENTITY,
            llm_service=FakeLLM(),
            memory_service=memory,
        )
        context = AgentContext(message="带记忆的执行", memory=memory)
        response = await agent.execute(context)
        assert isinstance(response, AgentResponse)

    @pytest.mark.asyncio
    async def test_execute_with_tool_bridge(self) -> None:
        tools = FakeToolBridge()
        agent = SpecializedAgent(
            identity=SAMPLE_IDENTITY,
            llm_service=FakeLLM(),
            tool_bridge=tools,
        )
        context = AgentContext(message="使用工具", tool_bridge=tools)
        response = await agent.execute(context)
        assert isinstance(response, AgentResponse)


class _StubExecuteMixin:
    """Mixin to provide a concrete execute implementation for BaseAgent subclasses in tests."""

    async def execute(self, context: AgentContext) -> AgentResponse:  # type: ignore[misc]
        return AgentResponse(reply="stub")


class TestBaseAgentDefaultCapabilities:
    """BaseAgent._default_capabilities 测试"""

    def test_default_capabilities_returns_empty_list(self) -> None:
        class NoOverrideAgent(_StubExecuteMixin, BaseAgent):
            pass

        agent = NoOverrideAgent()
        assert agent.capabilities() == []

    def test_default_capabilities_subclass_override(self) -> None:
        class OverrideAgent(_StubExecuteMixin, BaseAgent):
            def _default_capabilities(self) -> list[str]:
                return ["a", "b"]

        agent = OverrideAgent()
        assert agent.capabilities() == ["a", "b"]

    def test_capabilities_reads_identity_allowed_tools(self) -> None:
        class IdentityAgent(_StubExecuteMixin, BaseAgent):
            pass

        agent = IdentityAgent()
        agent._identity = SAMPLE_IDENTITY
        assert agent.capabilities() == ["tool_a", "tool_b", "tool_c"]

    def test_capabilities_fallback_when_identity_none(self) -> None:
        class FallbackAgent(_StubExecuteMixin, BaseAgent):
            def _default_capabilities(self) -> list[str]:
                return ["fallback"]

        agent = FallbackAgent()
        agent._identity = None
        assert agent.capabilities() == ["fallback"]
