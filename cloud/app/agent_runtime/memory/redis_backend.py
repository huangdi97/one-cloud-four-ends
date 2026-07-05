"""Redis backend for SharedState — fallback to in-memory dict when REDIS_URL not set."""

import json
import logging
import os
import threading
import time
from typing import Any

logger = logging.getLogger(__name__)


class RedisBackend:
    def __init__(self, redis_url: str | None = None):
        self._redis_url = redis_url or os.getenv("REDIS_URL", "")
        self._in_memory: dict[str, tuple[Any, float]] = {}
        self._mem_lock = threading.Lock()
        self._redis = None
        if self._redis_url:
            try:
                import redis as _redis_module

                self._redis = _redis_module.Redis.from_url(self._redis_url, decode_responses=True)
                self._redis.ping()
                logger.info("RedisBackend connected to %s", self._redis_url)
            except Exception:
                logger.warning("RedisBackend: redis unavailable, fallback to in-memory")
                self._redis = None

    @property
    def available(self) -> bool:
        """检查 Redis 后端是否可用。"""
        return self._redis is not None

    def get(self, key: str) -> Any | None:
        """从后端获取键对应的值，支持 TTL 过期。"""
        if self._redis:
            val = self._redis.get(key)
            if val is None:
                return None
            try:
                return json.loads(val)
            except (json.JSONDecodeError, TypeError):
                return val
        with self._mem_lock:
            entry = self._in_memory.get(key)
            if entry is None:
                return None
            value, expires_at = entry
            if expires_at and time.time() > expires_at:
                del self._in_memory[key]
                return None
            return value

    def set(self, key: str, value: Any, ttl: int | None = None) -> None:
        """写入键值对到后端，可选 TTL。"""
        if self._redis:
            serialized = json.dumps(value, ensure_ascii=False, default=str)
            if ttl:
                self._redis.setex(key, ttl, serialized)
            else:
                self._redis.set(key, serialized)
            return
        with self._mem_lock:
            expires_at = (time.time() + ttl) if ttl else 0.0
            self._in_memory[key] = (value, expires_at)

    def delete(self, key: str) -> None:
        """从后端删除键值对。"""
        if self._redis:
            self._redis.delete(key)
            return
        with self._mem_lock:
            self._in_memory.pop(key, None)
