"""Agent 使用审计日志 — 记录每条Agent交互并生成聚合报告。"""

import logging
import sqlite3
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

VALID_USER_ACTIONS = ("accepted", "dismissed", "asked", "modified")

CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS agent_audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tenant_id TEXT DEFAULT 'default',
    timestamp TEXT NOT NULL,
    user_id TEXT NOT NULL,
    agent_key TEXT NOT NULL,
    task_type TEXT DEFAULT '',
    confidence REAL DEFAULT 0.0,
    user_action TEXT NOT NULL,
    feedback TEXT DEFAULT '',
    created_at TEXT DEFAULT (datetime('now'))
)
"""

CREATE_INDEX_SQL = [
    "CREATE INDEX IF NOT EXISTS idx_audit_ts ON agent_audit_log(timestamp)",
    "CREATE INDEX IF NOT EXISTS idx_audit_user ON agent_audit_log(user_id)",
    "CREATE INDEX IF NOT EXISTS idx_audit_agent ON agent_audit_log(agent_key)",
    "CREATE INDEX IF NOT EXISTS idx_audit_action ON agent_audit_log(user_action)",
    "CREATE INDEX IF NOT EXISTS idx_audit_tenant ON agent_audit_log(tenant_id)",
]


class AgentAuditor:
    def __init__(self, db: sqlite3.Connection):
        """Initialize the auditor with a database connection."""
        self._db = db
        self._ensure_table()

    def _ensure_table(self) -> None:
        self._db.execute(CREATE_TABLE_SQL)
        for idx_sql in CREATE_INDEX_SQL:
            try:
                self._db.execute(idx_sql)
            except sqlite3.Error:
                pass
        self._db.commit()

    def log_interaction(
        self,
        user_id: str,
        agent_key: str,
        user_action: str,
        task_type: str = "",
        confidence: float = 0.0,
        feedback: str = "",
        timestamp: str | None = None,
    ) -> None:
        """Log a single agent interaction to the audit database."""
        if user_action not in VALID_USER_ACTIONS:
            logger.warning("AgentAuditor: invalid user_action '%s', using 'accepted'", user_action)
            user_action = "accepted"
        ts = timestamp or datetime.utcnow().isoformat()
        try:
            self._db.execute(
                "INSERT INTO agent_audit_log (timestamp, user_id, agent_key, task_type, confidence, user_action, feedback) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (ts, user_id, agent_key, task_type, confidence, user_action, feedback),
            )
            self._db.commit()
        except sqlite3.Error:
            logger.exception("AgentAuditor: failed to log interaction")

    def query_logs(
        self,
        user_id: str = "",
        agent_key: str = "",
        user_action: str = "",
        start: str = "",
        end: str = "",
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict]:
        """Query audit logs with optional filters."""
        query = "SELECT * FROM agent_audit_log WHERE 1=1"
        params: list[str] = []
        if user_id:
            query += " AND user_id=?"
            params.append(user_id)
        if agent_key:
            query += " AND agent_key=?"
            params.append(agent_key)
        if user_action:
            query += " AND user_action=?"
            params.append(user_action)
        if start:
            query += " AND timestamp>=?"
            params.append(start)
        if end:
            query += " AND timestamp<=?"
            params.append(end)
        query += " ORDER BY timestamp DESC LIMIT ? OFFSET ?"
        params.extend([str(limit), str(offset)])
        rows = self._db.execute(query, params).fetchall()
        return [dict(r) for r in rows]

    def get_adoption_rate(self, days: int = 7) -> dict:
        """Compute the adoption rate (accepted / total) over the given period."""
        cutoff = (datetime.utcnow() - timedelta(days=days)).isoformat()
        total = self._db.execute("SELECT COUNT(*) as cnt FROM agent_audit_log WHERE timestamp>=?", (cutoff,)).fetchone()["cnt"]
        if total == 0:
            return {"rate": 0.0, "total": 0, "accepted": 0}
        accepted = self._db.execute(
            "SELECT COUNT(*) as cnt FROM agent_audit_log WHERE timestamp>=? AND user_action='accepted'",
            (cutoff,),
        ).fetchone()["cnt"]
        return {"rate": round(accepted / total * 100, 2), "total": total, "accepted": accepted}

    def get_feedback_trends(self, days: int = 7) -> list[dict]:
        """Return daily user-action counts for the given period."""
        cutoff = (datetime.utcnow() - timedelta(days=days)).isoformat()
        rows = self._db.execute(
            "SELECT DATE(timestamp) as day, user_action, COUNT(*) as count "
            "FROM agent_audit_log WHERE timestamp>=? "
            "GROUP BY DATE(timestamp), user_action ORDER BY day",
            (cutoff,),
        ).fetchall()
        return [dict(r) for r in rows]

    def get_high_dismiss(self, days: int = 7, min_count: int = 3) -> list[dict]:
        """Return agents with dismiss counts above min_count."""
        cutoff = (datetime.utcnow() - timedelta(days=days)).isoformat()
        rows = self._db.execute(
            "SELECT agent_key, COUNT(*) as dismiss_count "
            "FROM agent_audit_log WHERE timestamp>=? AND user_action='dismissed' "
            "GROUP BY agent_key HAVING dismiss_count>=? ORDER BY dismiss_count DESC",
            (cutoff, min_count),
        ).fetchall()
        return [dict(r) for r in rows]

    def get_summary_report(self, days: int = 7) -> dict:
        """Generate a summary report of audit data for the given period."""
        cutoff = (datetime.utcnow() - timedelta(days=days)).isoformat()
        rows = self._db.execute(
            "SELECT user_action, COUNT(*) as count FROM agent_audit_log WHERE timestamp>=? GROUP BY user_action",
            (cutoff,),
        ).fetchall()
        action_counts = {r["user_action"]: r["count"] for r in rows}
        total = sum(action_counts.values())
        if total == 0:
            return {"total": 0, "actions": {}, "adoption_rate": 0.0, "top_dismissed": []}
        adoption = action_counts.get("accepted", 0) / total * 100
        top_dismissed = self.get_high_dismiss(days, 1)
        return {
            "total": total,
            "actions": action_counts,
            "adoption_rate": round(adoption, 2),
            "top_dismissed": top_dismissed,
        }
