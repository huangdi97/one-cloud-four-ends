"""死信队列 — 无法处理的请求持久化存储，支持重试。"""

import time
from collections import Counter
from typing import Any


class DeadLetterEntry:
    def __init__(
        self, agent_key: str, input_data: str, error: str, timestamp: float | None = None, retry_count: int = 0, error_category: str = "unknown"
    ):
        self.agent_key = agent_key
        self.input = input_data
        self.error = error
        self.timestamp = timestamp or time.time()
        self.retry_count = retry_count
        self.error_category = error_category

    def to_dict(self) -> dict[str, Any]:
        """Serialize the entry to a dictionary."""
        return {
            "agent_key": self.agent_key,
            "input": self.input,
            "error": self.error,
            "timestamp": self.timestamp,
            "retry_count": self.retry_count,
            "error_category": self.error_category,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "DeadLetterEntry":
        """Deserialize a dictionary into a DeadLetterEntry."""
        return cls(
            agent_key=d["agent_key"],
            input_data=d["input"],
            error=d["error"],
            timestamp=d.get("timestamp", time.time()),
            retry_count=d.get("retry_count", 0),
            error_category=d.get("error_category", "unknown"),
        )


class DeadLetterQueue:
    def __init__(self):
        self._entries: list[DeadLetterEntry] = []

    def push(self, entry: dict[str, Any] | DeadLetterEntry) -> None:
        """Push an entry onto the dead letter queue."""
        if isinstance(entry, dict):
            entry = DeadLetterEntry.from_dict(entry)
        self._entries.append(entry)

    def pop_all(self) -> list[dict[str, Any]]:
        """Pop and return all entries as dictionaries."""
        result = [e.to_dict() for e in self._entries]
        self._entries.clear()
        return result

    def retry(self, entry: dict[str, Any] | DeadLetterEntry, max_retries: int = 3) -> bool:
        """Increment retry count for an entry if under the max."""
        if isinstance(entry, dict):
            entry = DeadLetterEntry.from_dict(entry)
        if entry.retry_count >= max_retries:
            return False
        entry.retry_count += 1
        return True

    def replay_all(self, max_retries: int = 3) -> list[dict[str, Any]]:
        """Replay all entries, retrying each up to max_retries."""
        results = []
        for entry in self._entries:
            ok = self.retry(entry, max_retries)
            results.append({"agent_key": entry.agent_key, "retried": ok, "error_category": entry.error_category})
        return results

    def replay_by_error_type(self, error_type: str, max_retries: int = 3) -> list[dict[str, Any]]:
        """Replay entries matching a specific error category."""
        results = []
        for entry in self._entries:
            if entry.error_category == error_type:
                ok = self.retry(entry, max_retries)
                results.append({"agent_key": entry.agent_key, "retried": ok, "error_category": entry.error_category})
        return results

    def get_stats(self) -> dict[str, Any]:
        """Return summary statistics for all entries."""
        categories = Counter(e.error_category for e in self._entries)
        return {
            "total": len(self._entries),
            "by_error_type": dict(categories),
        }

    def __len__(self) -> int:
        return len(self._entries)
