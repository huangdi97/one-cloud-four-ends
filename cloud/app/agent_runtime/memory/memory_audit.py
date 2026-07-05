"""记忆审计日志 — 记录记忆操作的可追溯日志。"""

import sqlite3
from datetime import datetime


class MemoryAuditLogger:
    """记忆操作审计日志记录器。"""

    def __init__(self, db: sqlite3.Connection | None):
        self._db = db
        self._fallback_log: list[dict] = []
        if db:
            self._ensure_table()

    def _ensure_table(self) -> None:
        self._db.execute(
            "CREATE TABLE IF NOT EXISTS memory_audit_log ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT, "
            "timestamp TEXT, action TEXT, agent_key TEXT, "
            "user_id INTEGER, key TEXT, value_preview TEXT)"
        )
        self._db.commit()

    def log(self, action: str, agent_key: str, user_id: int, key: str, value: str = "") -> None:
        entry = {
            "timestamp": datetime.now().isoformat(),
            "action": action,
            "agent_key": agent_key,
            "user_id": user_id,
            "key": key,
            "value_preview": str(value)[:200],
        }
        if self._db:
            try:
                self._db.execute(
                    "INSERT INTO memory_audit_log (timestamp, action, agent_key, user_id, key, value_preview) VALUES (?, ?, ?, ?, ?, ?)",
                    (entry["timestamp"], entry["action"], entry["agent_key"], entry["user_id"], entry["key"], entry["value_preview"]),
                )
                self._db.commit()
            except sqlite3.Error:
                pass
        self._fallback_log.append(entry)

    def query(self, agent_key: str | None = None, action: str | None = None, limit: int = 50) -> list[dict]:
        """查询审计日志，支持按 agent_key 和 action 过滤。"""
        results = []
        if self._db:
            try:
                sql = "SELECT * FROM memory_audit_log WHERE 1=1"
                params = []
                if agent_key:
                    sql += " AND agent_key=?"
                    params.append(agent_key)
                if action:
                    sql += " AND action=?"
                    params.append(action)
                sql += " ORDER BY id DESC LIMIT ?"
                params.append(limit)
                rows = self._db.execute(sql, params).fetchall()
                results = [dict(r) for r in rows]
            except sqlite3.Error:
                pass
        if not results and self._fallback_log:
            results = self._fallback_log[-limit:]
            if agent_key:
                results = [r for r in results if r.get("agent_key") == agent_key]
            if action:
                results = [r for r in results if r.get("action") == action]
        return list(reversed(results))
