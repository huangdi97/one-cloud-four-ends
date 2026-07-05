"""会话管理器 — Agent 会话创建/获取/关闭/清理。"""

import time
import uuid


class Session:
    """Agent 执行会话，含生命周期管理。"""

    def __init__(self, session_id: str, user_id: str, agent_key: str):
        self.session_id = session_id
        self.user_id = user_id
        self.agent_key = agent_key
        self.created_at = time.time()
        self.last_active = time.time()
        self.status = "active"  # active | expired | closed

    def touch(self) -> None:
        """更新最后活跃时间。"""
        self.last_active = time.time()

    def close(self) -> None:
        """关闭会话。"""
        self.status = "closed"

    def is_expired(self, max_idle_minutes: int = 30) -> bool:
        """检查是否超时。"""
        return (time.time() - self.last_active) > max_idle_minutes * 60

    def to_dict(self) -> dict:
        """Serialize the session to a dictionary."""
        return {
            "session_id": self.session_id,
            "user_id": self.user_id,
            "agent_key": self.agent_key,
            "status": self.status,
            "created_at": self.created_at,
            "last_active": self.last_active,
        }


class SessionManager:
    """管理所有 Agent 会话。"""

    def __init__(self):
        self._sessions: dict[str, Session] = {}

    def create_session(self, user_id: str, agent_key: str) -> str:
        """Create a new session and return its ID."""
        session_id = str(uuid.uuid4())[:8]
        self._sessions[session_id] = Session(session_id, user_id, agent_key)
        return session_id

    def get_session(self, session_id: str) -> Session | None:
        """Retrieve an active session by ID, or None."""
        session = self._sessions.get(session_id)
        if session is None:
            return None
        if session.status == "expired" or session.status == "closed":
            return None
        session.touch()
        return session

    def close_session(self, session_id: str) -> None:
        """Close the session with the given ID."""
        session = self._sessions.get(session_id)
        if session:
            session.close()

    def cleanup_expired(self, max_idle_minutes: int = 30) -> int:
        """Mark idle active sessions as expired; return the count."""
        now = time.time()
        expired = [sid for sid, s in self._sessions.items() if s.status == "active" and (now - s.last_active) > max_idle_minutes * 60]
        for sid in expired:
            self._sessions[sid].status = "expired"
        return len(expired)

    def active_count(self) -> int:
        """Return the number of active sessions."""
        return sum(1 for s in self._sessions.values() if s.status == "active")
