"""SharedState 结构化数据模型 — 设计文档 §3.3"""

import logging
import os
import re
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Generator, List

from cloud.app.services.platform_svc.tenant_isolation_service import CURRENT_TENANT
from shared.config import is_multi_tenant

logger = logging.getLogger(__name__)

_global_shared_state: "SharedState | None" = None
_global_ss_lock = threading.Lock()


def get_shared_state() -> "SharedState":
    """Return the singleton SharedState instance."""
    global _global_shared_state
    if _global_shared_state is None:
        with _global_ss_lock:
            if _global_shared_state is None:
                redis_url = os.getenv("REDIS_URL", "")
                backend = None
                if redis_url:
                    from cloud.app.agent_runtime.memory.redis_backend import RedisBackend

                    backend = RedisBackend(redis_url)
                _global_shared_state = SharedState(backend=backend)
    return _global_shared_state


@dataclass
class SharedStateEntry:
    namespace: str
    key: str
    value: Any
    confidence: float = 1.0
    agent_key: str = ""
    timestamp: str = ""
    version: int = 1
    evidence: List[str] = field(default_factory=list)


def _validate_namespace(caller_agent_key: str, namespace: str) -> None:
    from shared.agent_identity import get_identity

    identity = get_identity(caller_agent_key)
    allowed = identity.get("memory_namespace", caller_agent_key)
    if not namespace.startswith(allowed):
        raise PermissionError(f"Agent {caller_agent_key} (namespace={allowed}) 无权写入 namespace={namespace}")


class SharedState:
    def __init__(self, backend=None):
        self._lock = threading.Lock()
        self._entries: List[SharedStateEntry] = []
        self._watchers: dict[str, List[callable]] = {}
        self._subscribers: dict[str, List[callable]] = {}
        self._version_counter = 0
        self._backend = backend

    def _ensure_tenant_prefix(self, namespace: str) -> str:
        if is_multi_tenant():
            tenant_id = CURRENT_TENANT.get() or "default"
        else:
            tenant_id = "default"
        prefix = f"{tenant_id}."
        if namespace.startswith(prefix):
            return namespace
        return f"{prefix}{namespace}"

    @property
    def backend(self):
        """Return the optional persistence backend."""
        return self._backend

    def write(self, entry: SharedStateEntry, caller_agent_key: str | None = None) -> None:
        """Write an entry to shared state with optional caller validation."""
        entry.namespace = self._ensure_tenant_prefix(entry.namespace)
        if caller_agent_key:
            _validate_namespace(caller_agent_key, entry.namespace)
        if not entry.evidence:
            entry.confidence *= 0.5
            logger.warning(
                "Empty evidence on write: namespace=%s key=%s confidence reduced to %.2f",
                entry.namespace,
                entry.key,
                entry.confidence,
            )
        with self._lock:
            self._version_counter += 1
            entry.version = self._version_counter
            entry.timestamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            self._entries.append(entry)
            self._notify_watchers(entry)

    def read(
        self,
        namespace: str,
        key: str | None = None,
        min_confidence: float = 0.0,
    ) -> List[SharedStateEntry]:
        """Read entries matching namespace and optional key filter."""
        namespace = self._ensure_tenant_prefix(namespace)
        results = []
        with self._lock:
            for e in self._entries:
                if e.namespace != namespace:
                    continue
                if key is not None and not e.key.startswith(key):
                    continue
                if e.confidence < min_confidence:
                    continue
                results.append(e)
        return results

    def watch(self, namespace_pattern: str) -> Generator[SharedStateEntry, None, None]:
        """Yield entries matching a namespace regex pattern."""
        import queue

        q: queue.Queue[SharedStateEntry | None] = queue.Queue()

        def _callback(entry: SharedStateEntry) -> None:
            if re.match(namespace_pattern, entry.namespace):
                q.put(entry)

        with self._lock:
            self._watchers.setdefault(namespace_pattern, []).append(_callback)

        try:
            while True:
                entry = q.get()
                if entry is None:
                    break
                yield entry
        finally:
            with self._lock:
                if namespace_pattern in self._watchers:
                    self._watchers[namespace_pattern] = [cb for cb in self._watchers[namespace_pattern] if cb is not _callback]

    def subscribe(self, callback: callable) -> None:
        """Register a callback to be invoked on every namespace write.

        The callback receives the SharedStateEntry that was just written.
        """
        with self._lock:
            self._subscribers.setdefault("__all__", []).append(callback)

    def unsubscribe(self, callback: callable) -> None:
        """Remove a previously registered subscriber callback."""
        with self._lock:
            callbacks = self._subscribers.get("__all__", [])
            if callback in callbacks:
                callbacks.remove(callback)

    def _notify_watchers(self, entry: SharedStateEntry) -> None:
        for pattern, callbacks in list(self._watchers.items()):
            if re.match(pattern, entry.namespace):
                for cb in callbacks:
                    try:
                        cb(entry)
                    except Exception:
                        logger.exception("Watcher callback failed for pattern=%s", pattern)
        for cb in list(self._subscribers.get("__all__", [])):
            try:
                cb(entry)
            except Exception:
                logger.exception("Subscriber callback failed")

    def list_all_namespaces(self) -> dict[str, list]:
        """Return all namespaces and their values (excluding shared.*)."""
        with self._lock:
            result: dict[str, list] = {}
            for e in self._entries:
                if e.namespace.startswith("shared."):
                    continue
                result.setdefault(e.namespace, []).append(e.value)
            return result
