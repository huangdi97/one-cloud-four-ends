"""Tracks agent health status (healthy/degraded/stale/unhealthy)."""

from datetime import datetime, timezone
from threading import Lock
from typing import Literal

AgentStatus = Literal["healthy", "degraded", "stale"]


class AgentHealthRecord:
    last_run_at: str = ""
    last_success_at: str = ""
    total_runs: int = 0
    success_count: int = 0
    fail_count: int = 0
    last_error: str = ""
    status: AgentStatus = "healthy"


class HealthTracker:
    def __init__(self):
        self._records: dict[str, AgentHealthRecord] = {}
        self._consecutive_failures: dict[str, int] = {}
        self._lock = Lock()

    def _get_or_create(self, agent_name: str) -> AgentHealthRecord:
        if agent_name not in self._records:
            self._records[agent_name] = AgentHealthRecord()
        return self._records[agent_name]

    def record_run(self, agent_name: str, success: bool, error: str = ""):
        """Record a run outcome for the given agent."""
        with self._lock:
            record = self._get_or_create(agent_name)
            now = datetime.now(timezone.utc).isoformat()
            record.last_run_at = now
            record.total_runs += 1
            if success:
                record.last_success_at = now
                record.success_count += 1
                self._consecutive_failures[agent_name] = 0
            else:
                record.fail_count += 1
                if error:
                    record.last_error = error
                consecutive = self._consecutive_failures.get(agent_name, 0) + 1
                self._consecutive_failures[agent_name] = consecutive
                if consecutive >= 3:
                    record.status = "unhealthy"
                    return
            self._update_status(record)

    @staticmethod
    def _update_status(record: AgentHealthRecord):
        if record.total_runs == 0:
            record.status = "healthy"
            return
        fail_rate = record.fail_count / record.total_runs
        if fail_rate > 0.5 and record.total_runs >= 5:
            record.status = "degraded"
        elif fail_rate > 0.8:
            record.status = "degraded"
        else:
            record.status = "healthy"

    def is_unhealthy(self, agent_name: str) -> bool:
        """Check if the agent has been marked unhealthy."""
        with self._lock:
            record = self._get_or_create(agent_name)
            return record.status == "unhealthy"

    def mark_stale(self, agent_name: str):
        """Mark the agent as stale."""
        with self._lock:
            record = self._get_or_create(agent_name)
            record.status = "stale"

    def mark_unhealthy(self, agent_name: str):
        """Mark the agent as unhealthy."""
        with self._lock:
            record = self._get_or_create(agent_name)
            record.status = "unhealthy"

    def get_health(self, agent_name: str) -> dict:
        """Return the health record for the given agent."""
        with self._lock:
            record = self._get_or_create(agent_name)
            return {
                "agent_name": agent_name,
                "status": record.status,
                "last_run_at": record.last_run_at,
                "last_success_at": record.last_success_at,
                "total_runs": record.total_runs,
                "success_count": record.success_count,
                "fail_count": record.fail_count,
                "last_error": record.last_error,
                "consecutive_failures": self._consecutive_failures.get(agent_name, 0),
            }

    def get_all_health(self) -> list[dict]:
        """Return health records for all tracked agents."""
        with self._lock:
            return [self.get_health(name) for name in self._records]

    def get_summary(self) -> dict:
        """Return a summary of agent health counts."""
        with self._lock:
            total = len(self._records)
            healthy = sum(1 for r in self._records.values() if r.status == "healthy")
            degraded = sum(1 for r in self._records.values() if r.status == "degraded")
            stale = sum(1 for r in self._records.values() if r.status == "stale")
            unhealthy = sum(1 for r in self._records.values() if r.status == "unhealthy")
            return {
                "total_agents": total,
                "healthy": healthy,
                "degraded": degraded,
                "stale": stale,
                "unhealthy": unhealthy,
            }


_health_tracker: HealthTracker | None = None
_tracker_lock = Lock()


def get_health_tracker() -> HealthTracker:
    """Return the singleton HealthTracker instance."""
    global _health_tracker
    if _health_tracker is None:
        with _tracker_lock:
            if _health_tracker is None:
                _health_tracker = HealthTracker()
    return _health_tracker
