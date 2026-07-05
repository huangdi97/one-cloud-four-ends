"""将 Agent 执行隔离到独立子进程。"""

import concurrent.futures
import logging
from concurrent.futures import ProcessPoolExecutor, TimeoutError

logger = logging.getLogger(__name__)


def _run_agent_task(task: dict) -> dict:
    """在子进程中执行 Agent 任务。"""
    try:
        agent_key = task["agent_key"]
        goal = task["goal"]
        from cloud.app.agent_runtime.core.agent_specs import AGENT_SPECS
        from cloud.app.agent_runtime.core.runtime_core import RuntimeCore

        spec = AGENT_SPECS.get(agent_key)
        if not spec:
            return {"status": "error", "result": f"unknown agent_key: {agent_key}"}
        import sqlite3 as _sqlite3

        from cloud.app.database import DB_PATH as _DB_PATH

        conn = _sqlite3.connect(_DB_PATH)
        conn.row_factory = _sqlite3.Row
        try:
            runtime = RuntimeCore(conn, conn, "", agent_key)
            result = runtime.execute(goal, agent_key, task.get("context"))
            return result.model_dump()
        finally:
            conn.close()
    except (TimeoutError, concurrent.futures.CancelledError) as exc:
        return {"status": "error", "result": str(exc)}


class AgentWorker:
    """将 Agent 执行隔离到独立子进程。"""

    COMPUTE_INTENSIVE_AGENTS = {"compliance_monitor", "anomaly_analysis"}

    def __init__(self, agent_name: str, max_workers: int = 3):
        """Initialize worker with a process pool for agent execution."""
        self.agent_name = agent_name
        self._pool = ProcessPoolExecutor(max_workers=max_workers)

    async def execute(self, task: dict, timeout: int = 60) -> dict:
        """execute."""
        future = self._pool.submit(_run_agent_task, task)
        try:
            return future.result(timeout=timeout)
        except TimeoutError:
            future.cancel()
            logger.warning("Agent %s task timed out after %ds, killing process", self.agent_name, timeout)
            return {"status": "timeout", "result": f"task timed out after {timeout}s"}
        except (TimeoutError, concurrent.futures.TimeoutError) as exc:
            logger.error("Agent %s task failed: %s", self.agent_name, exc)
            return {"status": "error", "result": str(exc)}

    def health(self) -> bool:
        """Check whether the process pool is responsive."""
        try:
            future = self._pool.submit(lambda: True)
            return future.result(timeout=5)
        except (TimeoutError, concurrent.futures.CancelledError):
            logger.warning("Agent worker异常", exc_info=True)
            return False

    def shutdown(self):
        """shutdown."""
        self._pool.shutdown(wait=False)
