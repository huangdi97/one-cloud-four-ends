"""Agent 调度器，定时轮询任务队列并触发 Agent 执行。"""

import logging
import re
import threading
import time
from datetime import datetime, timedelta

from cloud.app.agent_runtime.core.agent_registry import AgentRegistry
from cloud.app.agent_runtime.core.models import RuntimeResult
from cloud.app.agent_runtime.core.queue_manager import AgentQueueManager
from cloud.app.agent_runtime.core.runtime_core import RuntimeCore

logger = logging.getLogger(__name__)


def _cron_to_interval(cron_expr: str) -> int | None:
    """Convert a cron expression to interval in seconds.
    Only supports "0 */N * * *" (every N hours) and "*/N * * * *" (every N minutes).
    """
    cron_expr = cron_expr.strip()
    m = re.match(r"^0\s+\*/(\d+)\s+\*\s+\*\s+\*$", cron_expr)
    if m:
        return int(m.group(1)) * 3600
    m = re.match(r"^\*/(\d+)\s+\*\s+\*\s+\*\s+\*$", cron_expr)
    if m:
        return int(m.group(1)) * 60
    return None


class AgentScheduler:
    """后台线程调度器，按间隔调度 Agent 任务并处理队列消费。"""

    def __init__(self, db, runtime_factory=None):
        self._db = db
        self._runtime_factory = runtime_factory
        self._queue = AgentQueueManager(db)
        self._running = False
        self._thread = None

    def start(self):
        """Start the scheduler background thread and schedule all registered agents."""
        self._queue.recover()
        self._running = True
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()
        for agent in AgentRegistry.list():
            cron = agent.identity.trigger_cron
            if cron:
                interval = _cron_to_interval(cron)
                if interval:
                    self.schedule_agent(agent.identity.key, interval, f"执行 {agent.identity.role}")
                else:
                    self.schedule_agent(agent.identity.key, 3600, f"执行 {agent.identity.role}")

    def stop(self):
        """Stop the scheduler background thread."""
        self._running = False

    def schedule_agent(self, agent_key: str, interval_seconds: int, goal: str):
        """Enqueue an agent task for execution after the specified interval."""
        scheduled_at = (datetime.now() + timedelta(seconds=interval_seconds)).isoformat()
        self._queue.enqueue(agent_key, goal, scheduled_at)

    def trigger_now(self, agent_key: str, goal: str, auth_header: str) -> RuntimeResult:
        """Immediately execute an agent task with the given goal and auth."""
        runtime = self._runtime_factory() if self._runtime_factory else RuntimeCore(self._db, self._db, auth_header, agent_key)
        return runtime.execute(goal, agent_key)

    def _run_loop(self):
        while self._running:
            try:
                task = self._queue.dequeue()
                if task is not None:
                    self._process_task(task)
            except (KeyError, TypeError, ValueError) as e:
                if task:
                    self._queue.fail(task["id"], str(e))
            time.sleep(30)

    def _process_task(self, task):
        from cloud.app.agent_runtime.core.agent_health import get_health_tracker

        agent_key = task["agent_key"]
        if get_health_tracker().is_unhealthy(agent_key):
            logger.warning("Skipping unhealthy agent: %s", agent_key)
            self._queue.fail(task["id"], "agent unhealthy")
            time.sleep(30)
            return
        auth_header = ""
        runtime = self._runtime_factory() if self._runtime_factory else RuntimeCore(self._db, self._db, auth_header, agent_key)
        result = runtime.execute(task["goal"], agent_key)
        if result.status == "completed":
            self._queue.complete(task["id"], result.result)
        else:
            self._queue.fail(task["id"], result.result)
