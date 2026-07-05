"""Approval request data models and manager."""

import json
import logging
import uuid
from datetime import datetime

logger = logging.getLogger(__name__)

APPROVAL_TIMEOUT_HOURS = 24


class ApprovalRequest:
    def __init__(
        self,
        request_id: str,
        agent_name: str,
        action: str,
        detail: dict,
        status: str = "pending",
        created_at: str | None = None,
        expires_at: str | None = None,
    ):
        """Initialize an approval request with metadata."""
        self.request_id = request_id
        self.agent_name = agent_name
        self.action = action
        self.detail = detail
        self.status = status
        self.created_at = created_at or datetime.now().isoformat()
        self.expires_at = expires_at

    def to_dict(self) -> dict:
        """to dict."""
        return {
            "request_id": self.request_id,
            "agent_name": self.agent_name,
            "action": self.action,
            "detail": self.detail,
            "status": self.status,
            "created_at": self.created_at,
            "expires_at": self.expires_at,
        }


class ApprovalRequestManager:
    def __init__(self, db):
        """Initialize with database connection."""
        self._db = db

    def create_request(self, agent_name: str, action: str, detail: dict) -> ApprovalRequest:
        """create request."""
        request_id = str(uuid.uuid4())
        now = datetime.now().isoformat()
        self._db.execute(
            "INSERT INTO agent_runtime_approvals (trace_id, agent_key, goal, step, tool, params, reasoning, status, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (request_id, agent_name, action, 0, action, json.dumps(detail, ensure_ascii=False), "", "pending", now),
        )
        self._db.commit()
        return ApprovalRequest(request_id=request_id, agent_name=agent_name, action=action, detail=detail, created_at=now)

    def get_request(self, request_id: str) -> ApprovalRequest | None:
        """get request."""
        row = self._db.execute(
            "SELECT * FROM agent_runtime_approvals WHERE trace_id=?",
            (request_id,),
        ).fetchone()
        if not row:
            return None
        return ApprovalRequest(
            request_id=row["trace_id"],
            agent_name=row["agent_key"],
            action=row["goal"],
            detail=json.loads(row["params"]) if row["params"] else {},
            status=row["status"],
            created_at=row["created_at"],
        )

    def approve(self, request_id: str, responded_by: str = "") -> bool:
        """approve."""
        now = datetime.now().isoformat()
        cur = self._db.execute(
            "UPDATE agent_runtime_approvals SET status='approved', responded_at=?, responded_by=? WHERE trace_id=? AND status='pending'",
            (now, responded_by, request_id),
        )
        self._db.commit()
        return cur.rowcount > 0

    def reject(self, request_id: str, responded_by: str = "") -> bool:
        """reject."""
        now = datetime.now().isoformat()
        cur = self._db.execute(
            "UPDATE agent_runtime_approvals SET status='rejected', responded_at=?, responded_by=? WHERE trace_id=? AND status='pending'",
            (now, responded_by, request_id),
        )
        self._db.commit()
        return cur.rowcount > 0

    def begin_editing(self, request_id: str, editor: str = "") -> bool:
        """transition rejected → editing."""
        now = datetime.now().isoformat()
        cur = self._db.execute(
            "UPDATE agent_runtime_approvals SET status='editing', responded_at=?, responded_by=? WHERE trace_id=? AND status='rejected'",
            (now, editor, request_id),
        )
        self._db.commit()
        return cur.rowcount > 0

    def resubmit(self, request_id: str, params: dict) -> bool:
        """transition editing → resubmitted, updating params."""
        now = datetime.now().isoformat()
        cur = self._db.execute(
            "UPDATE agent_runtime_approvals SET status='resubmitted', params=?, responded_at=? WHERE trace_id=? AND status='editing'",
            (json.dumps(params, ensure_ascii=False), now, request_id),
        )
        self._db.commit()
        return cur.rowcount > 0

    def get_pending_requests(self) -> list[ApprovalRequest]:
        """get pending requests."""
        rows = self._db.execute("SELECT * FROM agent_runtime_approvals WHERE status='pending' ORDER BY created_at ASC").fetchall()
        return [
            ApprovalRequest(
                request_id=r["trace_id"],
                agent_name=r["agent_key"],
                action=r["goal"],
                detail=json.loads(r["params"]) if r["params"] else {},
                status=r["status"],
                created_at=r["created_at"],
            )
            for r in rows
        ]

    def check_timeouts(self) -> int:
        """check timeouts."""
        expired = 0
        for req in self.get_pending_requests():
            if req.created_at:
                created = datetime.fromisoformat(req.created_at)
                elapsed_hours = (datetime.now() - created).total_seconds() / 3600
                if elapsed_hours >= APPROVAL_TIMEOUT_HOURS:
                    self._db.execute(
                        "UPDATE agent_runtime_approvals SET status='rejected', responded_at=? WHERE trace_id=? AND status='pending'",
                        (datetime.now().isoformat(), req.request_id),
                    )
                    self._db.commit()
                    expired += 1
                    logger.warning("Approval %s auto-rejected after timeout", req.request_id)
        return expired
