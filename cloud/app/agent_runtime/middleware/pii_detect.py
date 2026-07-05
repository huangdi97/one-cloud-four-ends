"""PIIDetectMiddleware — 输入/输出 PII 检测和脱敏。"""

from __future__ import annotations

import logging
from typing import Any

from cloud.app.agent_runtime.middleware.base import Middleware
from cloud.app.agent_runtime.safety.pii_redactor import redact

logger = logging.getLogger(__name__)


class PIIDetectMiddleware(Middleware):
    name = "pii_detect"

    def before_execute(self, goal: str, agent_key: str, context: dict | None) -> dict | None:
        """Redact PII from context before agent execution."""
        if context:
            redacted = {}
            for k, v in context.items():
                if isinstance(v, str):
                    redacted[k] = redact(v)
                else:
                    redacted[k] = v
            return redacted
        return context

    def after_execute(self, goal: str, agent_key: str, result: dict[str, Any]) -> dict[str, Any] | None:
        """Redact PII from agent output after execution."""
        content = result.get("result", "")
        if isinstance(content, str):
            redacted_result = redact(content)
            if redacted_result != content:
                result["pii_redacted"] = True
                result["result"] = redacted_result
                logger.info("PIIDetectMiddleware: redacted PII in output for %s", agent_key)
        return result
