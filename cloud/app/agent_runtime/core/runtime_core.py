"""Agent运行时核心模块，提供"规划-决策-反思-执行-验证"五阶段执行循环；通过RuntimeState状态管理与StateSnapshot快照回滚机制保障任务可靠执行。"""

import asyncio
import logging
import os
import threading
import time
import uuid
from datetime import datetime

from cloud.app.agent_runtime.comm.notifier import Notifier
from cloud.app.agent_runtime.comm.streamer import AgentStreamer
from cloud.app.agent_runtime.core.agent_health import get_health_tracker
from cloud.app.agent_runtime.core.agent_registry import AgentRegistry
from cloud.app.agent_runtime.core.agent_state_machine import AgentStateMachine
from cloud.app.agent_runtime.core.error_categories import categorize_error
from cloud.app.agent_runtime.core.loop_detector import LoopDetector
from cloud.app.agent_runtime.core.models import RuntimeResult
from cloud.app.agent_runtime.core.planner import Planner
from cloud.app.agent_runtime.core.runtime_core_tools import RuntimeCoreTools
from cloud.app.agent_runtime.core.runtime_helpers import CompositionHelper
from cloud.app.agent_runtime.core.runtime_state import ApprovalManager, RuntimeState
from cloud.app.agent_runtime.lifecycle.circuit_breaker import CircuitBreaker
from cloud.app.agent_runtime.lifecycle.execution_loop import ExecutionEngine
from cloud.app.agent_runtime.lifecycle.rollback_handler import RollbackHandler
from cloud.app.agent_runtime.lifecycle.tracer import AgentTracer
from cloud.app.agent_runtime.memory.memory import Memory
from cloud.app.agent_runtime.memory.state_snapshot import StateSnapshot
from cloud.app.agent_runtime.memory.vector_memory import VectorMemory
from cloud.app.agent_runtime.metrics.agent_metrics import (
    agent_call_duration_seconds,
    agent_calls_total,
    agent_token_consumed_total,
    agent_tool_calls_total,
)
from cloud.app.agent_runtime.reflection.reflector import Reflector
from cloud.app.agent_runtime.runtime_llm import RuntimeLLM
from cloud.app.agent_runtime.safety.bulkhead import Bulkhead
from cloud.app.agent_runtime.safety.content_filter import ContentBlocked, ContentFilter
from cloud.app.agent_runtime.safety.cost_governor import CostGovernor
from cloud.app.agent_runtime.safety.rate_limiter import RateLimiter
from cloud.app.agent_runtime.safety.verifier import Verifier
from cloud.app.agent_runtime.tools.metrics import agent_active_count, agent_requests_total
from cloud.app.agent_runtime.tools.runtime_tool_exec import ToolExecutor
from cloud.app.agent_runtime.tools.tool_bridge import ToolBridge
from shared.agent_identity import get_identity

logger = logging.getLogger(__name__)

_agent_exec_semaphore: threading.Semaphore | None = None
_agent_sem_lock = threading.Lock()


def _get_global_semaphore() -> threading.Semaphore:
    global _agent_exec_semaphore
    if _agent_exec_semaphore is None:
        with _agent_sem_lock:
            if _agent_exec_semaphore is None:
                max_concurrency = int(os.getenv("AGENT_MAX_CONCURRENCY", "2"))
                _agent_exec_semaphore = threading.Semaphore(max_concurrency)
    return _agent_exec_semaphore


