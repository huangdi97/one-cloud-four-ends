"""SummarizationMiddleware — 接近 token 上限时自动摘要历史。"""

from __future__ import annotations

import logging
from typing import Any

from cloud.app.agent_runtime.core.context_engine import estimate_tokens
from cloud.app.agent_runtime.middleware.base import Middleware

logger = logging.getLogger(__name__)

TOKEN_LIMIT = 4096
SUMMARIZE_AT = int(TOKEN_LIMIT * 0.85)


class SummarizationMiddleware(Middleware):
    name = "summarization"

    def before_execute(self, goal: str, agent_key: str, context: dict | None) -> dict | None:
        """Pass context through unchanged before execution."""
        return context

    def after_execute(self, goal: str, agent_key: str, result: dict[str, Any]) -> dict[str, Any] | None:
        """Summarize conversation history if token limit is approaching."""
        messages = result.get("messages", [])
        if not messages:
            return None
        total = sum(estimate_tokens(m.get("content", "")) for m in messages)
        if total <= SUMMARIZE_AT:
            return None
        system_msgs = [m for m in messages if m.get("role") == "system"]
        non_system = [m for m in messages if m.get("role") != "system"]
        if non_system:
            summary_text = " ".join(m.get("content", "")[:80] for m in non_system[:-6] if m.get("content"))
            summary = {"role": "system", "content": f"[自动摘要] {summary_text[:300]}..."}
            compressed = system_msgs + [summary] + non_system[-6:]
            result["messages"] = compressed
            logger.info("SummarizationMiddleware: compressed %d messages for %s", len(messages), agent_key)
        return {"messages": result["messages"]}
