"""Agent 后台任务队列 — 支持 Redis 和内存两种后端。"""

import asyncio
import json
import logging
import os
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"


@dataclass
class AgentTask:
    task_id: str
    goal: str
    agent_key: str
    context: dict | None = None
    status: TaskStatus = TaskStatus.PENDING
    result: Any = None
    error: str = ""
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)


class AgentTaskQueue:
    def __init__(self, max_workers: int = 4):
        """Initialize the task queue with optional Redis backend."""
        self._tasks: dict[str, AgentTask] = {}
        self._lock = threading.Lock()
        self._executor = ThreadPoolExecutor(max_workers=max_workers)
        self._redis = None
        self._event_loop: asyncio.AbstractEventLoop | None = None

        redis_url = os.getenv("REDIS_URL", "")
        if redis_url:
            try:
                import redis as _redis_module

                self._redis = _redis_module.Redis.from_url(redis_url, decode_responses=True)
                self._redis.ping()
                logger.info("AgentTaskQueue connected to %s", redis_url)
            except Exception:
                logger.warning("AgentTaskQueue: redis unavailable, fallback to in-memory")
                self._redis = None

    def _run_agent(self, task_id: str) -> None:
        task = self._get_task(task_id)
        if not task:
            return
        try:
            task.status = TaskStatus.RUNNING
            task.updated_at = time.time()
            self._update_task(task)

            from cloud.app.agent_runtime.core.agent_worker import AgentWorker

            worker = AgentWorker()
            result = worker.execute(task.goal, task.agent_key, task.context)
            task.status = TaskStatus.DONE
            task.result = result
        except Exception as e:
            task.status = TaskStatus.FAILED
            task.error = str(e)
            logger.exception("AgentTaskQueue: task %s failed", task_id)
        finally:
            task.updated_at = time.time()
            self._update_task(task)

    def _get_task(self, task_id: str) -> AgentTask | None:
        if self._redis:
            raw = self._redis.get(f"agent_task:{task_id}")
            if raw:
                data = json.loads(raw)
                return AgentTask(**data)
            return None
        with self._lock:
            return self._tasks.get(task_id)

    def _update_task(self, task: AgentTask) -> None:
        if self._redis:
            self._redis.setex(f"agent_task:{task.task_id}", 86400, json.dumps(task.__dict__, default=str))
            return
        with self._lock:
            self._tasks[task.task_id] = task

    def submit(self, goal: str, agent_key: str, context: dict | None = None) -> str:
        """Submit a new agent task and return its ID."""
        task_id = str(uuid.uuid4())
        task = AgentTask(task_id=task_id, goal=goal, agent_key=agent_key, context=context)
        self._update_task(task)

        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            loop.run_in_executor(self._executor, self._run_agent, task_id)
        else:
            self._executor.submit(self._run_agent, task_id)

        logger.info("AgentTaskQueue: submitted task %s (agent=%s)", task_id, agent_key)
        return task_id

    def get_result(self, task_id: str) -> dict | None:
        """Get the result of a previously submitted task."""
        task = self._get_task(task_id)
        if not task:
            return None
        return {
            "task_id": task.task_id,
            "status": task.status.value,
            "result": task.result,
            "error": task.error,
            "created_at": task.created_at,
            "updated_at": task.updated_at,
        }

    def list_tasks(self, limit: int = 20) -> list[dict]:
        """List recent tasks, up to the given limit."""
        if self._redis:
            keys = self._redis.keys("agent_task:*")
            tasks = []
            for key in sorted(keys, reverse=True)[:limit]:
                raw = self._redis.get(key)
                if raw:
                    data = json.loads(raw)
                    tasks.append(
                        {
                            "task_id": data["task_id"],
                            "status": data["status"],
                            "goal": data["goal"][:80],
                            "agent_key": data["agent_key"],
                            "created_at": data["created_at"],
                        }
                    )
            return tasks
        with self._lock:
            sorted_tasks = sorted(self._tasks.values(), key=lambda t: t.created_at, reverse=True)
            return [
                {
                    "task_id": t.task_id,
                    "status": t.status.value,
                    "goal": t.goal[:80],
                    "agent_key": t.agent_key,
                    "created_at": t.created_at,
                }
                for t in sorted_tasks[:limit]
            ]

    def shutdown(self, timeout: float = 30.0) -> None:
        """Shut down the task queue executor."""
        self._executor.shutdown(wait=True, timeout=timeout)
        logger.info("AgentTaskQueue: shut down")


_global_queue: AgentTaskQueue | None = None
_queue_lock = threading.Lock()


def get_task_queue() -> AgentTaskQueue:
    """Get or create the global singleton task queue."""
    global _global_queue
    if _global_queue is None:
        with _queue_lock:
            if _global_queue is None:
                _global_queue = AgentTaskQueue()
    return _global_queue
