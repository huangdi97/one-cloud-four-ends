"""Agent 间通信的标准消息格式与消息总线。"""

import logging
from datetime import datetime
from typing import Callable

from cloud.app.agent_runtime.safety.defense_pipeline import is_quarantined

logger = logging.getLogger(__name__)


class AgentMessage:
    """Agent 间通信的标准消息格式。"""

    VERSION = "1.0"

    def __init__(
        self,
        source: str,
        target: str,
        msg_type: str,
        payload: dict,
        trace_id: str = "",
        priority: str = "normal",
    ):
        self.source = source
        self.target = target
        self.msg_type = msg_type
        self.payload = payload
        self.trace_id = trace_id
        self.priority = priority
        self.timestamp = datetime.now()

    def to_dict(self) -> dict:
        """to dict."""
        return {
            "version": self.VERSION,
            "source": self.source,
            "target": self.target,
            "msg_type": self.msg_type,
            "payload": self.payload,
            "trace_id": self.trace_id,
            "priority": self.priority,
            "timestamp": self.timestamp.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "AgentMessage":
        """从字典反序列化为 AgentMessage。"""
        msg = cls(
            source=data.get("source", ""),
            target=data.get("target", ""),
            msg_type=data.get("msg_type", ""),
            payload=data.get("payload", {}),
            trace_id=data.get("trace_id", ""),
            priority=data.get("priority", "normal"),
        )
        if data.get("timestamp"):
            try:
                msg.timestamp = datetime.fromisoformat(data["timestamp"])
            except (ValueError, TypeError):
                logger.warning("Agent protocol exception", exc_info=True)
        return msg


class AgentMessageBus:
    """基于 EventBus 的消息总线，含 L0 隔离检查。"""

    def __init__(self):
        self._handlers: dict[str, list[Callable]] = {}

    def send(self, message: AgentMessage):
        """发送消息到目标 Agent，含 L0 隔离检查。"""
        if is_quarantined(message.source):
            logger.warning("Blocked send from quarantined agent: %s", message.source)
            return
        if is_quarantined(message.target):
            logger.warning("Blocked send to quarantined agent: %s", message.target)
            return
        logger.info(
            "AgentMessageBus send: %s -> %s type=%s trace=%s",
            message.source,
            message.target,
            message.msg_type,
            message.trace_id,
        )
        targets = [message.target] if message.target != "*" else list(self._handlers.keys())
        for target in targets:
            key = f"{target}:{message.msg_type}"
            handlers = self._handlers.get(key, []) + self._handlers.get(f"{target}:*", [])
            for handler in handlers:
                try:
                    handler(message)
                except Exception:  # handler 可能抛出任意异常
                    logger.exception("Handler for %s failed", key)
            if not handlers:
                logger.debug("No handler for %s", key)

    def subscribe(self, agent_name: str, msg_type: str, handler: Callable):
        """subscribe."""
        key = f"{agent_name}:{msg_type}"
        if key not in self._handlers:
            self._handlers[key] = []
        self._handlers[key].append(handler)
        logger.info("AgentMessageBus subscribe: %s", key)

    def unsubscribe(self, agent_name: str, msg_type: str, handler: Callable):
        """unsubscribe."""
        key = f"{agent_name}:{msg_type}"
        if key in self._handlers and handler in self._handlers[key]:
            self._handlers[key].remove(handler)
