"""HITLMiddleware — 关键工具调用前检查是否需要人工审批。

ApprovalThreshold 配置:
- critical → 强制审批
- confidence < 0.6 → 建议审批
- confidence >= 0.9 → 自动通过
"""

from __future__ import annotations

import enum
import logging
from datetime import datetime, timedelta
from typing import Any

from cloud.app.agent_runtime.core.shared_state import SharedStateEntry, get_shared_state
from cloud.app.agent_runtime.middleware.base import Middleware

logger = logging.getLogger(__name__)

_SENSITIVE_TOOLS = frozenset(
    {
        "agent_brain_delete",
        "agent_brain_set",
    }
)

APPROVAL_NAMESPACE = "hitl.approval"
DEFAULT_TIMEOUT_MINUTES = 15
ESCALATION_TIMEOUT_MINUTES = 30


class ApprovalThreshold(enum.Enum):
    MANDATORY = "mandatory"
    SUGGESTED = "suggested"
    AUTO_PASS = "auto_pass"


class HITLMiddleware(Middleware):
    name = "hitl"

    def __init__(self, approval_queue: Any | None = None):
        """Initialize the HITL middleware with an optional approval queue."""
        self._approval_queue = approval_queue

    def before_execute(self, goal: str, agent_key: str, context: dict | None) -> dict | None:
        """Pass context through unchanged before execution."""
        return context

    def after_execute(self, goal: str, agent_key: str, result: dict[str, Any]) -> dict[str, Any] | None:
        """Check if the result requires human approval and annotate accordingly."""
        tool_name = result.get("tool", "")
        confidence = result.get("confidence", 1.0)
        threshold = self._classify(agent_key, tool_name, confidence)

        if threshold == ApprovalThreshold.AUTO_PASS:
            return result

        if tool_name in _SENSITIVE_TOOLS or result.get("needs_approval") or threshold == ApprovalThreshold.MANDATORY:
            approval_id = create_approval_request(
                agent_key=agent_key,
                tool_name=tool_name,
                goal=goal,
                context=result,
                threshold=threshold.value,
            )
            result["requires_hitl"] = True
            result["approval_id"] = approval_id
            result["approval_threshold"] = threshold.value
            logger.info(
                "HITLMiddleware: %s requires approval id=%s threshold=%s",
                agent_key,
                approval_id,
                threshold.value,
            )
        elif threshold == ApprovalThreshold.SUGGESTED:
            result["suggested_approval"] = True
            logger.info("HITLMiddleware: %s suggested approval (tool=%s)", agent_key, tool_name)

        return result

    def _classify(self, agent_key: str, tool_name: str, confidence: float) -> ApprovalThreshold:
        if tool_name in _SENSITIVE_TOOLS:
            return ApprovalThreshold.MANDATORY
        if confidence >= 0.9:
            return ApprovalThreshold.AUTO_PASS
        if confidence < 0.6:
            return ApprovalThreshold.SUGGESTED
        return ApprovalThreshold.SUGGESTED


def create_approval_request(
    agent_key: str,
    tool_name: str,
    goal: str,
    context: dict | None = None,
    threshold: str = "suggested",
    timeout_minutes: int = DEFAULT_TIMEOUT_MINUTES,
) -> str:
    """Create a new approval request in shared state and return its ID."""
    from uuid import uuid4

    ss = get_shared_state()
    approval_id = uuid4().hex[:12]
    now = datetime.utcnow()
    approval_value = {
        "approval_id": approval_id,
        "agent_key": agent_key,
        "tool_name": tool_name,
        "goal": goal,
        "context": context or {},
        "threshold": threshold,
        "status": "pending",
        "created_at": now.isoformat(),
        "timeout_at": (now + timedelta(minutes=timeout_minutes)).isoformat(),
        "escalated": False,
        "resolved_by": None,
        "resolved_at": None,
        "resolution": None,
    }
    ss.write(
        SharedStateEntry(
            namespace=APPROVAL_NAMESPACE,
            key=approval_id,
            value=approval_value,
            confidence=1.0,
            agent_key=agent_key,
            evidence=[f"HITL: create_approval_request agent={agent_key} tool={tool_name}"],
        ),
    )
    logger.info("Approval request created: %s for %s tool=%s", approval_id, agent_key, tool_name)
    return approval_id


def resolve_approval(approval_id: str, approver: str, resolution: str) -> bool:
    """Resolve a pending approval with the given resolution. Returns True on success."""
    ss = get_shared_state()
    entries = ss.read(APPROVAL_NAMESPACE, key=approval_id)
    if not entries:
        logger.warning("resolve_approval: approval %s not found", approval_id)
        return False

    entry = entries[-1]
    current = entry.value
    if current.get("status") != "pending":
        logger.warning("resolve_approval: approval %s already %s", approval_id, current.get("status"))
        return False

    if resolution not in ("approved", "rejected"):
        logger.warning("resolve_approval: invalid resolution %s for %s", resolution, approval_id)
        return False

    now = datetime.utcnow()
    current["status"] = resolution
    current["resolved_by"] = approver
    current["resolved_at"] = now.isoformat()
    current["resolution"] = resolution

    ss.write(
        SharedStateEntry(
            namespace=APPROVAL_NAMESPACE,
            key=approval_id,
            value=current,
            confidence=1.0,
            agent_key="hitl_resolver",
            evidence=[f"HITL: resolve_approval id={approval_id} by={approver} resolution={resolution}"],
        ),
    )
    logger.info("Approval %s resolved: %s by %s", approval_id, resolution, approver)
    return True


def escalate_approval(approval_id: str) -> bool:
    """Escalate an approval that has timed out. Returns True if escalated."""
    ss = get_shared_state()
    entries = ss.read(APPROVAL_NAMESPACE, key=approval_id)
    if not entries:
        return False

    entry = entries[-1]
    current = entry.value
    if current.get("status") != "pending":
        return False

    now = datetime.utcnow()
    timeout_at = datetime.fromisoformat(current["timeout_at"])

    if now > timeout_at and not current.get("escalated"):
        current["escalated"] = True
        current["status"] = "escalated"
        current["timeout_at"] = (now + timedelta(minutes=ESCALATION_TIMEOUT_MINUTES)).isoformat()
        ss.write(
            SharedStateEntry(
                namespace=APPROVAL_NAMESPACE,
                key=approval_id,
                value=current,
                confidence=1.0,
                agent_key="hitl_escalator",
                evidence=[f"HITL: escalate_approval id={approval_id} timeout exceeded"],
            ),
        )
        logger.info("Approval %s escalated due to timeout", approval_id)
        return True
    return False


def check_approval_timeouts() -> list[str]:
    """Check all pending approvals and escalate any that have timed out."""
    ss = get_shared_state()
    entries = ss.read(APPROVAL_NAMESPACE)
    escalated = []
    now = datetime.utcnow()
    for e in entries:
        val = e.value
        if val.get("status") != "pending":
            continue
        timeout_at = datetime.fromisoformat(val["timeout_at"])
        if now > timeout_at:
            if escalate_approval(val["approval_id"]):
                escalated.append(val["approval_id"])
    return escalated


def get_pending_approvals() -> list[dict]:
    """Return all pending approvals from shared state."""
    ss = get_shared_state()
    entries = ss.read(APPROVAL_NAMESPACE)
    return [e.value for e in entries if e.value.get("status") == "pending"]
