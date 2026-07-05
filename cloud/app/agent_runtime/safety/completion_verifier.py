"""Verifies completion conditions with retry logic for unmet conditions."""

import json
import logging

from cloud.app.agent_runtime.core.models import RuntimeResult

logger = logging.getLogger(__name__)


class CompletionVerifier:
    """Verifies completion conditions and handles retry logic when conditions are unmet."""

    def __init__(self, host):
        self._host = host

    def verify_and_handle(self, c, step, decision, ai_resp, duration_ms) -> RuntimeResult | None:
        """Verify completion conditions and either complete or retry the step."""
        plan = c.get("_plan")
        conditions = plan.completion_conditions if plan else []
        if not conditions:
            return self._host._tool_exec._handle_completion(c, step, decision, ai_resp, duration_ms)

        last_tool_result = ""
        for msg in reversed(c["messages"]):
            if isinstance(msg.get("content"), str) and msg["content"].startswith("工具返回："):
                last_tool_result = msg["content"]
                break

        context = {"messages": c["messages"], "last_tool_result": last_tool_result}
        passed, reason = self._host._verifier.verify_completion(conditions, context)

        if passed:
            c["logs"].append({"step": step, "type": "completion_verified", "detail": reason})
            return self._host._tool_exec._handle_completion(c, step, decision, ai_resp, duration_ms)

        retries = c.get("_completion_retries", 0)
        max_retries = 2
        if retries < max_retries:
            c["_completion_retries"] = retries + 1
            feedback = f"完成条件未完全满足：{reason}\n请修正后重试。当前条件：{json.dumps(conditions, ensure_ascii=False)}"
            c["messages"].append({"role": "user", "content": feedback})
            logger.warning("Completion verification failed (attempt %d/%d): %s", retries + 1, max_retries, reason)
            return None

        logger.warning("Completion verification failed after %d retries: %s", max_retries, reason)
        c["logs"].append({"step": step, "type": "completion_retry_exhausted", "detail": reason})
        return self._host._finish(c, "incomplete", reason, step, step + 1, False)
