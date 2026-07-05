"""FallbackMiddleware — 主模型失败自动切备选模型。"""

from __future__ import annotations

import logging
from typing import Any

from cloud.app.agent_runtime.middleware.base import Middleware

logger = logging.getLogger(__name__)

_FALLBACK_MODELS = [
    "gpt-4o-mini",
    "gpt-3.5-turbo",
    "claude-3-haiku",
]


class FallbackMiddleware(Middleware):
    name = "fallback"

    def __init__(self):
        """Initialize the fallback middleware with an empty fallback index."""
        self._fallback_index: dict[str, int] = {}

    def before_execute(self, goal: str, agent_key: str, context: dict | None) -> dict | None:
        """Pass context through unchanged before execution."""
        return context

    def after_execute(self, goal: str, agent_key: str, result: dict[str, Any]) -> dict[str, Any] | None:
        """Fall back to the next model if the current model failed."""
        if result.get("status") not in ("llm_failed", "error"):
            self._fallback_index.pop(agent_key, None)
            return None
        current_idx = self._fallback_index.get(agent_key, -1)
        next_idx = current_idx + 1
        if next_idx < len(_FALLBACK_MODELS):
            self._fallback_index[agent_key] = next_idx
            result["fallback_model"] = _FALLBACK_MODELS[next_idx]
            result["retry_with_fallback"] = True
            logger.info("FallbackMiddleware: %s falling back to %s", agent_key, _FALLBACK_MODELS[next_idx])
        return result
