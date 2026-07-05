"""Agent 记忆与脑状态管理模块。"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from typing import Any


class Memory:
    """Agent 短期脑状态存储，支持键值对读写及 JSON/str/int/float 类型。"""

    _agent_db: sqlite3.Connection

    def __init__(self, agent_db: sqlite3.Connection) -> None:
        self._agent_db = agent_db
        self._vector_memory = None
        self._audit_logger = None

    def set_audit_logger(self, logger) -> None:
        """设置审计日志记录器。"""
        self._audit_logger = logger

    def set_vector_memory(self, vm) -> None:
        """设置向量记忆后端。"""
        self._vector_memory = vm

    def get(self, agent_key: str, key: str, user_id: int = 0) -> Any | None:
        """获取 Agent 短期记忆值。"""
        row = self._agent_db.execute(
            "SELECT value, value_type FROM agent_brains WHERE agent_key=? AND user_id=? AND key=?",
            (agent_key, user_id, key),
        ).fetchone()
        if not row:
            return None
        if row["value_type"] == "json":
            return json.loads(row["value"])
        if row["value_type"] == "int":
            return int(row["value"])
        if row["value_type"] == "float":
            return float(row["value"])
        return row["value"]

    def set(self, agent_key: str, key: str, value: Any, user_id: int = 0, importance: float = 0.5, caller_agent_key: str | None = None) -> None:
        """设置 Agent 短期记忆值。importance（0-1）用于后续淘汰策略。

        当传入 caller_agent_key 时，会校验 agent_key namespace 是否匹配该 Agent 身份。
        """
        if caller_agent_key is not None:
            from shared.agent_identity import get_identity

            identity = get_identity(caller_agent_key)
            allowed = identity.get("memory_namespace", caller_agent_key)
            if not agent_key.startswith(allowed):
                raise PermissionError(f"Agent {caller_agent_key} (namespace={allowed}) 无权写入 namespace={agent_key}")

        # 去重：内容相同则跳过
        existing = self.get(agent_key, key, user_id)
        if existing is not None and existing == value:
            return

        if isinstance(value, str):
            value_type = "str"
        elif isinstance(value, (int, float)):
            value_type = "int" if isinstance(value, int) else "float"
            value = str(value)
        else:
            value_type = "json"
            value = json.dumps(value, ensure_ascii=False)

        self._agent_db.execute(
            "INSERT INTO agent_brains (agent_key, user_id, key, value, value_type, updated_at, importance) "
            "VALUES (?, ?, ?, ?, ?, datetime('now'), ?) "
            "ON CONFLICT(agent_key, user_id, key) DO UPDATE SET value=excluded.value, "
            "value_type=excluded.value_type, updated_at=excluded.updated_at, importance=excluded.importance",
            (agent_key, user_id, key, value, value_type, importance),
        )
        self._agent_db.commit()
        if self._audit_logger:
            self._audit_logger.log("set", agent_key, user_id, key, str(value)[:100])

    def delete(self, agent_key: str, key: str, user_id: int = 0) -> None:
        """删除 Agent 短期记忆值。"""
        if self._audit_logger:
            existing = self.get(agent_key, key, user_id)
            self._audit_logger.log("delete", agent_key, user_id, key, str(existing)[:100] if existing else "")
        self._agent_db.execute(
            "DELETE FROM agent_brains WHERE agent_key=? AND user_id=? AND key=?",
            (agent_key, user_id, key),
        )
        self._agent_db.commit()

    def dedup(self, agent_key: str | None = None) -> int:
        """扫描并合并重复条目：内容完全相同的保留最新一条。返回删除数。"""
        deleted = 0
        if agent_key:
            rows = self._agent_db.execute(
                "SELECT key, value, value_type, user_id, MAX(updated_at) as max_ts "
                "FROM agent_brains WHERE agent_key=? GROUP BY key, value, value_type, user_id HAVING COUNT(*) > 1",
                (agent_key,),
            ).fetchall()
        else:
            rows = self._agent_db.execute(
                "SELECT key, value, value_type, user_id, MAX(updated_at) as max_ts "
                "FROM agent_brains GROUP BY key, value, value_type, user_id HAVING COUNT(*) > 1"
            ).fetchall()
        for row in rows:
            if agent_key:
                cur = self._agent_db.execute(
                    "DELETE FROM agent_brains WHERE agent_key=? AND key=? AND value=? AND value_type=? AND user_id=? AND updated_at < ?",
                    (agent_key, row["key"], row["value"], row["value_type"], row["user_id"], row["max_ts"]),
                )
            else:
                cur = self._agent_db.execute(
                    "DELETE FROM agent_brains WHERE key=? AND value=? AND value_type=? AND user_id=? AND updated_at < ?",
                    (row["key"], row["value"], row["value_type"], row["user_id"], row["max_ts"]),
                )
            deleted += cur.rowcount
        self._agent_db.commit()
        return deleted

    def search(self, agent_key: str, keyword: str, limit: int = 5) -> list[dict[str, Any]]:
        """搜索 Agent 短期记忆。"""
        rows = self._agent_db.execute(
            "SELECT key, value, value_type FROM agent_brains WHERE agent_key=? AND (key LIKE ? OR value LIKE ?) ORDER BY updated_at DESC LIMIT ?",
            (agent_key, f"%{keyword}%", f"%{keyword}%", limit),
        ).fetchall()
        return [dict(r) for r in rows]

    def hybrid_search(self, query: str, agent_key: str, limit: int = 5) -> list[dict[str, Any]]:
        """混合检索：关键词 + 向量语义检索，合并去重排序。"""
        seen = set()
        results = []

        kw_results = self.search(agent_key, query, limit=limit)
        for r in kw_results:
            key = r.get("key", "")
            if key not in seen:
                seen.add(key)
                r["_source"] = "keyword"
                r["_score"] = 0.5
                results.append(r)

        if self._vector_memory:
            try:
                vec_results = self._vector_memory.search(agent_key, query, top_k=limit)
                self._dedup_vector_results(vec_results, seen, results)
            except Exception:
                pass

        results.sort(key=lambda x: x.get("_score", 0), reverse=True)
        return results[:limit]

    def _dedup_vector_results(self, vec_results, seen, results):
        for r in vec_results:
            key = r.get("key", "")
            if key not in seen:
                seen.add(key)
                r["_source"] = "vector"
                r["_score"] = r.get("score", 0.0)
                results.append(r)


# --- 记忆压缩 & 淘汰 ---


def compress_messages(messages: list[dict], max_tokens: int = 4000) -> list[dict]:
    """压缩消息列表。"""
    if not messages:
        return messages
    total_chars = sum(len(m.get("content", "") or "") for m in messages)
    total_tokens = total_chars // 4
    if total_tokens <= max_tokens:
        return messages
    system_msgs = [m for m in messages if m.get("role") == "system"]
    non_system = [m for m in messages if m.get("role") != "system"]
    keep = non_system[-4:] if len(non_system) >= 4 else non_system
    mid = non_system[:-4] if len(non_system) >= 4 else []
    if mid:
        summary_text = " ".join(m.get("content", "")[:100] for m in mid if m.get("content"))
        summary = {"role": "system", "content": f"[记忆摘要：{summary_text[:200]}...]"}
        result = system_msgs + [summary] + keep
    else:
        result = system_msgs + keep
    return result


def evict_old_entries(db, agent_key: str | None = None, ttl_hours: int = 168) -> int:
    """删除超过 ttl_hours 的记忆条目。"""
    import time

    cutoff = time.time() - ttl_hours * 3600
    if agent_key:
        cur = db.execute("DELETE FROM agent_brains WHERE agent_key=? AND updated_at < ?", (agent_key, cutoff))
    else:
        cur = db.execute("DELETE FROM agent_brains WHERE updated_at < ?", (cutoff,))
    db.commit()
    return cur.rowcount


def evict_low_importance(db, threshold: float = 0.2, agent_key: str | None = None) -> int:
    """删除重要性低于 threshold 的记忆条目。"""
    if agent_key:
        cur = db.execute("DELETE FROM agent_brains WHERE agent_key=? AND importance < ?", (agent_key, threshold))
    else:
        cur = db.execute("DELETE FROM agent_brains WHERE importance < ?", (threshold,))
    db.commit()
    return cur.rowcount


def scheduled_maintenance(db, ttl_hours: int = 168, importance_threshold: float = 0.2) -> dict:
    """执行全部维护任务。"""
    old = evict_old_entries(db, ttl_hours=ttl_hours)
    low = evict_low_importance(db, threshold=importance_threshold)
    return {"evicted_old": old, "evicted_low_importance": low, "total": old + low}


class AgentMemory:
    """Agent 长期记忆存储，支持按 session 存取及关键词搜索。"""

    _business_db: sqlite3.Connection

    def __init__(self, business_db: sqlite3.Connection) -> None:
        self._business_db = business_db

    def save(self, agent_key: str, session_id: str, entry: dict[str, Any]) -> None:
        """保存 Agent 长期记忆条目。"""
        self._business_db.execute(
            "INSERT INTO memory_gates (agent_key, session_id, content, created_at) VALUES (?, ?, ?, ?)",
            (agent_key, session_id, json.dumps(entry), datetime.now().isoformat()),
        )
        self._business_db.commit()

    def load(self, agent_key: str, limit: int = 5) -> list[dict[str, Any]]:
        """加载 Agent 长期记忆。"""
        cur = self._business_db.execute(
            "SELECT * FROM memory_gates WHERE agent_key = ? ORDER BY created_at DESC LIMIT ?",
            (agent_key, limit),
        )
        return [dict(r) for r in cur.fetchall()]

    def search(self, agent_key: str, keyword: str, limit: int = 5) -> list[dict[str, Any]]:
        """搜索 Agent 长期记忆。"""
        rows = self._business_db.execute(
            "SELECT * FROM memory_gates WHERE agent_key=? AND content LIKE ? ORDER BY created_at DESC LIMIT ?",
            (agent_key, f"%{keyword}%", limit),
        ).fetchall()
        return [dict(r) for r in rows]

    def get_session(self, agent_key: str, session_id: str) -> dict[str, Any]:
        """获取指定 session 的全部记忆条目。"""
        cur = self._business_db.execute(
            "SELECT * FROM memory_gates WHERE agent_key = ? AND session_id = ? ORDER BY created_at",
            (agent_key, session_id),
        )
        rows = cur.fetchall()
        return {
            "agent_key": agent_key,
            "session_id": session_id,
            "entries": [dict(r) for r in rows],
        }


AgentBrain = Memory
