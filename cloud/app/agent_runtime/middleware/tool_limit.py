"""ToolLimitMiddleware — 限制单次 Agent 调用的工具调用次数。"""

from __future__ import annotations

import logging
from typing import Any

from cloud.app.agent_runtime.middleware.base import Middleware

logger = logging.getLogger(__name__)

DEFAULT_MAX_TOOL_CALLS = 20


class ToolLimitMiddleware(Middleware):
    name = "tool_limit"

    def __init__(self, max_tool_calls: int = DEFAULT_MAX_TOOL_CALLS):
        """Initialize the tool limit middleware with a max call threshold."""
        self._max_tool_calls = max_tool_calls
        self._counters: dict[str, int] = {}

    def before_execute(self, goal: str, agent_key: str, context: dict | None) -> dict | None:
        """Reset tool call counter for the agent before execution."""
        self._counters[agent_key] = 0
        return context

    def after_execute(self, goal: str, agent_key: str, result: dict[str, Any]) -> dict[str, Any] | None:
        """Track tool calls and flag when the limit is exceeded."""
        tool_name = result.get("tool", "")
        if tool_name:
            self._counters[agent_key] = self._counters.get(agent_key, 0) + 1
            current = self._counters[agent_key]
            if current > self._max_tool_calls:
                result["tool_limit_exceeded"] = True
                result["status"] = "tool_limit_exceeded"
                logger.warning("ToolLimitMiddleware: %s exceeded %d tool calls", agent_key, self._max_tool_calls)
        return result