class RuntimeCore:
    def __init__(self, agent_db, business_db, auth_header: str, agent_key: str = "", notifier: Notifier | None = None):
        self._agent_db, self._db, self._auth_header, self._agent_key, self._notifier = agent_db, business_db, auth_header, agent_key, notifier
        self._agent_identity = get_identity(agent_key) if agent_key else {}
        self._tool_registry = ToolBridge()
        self._tool_registry.register_default_tools()
        self._brain = Memory(agent_db)
        self._tool_registry.set_brain(self._brain)
        self._stats = {"total_runs": 0, "success_count": 0, "fail_count": 0}
        self._trace_id = str(uuid.uuid4())
        self._cost_tracker = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0, "total_cost": 0.0, "step_costs": []}
        self._loop_detector, self._checkpoint = LoopDetector(), RuntimeState(agent_db)
        self._approval, self._snapshot_manager, self._cost_governor = ApprovalManager(agent_db), StateSnapshot(agent_db), CostGovernor()
        self._scan_recoverable_checkpoints()
        self._planner = Planner()
        self._reflector = Reflector(plan_generator=self._planner)
        self._reflector_level, self._reflector_light_clean_streak, self._reflector_timeout_seconds = "balanced", 0, 2.0
        self._verifier = Verifier()
        self._trace_data: list[dict] = []
        self._rate_limiter = RateLimiter()
        self._circuit_breaker = CircuitBreaker()
        self._content_filter = ContentFilter()
        self._tracer = AgentTracer(self._agent_db)
        self._bulkhead = Bulkhead()
        self._vector_memory = VectorMemory()
        self._vector_memory.set_db(self._agent_db)
        self._brain.set_vector_memory(self._vector_memory)
        self._streamer: AgentStreamer | None = None
        self._rollback = RollbackHandler(self)
        self._tool_exec = ToolExecutor(self)
        self._engine = ExecutionEngine(self)
        self._llm = RuntimeLLM(core=self)
        self._core_tools = RuntimeCoreTools(self)
        self._helper = CompositionHelper(agent_db, self)
        self._state_machine = AgentStateMachine()
        AgentRegistry.load()

    def set_streamer(self, streamer: AgentStreamer):
        """设置事件流推送器。"""
        self._streamer = streamer

    def execute(self, goal: str, agent_key: str, context: dict | None = None, user_context: dict | None = None) -> RuntimeResult:
        """执行 Agent 任务，包含全局并发限流与舱壁隔离。

        user_context: dict含 user_id/role/permission_level，注入到 System Prompt 并影响 CostGovernor。
        """
        sem = _get_global_semaphore()
        acquired = sem.acquire(blocking=True, timeout=120.0)
        if not acquired:
            return RuntimeResult(
                status="rate_limited",
                result="Global agent concurrency limit reached. Please try again later.",
                iterations=0,
                tool_calls=0,
                logs=[],
            )
        try:
            if not self._bulkhead.acquire(agent_key):
                return RuntimeResult(
                    status="bulkhead_rejected",
                    result=f"Agent '{agent_key}' is busy, too many concurrent executions. Try again later.",
                    iterations=0,
                    tool_calls=0,
                    logs=[],
                )
            try:
                return self._execute_with_bulkhead(goal, agent_key, context, user_context)
            finally:
                self._bulkhead.release(agent_key)
        finally:
            sem.release()

    def _execute_with_bulkhead(self, goal: str, agent_key: str, context: dict | None = None, user_context: dict | None = None) -> RuntimeResult:
        trace_id = self._tracer.start_trace(agent_key, self._auth_header or "anonymous", {"goal": goal, "context": context})
        self._trace_id = trace_id
        agent_active_count.labels(agent_name=agent_key).inc()
        _start_time = time.monotonic()
        if self._streamer:
            self._streamer.stream(trace_id, "agent.start", {"agent_name": agent_key, "goal": goal, "context": context})
        # Dispatch to dedicated BaseAgent for shell-to-complete agents
        try:
            agent = AgentRegistry.get(agent_key)
            if agent and hasattr(agent, "execute_message"):
                session_id = (user_context or {}).get("session_id", "")
                user_id = (user_context or {}).get("user_id", "")
                result = asyncio.run(agent.execute_message(goal, session_id, user_id))
                if result is not None:
                    self._tracer.end_trace("success", result)
                    agent_requests_total.labels(agent_name=agent_key, status="success").inc()
                    agent_active_count.labels(agent_name=agent_key).dec()
                    if self._streamer:
                        self._streamer.stream(trace_id, "agent.end", {"status": "success", "result": result.get("reply", "")})
                    return RuntimeResult(
                        status="success",
                        result=result.get("reply", ""),
                        iterations=1,
                        tool_calls=0,
                        logs=[],
                    )
        except Exception:
            logger.exception("Dispatch failed for %s, falling back to L4 loop", agent_key)
        try:
            injection_reason = self._content_filter.check_input(goal)
            if injection_reason:
                result = RuntimeResult(
                    status="blocked",
                    result=f"Input blocked by safety policy: {injection_reason}",
                    iterations=0,
                    tool_calls=0,
                    logs=[],
                )
                self._tracer.end_trace("blocked", result.model_dump())
                agent_requests_total.labels(agent_name=agent_key, status="blocked").inc()
                agent_active_count.labels(agent_name=agent_key).dec()
                if self._notifier:
                    self._notifier.send(f"合规拦截: {agent_key} - {injection_reason}", priority="high")
                return result
            user_key = f"user_agent:{self._auth_header or 'anonymous'}"
            self._rate_limiter.check_or_raise(user_key)
            if user_context:
                self._cost_governor.set_user_context(user_context)
                context = dict(context or {})
                context["_user"] = user_context
            task_type = (context or {}).get("task_type", "")
            if task_type:
                self._cost_governor.set_task_type(task_type)
            memories = self._vector_memory.search(agent_key, goal, top_k=3)
            if memories:
                context = dict(context or {})
                context["_vector_memories"] = [{"key": m["key"], "content": m["content"], "score": m["score"]} for m in memories]
            self._state_machine.transition("PERCEIVING", agent_key=agent_key, context=context)
            result = self._engine._execute_impl(goal, agent_key, context, user_context)
            if result.status == "success" and result.result:
                try:
                    self._content_filter.filter_output(result.result)
                except ContentBlocked:
                    result = RuntimeResult(
                        status="blocked",
                        result="Output blocked by safety policy",
                        iterations=result.iterations,
                        tool_calls=result.tool_calls,
                        logs=result.logs,
                        metadata=result.metadata,
                    )
                    self._tracer.end_trace("blocked", result.model_dump())
                    return result
            if result.status == "success":
                self._state_machine.transition("IDLE", agent_key=agent_key)
            error_category = categorize_error(result.status)
            if result.status != "success":
                result.metadata["error_category"] = error_category
            self._tracer.end_trace(result.status, result.model_dump())
            agent_requests_total.labels(agent_name=agent_key, status=result.status).inc()
            agent_active_count.labels(agent_name=agent_key).dec()
            health_tracker = get_health_tracker()
            is_success = result.status in ("success", "completed")
            health_tracker.record_run(agent_key, is_success, result.result if not is_success else "")
            if self._streamer:
                self._streamer.stream(trace_id, "agent.end", {"status": result.status, "result": result.result})
            _duration = time.monotonic() - _start_time
            agent_call_duration_seconds.labels(agent_key=agent_key).observe(_duration)
            agent_calls_total.labels(agent_key=agent_key, status=result.status).inc()
            _cost = result.metadata.get("cost", {})
            _tokens = _cost.get("total_tokens", 0) if isinstance(_cost, dict) else 0
            _model = (context or {}).get("model", "unknown")
            if _tokens:
                agent_token_consumed_total.labels(agent_key=agent_key, model=_model).inc(_tokens)
            for log_entry in result.logs:
                _tool = log_entry.get("tool")
                if _tool:
                    agent_tool_calls_total.labels(agent_key=agent_key, tool_name=_tool).inc()
            return result
        except Exception:  # agent 完整生命周期，保持宽捕获
            self._state_machine.transition("ERROR", agent_key=agent_key)
            logger.exception("Runtime core异常")
            self._save_snapshot(agent_key, -1, [], [], context or {}, "failed")
            self._tracer.end_trace("error", {"error": "unhandled exception"})
            _duration = time.monotonic() - _start_time
            agent_call_duration_seconds.labels(agent_key=agent_key).observe(_duration)
            agent_calls_total.labels(agent_key=agent_key, status="error").inc()
            if self._streamer:
                self._streamer.stream(trace_id, "agent.error", {"error": "unhandled exception"})
            raise

    def resume(self, agent_key: str, goal: str, auth_header: str) -> RuntimeResult:
        """从检查点恢复 Agent 任务执行。"""
        checkpoint = self._load_checkpoint(agent_key, goal)
        if not checkpoint:
            return RuntimeResult(status="error", result="no checkpoint found", iterations=0, tool_calls=0, logs=[])
        # 状态一致性校验：检查 snapshot 中的 trace_id 是否在日志表中存在
        trace_id = checkpoint.get("trace_id", "")
        if trace_id:
            row = self._agent_db.execute(
                "SELECT COUNT(*) as cnt FROM agent_runtime_logs WHERE trace_id=?",
                (trace_id,),
            ).fetchone()
            if row and row["cnt"] == 0:
                return RuntimeResult(
                    status="inconsistent",
                    result=f"Snapshot state inconsistent with DB: trace_id={trace_id} not found in agent_runtime_logs",
                    iterations=0,
                    tool_calls=0,
                    logs=[],
                )
        approval = self._agent_db.execute(
            "SELECT * FROM agent_runtime_approvals WHERE trace_id=? AND status='approved' ORDER BY id DESC LIMIT 1",
            (checkpoint["trace_id"],),
        ).fetchone()
        if not approval:
            return RuntimeResult(status="awaiting_approval", result="still pending approval", iterations=0, tool_calls=0, logs=[])
        self._trace_id = checkpoint["trace_id"]
        self._auth_header = auth_header
        return self.execute(goal, agent_key, checkpoint.get("context"))

    def rollback(self, trace_id: str, target_step: int) -> dict:
        """rollback."""
        return self._rollback.rollback(trace_id, target_step)

    def get_status(self) -> dict:
        """获取运行时状态统计。"""
        return self._helper.get_status()

    @property
    def brain(self) -> Memory:
        """获取 Agent 脑状态存储器。"""
        return self._brain

    def list_recoverable(self) -> list[dict]:
        """列出所有可恢复的checkpoint（中断且未过期）。"""
        return self._helper.list_recoverable()

    def _scan_recoverable_checkpoints(self) -> None:
        """启动时扫描可恢复的checkpoint并记录日志。"""
        self._helper.scan_recoverable_checkpoints()

    def _save_snapshot(self, agent_id, step_id, plan, results, context, status="active"):
        """保存状态快照到 StateSnapshot 管理器。"""
        return self._snapshot_manager.save(agent_id, step_id, plan, results, context, status)

    def _estimate_token_count(self, messages: list[dict]) -> int:
        """估算消息 token 数，委托 RuntimeLLM。"""
        return RuntimeLLM._estimate_token_count(messages)

    def get_cost_usage(self) -> dict:
        """获取当前成本使用详情。"""
        return self._cost_governor.get_usage()

    def _notify(self, c, status):
        if self._notifier:
            elapsed = (datetime.now() - datetime.fromisoformat(c["started_at"])).total_seconds()
            self._notifier.notify(c["agent_key"], c["goal"], status, elapsed, self._cost_tracker)

    def _finish(self, c, status, result, step, iterations, success=None, metadata=None, notify=False, delete_checkpoint=False):
        self._helper._save_log(c["agent_key"], c["goal"], status, iterations, c["tool_calls"], c["logs"], c["started_at"])
        if notify:
            self._notify(c, status)
        if delete_checkpoint:
            self._checkpoint.delete(c["agent_key"], c["goal"])
        if success is not None:
            self._stats["total_runs"] += 1
            self._stats["success_count" if success else "fail_count"] += 1
        data = {"trace_id": self._trace_id, "cost": self.get_cost_usage()}
        data.update(metadata or {})
        return RuntimeResult(status=status, result=result, iterations=iterations, tool_calls=c["tool_calls"], logs=c["logs"], metadata=data)

    def _handle_budget_exceeded(self, c, step, step_start):
        c["logs"].append(
            self._core_tools._build_step_log(
                step,
                "budget_exceeded",
                result="cost budget exceeded",
                duration_ms=int((time.time() - step_start) * 1000),
            )
        )
        self._save_step_checkpoint(c, step, "budget_exceeded")
        return self._finish(c, "budget_exceeded", "cost budget exceeded", step, step + 1, False)

    def _call_ai(self, messages: list[dict], temperature: float, step: int = 0, force_level: int | None = None) -> dict:
        return self._llm._call_ai(messages, temperature, step, force_level)

    def _compress_messages(self, messages: list[dict]) -> list[dict]:
        return self._llm._compress_messages(messages)

    def _is_completed(self, decision) -> bool:
        return decision.action == "complete"


AgentRuntime = RuntimeCore
