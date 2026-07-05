"""HITL 审批回路 — 提交/审批/超时处理。"""

import logging
import threading
import uuid
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT_SECONDS = 3600


class ApprovalQueue:
    def __init__(self, timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS):
        """Initialize an empty approval queue with the given timeout."""
        self._timeout = timeout_seconds
        self._lock = threading.Lock()
        self._items: dict[str, dict] = {}

    def submit(self, requester: str, action: str, context: dict | None = None) -> str:
        """Submit a new approval request and return its ID."""
        item_id = uuid.uuid4().hex[:12]
        item = {
            "id": item_id,
            "requester": requester,
            "action": action,
            "context": context or {},
            "status": "pending",
            "created_at": datetime.utcnow().isoformat(),
            "decided_at": None,
            "decided_by": None,
        }
        with self._lock:
            self._items[item_id] = item
        logger.info("ApprovalQueue: submitted %s by %s for %s", item_id, requester, action)
        return item_id

    def approve(self, item_id: str, approver: str) -> bool:
        """Approve a pending approval request. Returns True on success."""
        with self._lock:
            item = self._items.get(item_id)
            if not item or item["status"] != "pending":
                return False
            if self._is_expired(item):
                item["status"] = "expired"
                return False
            item["status"] = "approved"
            item["decided_at"] = datetime.utcnow().isoformat()
            item["decided_by"] = approver
        logger.info("ApprovalQueue: approved %s by %s", item_id, approver)
        return True

    def reject(self, item_id: str, approver: str) -> bool:
        """Reject a pending approval request. Returns True on success."""
        with self._lock:
            item = self._items.get(item_id)
            if not item or item["status"] != "pending":
                return False
            if self._is_expired(item):
                item["status"] = "expired"
                return False
            item["status"] = "rejected"
            item["decided_at"] = datetime.utcnow().isoformat()
            item["decided_by"] = approver
        logger.info("ApprovalQueue: rejected %s by %s", item_id, approver)
        return True

    def get_pending(self) -> list[dict]:
        """Return all pending (non-expired) approval items."""
        self._purge_expired()
        with self._lock:
            return [v for v in self._items.values() if v["status"] == "pending"]

    def get_by_id(self, item_id: str) -> dict | None:
        """Get an approval item by its ID, or None if not found."""
        with self._lock:
            item = self._items.get(item_id)
            if item and self._is_expired(item):
                item["status"] = "expired"
            return item

    def _is_expired(self, item: dict) -> bool:
        created = datetime.fromisoformat(item["created_at"])
        return datetime.utcnow() - created > timedelta(seconds=self._timeout)

    def _purge_expired(self):
        with self._lock:
            expired_ids = []
            for item_id, item in self._items.items():
                if item["status"] == "pending" and self._is_expired(item):
                    item["status"] = "expired"
                    expired_ids.append(item_id)
            if expired_ids:
                logger.info("ApprovalQueue: expired %d pending items", len(expired_ids))
