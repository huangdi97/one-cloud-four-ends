"""跨会话长期记忆，使用 JSON 文件持久化。"""

import json
import logging
import threading
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

DEFAULT_PATH = "data/long_term_memory.json"


class LongTermMemory:
    def __init__(self, storage_path: str = DEFAULT_PATH):
        self._path = Path(storage_path)
        self._lock = threading.Lock()
        self._data: dict = {"preferences": {}, "facts": {}, "feedback": []}
        self._load()

    def _load(self):
        if self._path.exists():
            try:
                with open(self._path) as f:
                    self._data = json.load(f)
            except Exception as e:
                logger.warning("LongTermMemory: failed to load %s: %s", self._path, e)

    def _save(self):
        self._path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self._path.with_suffix(".tmp")
        with open(tmp, "w") as f:
            json.dump(self._data, f, ensure_ascii=False, indent=2)
        tmp.replace(self._path)

    def remember(self, namespace: str, key: str, value, ttl: int | None = None) -> None:
        """记忆一个事实到指定 namespace。"""
        entry = {"value": value, "timestamp": datetime.utcnow().isoformat()}
        if ttl:
            entry["ttl"] = ttl
        with self._lock:
            if namespace not in self._data["facts"]:
                self._data["facts"][namespace] = {}
            self._data["facts"][namespace][key] = entry
            self._save()

    def recall(self, namespace: str, key: str | None = None):
        """从指定 namespace 回忆事实，支持 TTL 过期检查。"""
        with self._lock:
            facts = self._data.get("facts", {})
            if namespace not in facts:
                return None
            ns = facts[namespace]
            if key:
                raw = ns.get(key)
                if not raw:
                    return None
                if raw.get("ttl"):
                    created = datetime.fromisoformat(raw["timestamp"])
                    elapsed = (datetime.utcnow() - created).total_seconds()
                    if elapsed > raw["ttl"]:
                        del ns[key]
                        self._save()
                        return None
                return raw["value"]
            return {k: v["value"] for k, v in ns.items() if not self._is_expired(v)}

    @staticmethod
    def _is_expired(entry: dict) -> bool:
        if not entry.get("ttl"):
            return False
        created = datetime.fromisoformat(entry["timestamp"])
        return (datetime.utcnow() - created).total_seconds() > entry["ttl"]

    def learn_from_feedback(self, namespace: str, key: str, feedback: dict) -> None:
        """从反馈中学习并持久化。"""
        with self._lock:
            self._data["feedback"].append(
                {
                    "namespace": namespace,
                    "key": key,
                    "feedback": feedback,
                    "timestamp": datetime.utcnow().isoformat(),
                }
            )
            self._save()

    def get_preferences(self, namespace: str) -> dict:
        """获取指定 namespace 的偏好设置。"""
        with self._lock:
            return self._data.get("preferences", {}).get(namespace, {})

    def set_preference(self, namespace: str, key: str, value) -> None:
        """设置指定 namespace 的偏好值。"""
        with self._lock:
            if namespace not in self._data["preferences"]:
                self._data["preferences"][namespace] = {}
            self._data["preferences"][namespace][key] = value
            self._save()
