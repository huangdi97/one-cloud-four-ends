"""Agent 抽象基类 — 定义 execute / capabilities 接口及上下文/响应结构。"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

__all__ = ["AgentContext", "AgentResponse", "BaseAgent"]


@dataclass
class AgentContext:
    """Agent 执行上下文，包含输入消息、会话信息及运行时服务引用。"""

    message: str
    session_id: str = ""
    user_id: str = ""
    memory: object = None
    tool_bridge: object = None


@dataclass
class AgentResponse:
    """Agent 执行结果，包含回复文本、动作列表及记忆更新。"""

    reply: str = ""
    actions: list[dict] = field(default_factory=list)
    memory_updates: list[dict] = field(default_factory=list)


class BaseAgent(ABC):
    """Agent 抽象基类，所有 Agent 实现必须继承并实现 execute / capabilities。"""

    @abstractmethod
    async def execute(self, context: AgentContext) -> AgentResponse:
        """执行 Agent 逻辑，返回结构化响应。"""

    def capabilities(self) -> list[str]:
        """默认从 identity 读取 allowed_tools。子类可覆盖 fallback 列表。"""
        if hasattr(self, "_identity") and self._identity is not None:
            if hasattr(self._identity, "allowed_tools") and self._identity.allowed_tools:
                return list(self._identity.allowed_tools)
        return self._default_capabilities()

    def _default_capabilities(self) -> list[str]:
        """子类覆盖此方法提供降级能力列表。"""
        return []
