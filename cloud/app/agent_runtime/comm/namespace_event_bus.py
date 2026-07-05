"""Namespace 变更事件总线 — SharedState write 完成后触发，匹配 event_subscriptions 并调度 Agent。"""

import logging
import re
import threading
from datetime import datetime

from cloud.app.agent_runtime.core.agent_registry import AgentRegistry
from cloud.app.agent_runtime.core.shared_state import SharedState, SharedStateEntry

logger = logging.getLogger(__name__)


class NamespaceEventBus:
    """监听 SharedState namespace 变更，检查各 Agent event_subscriptions，匹配则触发。"""

    def __init__(self, db=None):
        self._db = db
        self._subscribers: dict[str, list[callable]] = {}
        self._lock = threading.Lock()
        self._running = False
        self._thread = None

    def start(self, shared_state: SharedState) -> None:
        """Start listening to SharedState writes."""
        self._running = True
        shared_state.subscribe(self._on_namespace_change)
        logger.info("NamespaceEventBus started")

    def stop(self) -> None:
        """停止监听事件总线。"""
        self._running = False

    def _on_namespace_change(self, entry: SharedStateEntry) -> None:
        """Called when SharedState.write() completes."""
        namespace = entry.namespace
        for agent in AgentRegistry.list():
            subscriptions = agent.identity.event_subscriptions or []
            for pattern in subscriptions:
                if re.match(pattern, namespace):
                    logger.info(
                        "Event match: namespace=%s pattern=%s triggering agent=%s",
                        namespace,
                        pattern,
                        agent.identity.key,
                    )
                    self._trigger_agent(agent.identity.key, entry)

        # 交叉验证链检查
        try:
            from cloud.app.agent_runtime.core.cross_validation_chain import CrossValidationChain

            chain = CrossValidationChain(db=self._db)
            chain.execute_chain(entry)
        except Exception:
            logger.exception("CrossValidationChain.execute_chain failed")

    def _trigger_agent(self, agent_key: str, entry: SharedStateEntry) -> None:
        """Queue an agent execution triggered by a namespace event."""
        from cloud.app.agent_runtime.core.queue_manager import AgentQueueManager

        goal = f"事件触发: namespace={entry.namespace} key={entry.key}"
        qm = AgentQueueManager(self._db)
        scheduled_at = datetime.now().isoformat()
        qm.enqueue(agent_key, goal, scheduled_at)
        logger.info("Enqueued %s triggered by %s.%s", agent_key, entry.namespace, entry.key)


_namespace_event_bus: NamespaceEventBus | None = None
_bus_lock = threading.Lock()


def get_namespace_event_bus(db=None) -> NamespaceEventBus:
    """获取全局 NamespaceEventBus 单例。"""
    global _namespace_event_bus
    if _namespace_event_bus is None:
        with _bus_lock:
            if _namespace_event_bus is None:
                _namespace_event_bus = NamespaceEventBus(db=db)
    return _namespace_event_bus
