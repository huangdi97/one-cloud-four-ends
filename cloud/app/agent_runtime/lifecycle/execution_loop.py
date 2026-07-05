"""Agent 执行循环 — 步骤级串行执行引擎，支持工具调用与结果收集。"""

import json
import logging
import signal
import time
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FuturesTimeoutError
from datetime import datetime

from cloud.app.agent_runtime.comm.telemetry import trace_step
from cloud.app.agent_runtime.core.agent_registry import AgentRegistry
from cloud.app.agent_runtime.core.agent_specs import AGENT_SPECS
from cloud.app.agent_runtime.core.models import RuntimeResult
from cloud.app.agent_runtime.lifecycle.dead_letter_queue import DeadLetterQueue
from cloud.app.agent_runtime.lifecycle.execution_failover import FailoverHandler
from cloud.app.agent_runtime.lifecycle.execution_orchestrated import OrchestratedExecution, _identity_to_spec
from cloud.app.agent_runtime.lifecycle.execution_step_handler import StepHandler
from cloud.app.agent_runtime.lifecycle.replan_handler import ReplanHandler
from cloud.app.agent_runtime.runtime_llm import AllModelsFailedError
from cloud.app.agent_runtime.safety.completion_verifier import CompletionVerifier
from cloud.app.agent_runtime.safety.pii_redactor import PIIRedactionFilter
from cloud.app.agent_runtime.safety.schema_validator import OutputSchemaValidator
from cloud.app.agent_runtime.tools import metrics as agent_metrics

logger = logging.getLogger(__name__)
logger.addFilter(PIIRedactionFilter())


class ExecutionEngine:
    MAX_LLM_CALLS = 50
    MAX_EXECUTION_SECONDS = 600
    STEP_TIMEOUT_SECONDS = 60
    _shutdown_flag = False

    def __init__(self, host, enable_orchestrator: bool = False):
        self._host = host
        self._executor = ThreadPoolExecutor(max_workers=4)
        self._dead_letter_queue = DeadLetterQueue()
        self._timeout_count = 0
        self._replan_handler = ReplanHandler(self._host)
        self._completion_verifier = CompletionVerifier(self._host)
        self._step_handler = StepHandler(self)
        self._failover_handler = FailoverHandler(self)
        self._orchestrated = OrchestratedExecution(engine=self) if enable_orchestrator else None
        signal.signal(signal.SIGTERM, self._signal_handler)
        signal.signal(signal.SIGINT, self._signal_handler)

    @property
    def orchestrator(self) -> OrchestratedExecution | None:
        """Return the orchestrated execution instance, if enabled."""
        return self._orchestrated

    def _signal_handler(self, sig, frame):
        logger.warning("收到信号 %s，保存 checkpoint 后关闭", sig)
        self.__class__._shutdown_flag = True
        self._save_checkpoint_on_shutdown()

    def _save_checkpoint_on_shutdown(self):
        if not hasattr(self._host, "_trace_id") or not self._host._trace_id:
            return
        try:
            state = {
                "trace_id": self._host._trace_id,
                "step": -1,
                "messages": [],
                "logs": [],
                "tool_calls_so_far": 0,
                "goal": "",
                "agent_key": "",
                "context": {},
                "status": "interrupted",
            }
            self._host._helper._save_checkpoint("", "", state)
            logger.info("Checkpoint 已保存 (trace=%s)", self._host._trace_id)
        except Exception:
            logger.exception("保存中断 checkpoint 失败")

    def _load_approved_tool(self, agent_key, goal, checkpoint):
        if not checkpoint:
            return None, None
        app = self._host._agent_db.execute(
            "SELECT tool, params FROM agent_runtime_approvals WHERE agent_key=? AND goal=? AND status='approved' ORDER BY id DESC LIMIT 1",
            (agent_key, goal),
        ).fetchone()
        return (app["tool"], json.loads(app["params"]) if app["params"] else {}) if app else (None, None)

    def _new_context(self, goal, agent_key, context, spec, user_context=None):
        hot_reloader = getattr(self, "_prompt_hot_reloader", None)
        if hot_reloader:
            hot_spec = hot_reloader.get_spec(agent_key)
            if hot_spec:
                spec = {**spec, **hot_spec}
        checkpoint = self._host._helper._load_checkpoint(agent_key, goal)
        plan = None
        plan_available = False
        if checkpoint:
            messages = checkpoint["messages"]
            logs = checkpoint["logs"]
            tool_calls = checkpoint["tool_calls_so_far"]
            start_step = checkpoint["step"] + 1
        else:
            tools_list = spec.get("allowed_tools", [])
            if not tools_list:
                tools_list = [t["name"] for t in self._host._tool_registry.list_tools() if t.get("name")]
            plan = self._host._planner.generate_plan(goal, tools_list, context)
            plan_available = plan is not None and bool(plan.steps) and plan.plan_confidence > 0
            plan_section = ""
            if plan_available:
                plan_lines = ["你的计划："]
                for i, step in enumerate(plan.steps, 1):
                    plan_lines.append(f"步骤{i}: {step.description} — 工具：{step.tool}")
                plan_lines.append("")
                plan_lines.append(f"当前进度：第 0 步 / 共 {len(plan.steps)} 步")
                plan_lines.append(f"完成条件：{json.dumps(plan.completion_conditions, ensure_ascii=False)}")
                plan_section = "\n".join(plan_lines) + "\n\n"
            user_section = ""
            if user_context:
                user_section = (
                    f"用户信息：\n"
                    f"  user_id: {user_context.get('user_id', 'unknown')}\n"
                    f"  role: {user_context.get('role', 'unknown')}\n"
                    f"  permission_level: {user_context.get('permission_level', 'unknown')}\n\n"
                )
            prompt = (
                f"你是一个{spec['role_desc']}\n\n"
                f"{plan_section}"
                f"{user_section}"
                f"可用工具（JSON格式）：{json.dumps(self._host._tool_registry.list_tools(), ensure_ascii=False)}\n\n"
                f"当前上下文：{json.dumps(context or {}, ensure_ascii=False)}\n\n"
                '请回复JSON格式：{"action": "call_tool"|"complete"|"error", "tool": "tool_name", "params": {...}, "reasoning": "..."}'
            )
            messages, logs, tool_calls, start_step = [{"role": "system", "content": prompt}, {"role": "user", "content": goal}], [], 0, 0
        approved_tool, approved_params = self._load_approved_tool(agent_key, goal, checkpoint)
        logs.append(self._host._planner.plan(goal, agent_key, context))
        return {
            "goal": goal,
            "agent_key": agent_key,
            "context": context,
            "messages": messages,
            "logs": logs,
            "tool_calls": tool_calls,
            "start_step": start_step,
            "started_at": datetime.now().isoformat(),
            "approved_tool": approved_tool,
            "approved_params": approved_params,
            "_plan": plan,
            "_plan_step_index": 0 if plan_available else -1,
        }

    def _execute_impl(self, goal: str, agent_key: str, context: dict | None = None, user_context: dict | None = None) -> RuntimeResult:
        agent = AgentRegistry.get(agent_key)
        if agent is not None:
            spec = _identity_to_spec(agent)
        else:
            spec = AGENT_SPECS.get(agent_key)
        if spec is None:
            return RuntimeResult(status="error", result=f"unknown agent_key: {agent_key}", iterations=0, tool_calls=0, logs=[])
        c, max_iter = self._new_context(goal, agent_key, context, spec, user_context), min(spec["max_iterations"], 15)
        start_time = time.time()
        llm_call_count = 0
        for step in range(c["start_step"], max_iter):
            if self.__class__._shutdown_flag:
                return RuntimeResult(
                    status="interrupted",
                    result="execution interrupted by shutdown signal",
                    iterations=step - c["start_step"],
                    tool_calls=c["tool_calls"],
                    logs=c["logs"],
                )
            if time.time() - start_time > self.MAX_EXECUTION_SECONDS:
                return RuntimeResult(
                    status="timeout",
                    result="execution timeout",
                    iterations=step - c["start_step"],
                    tool_calls=c["tool_calls"],
                    logs=c["logs"],
                )
            c["messages"], step_start = self._host._compress_messages(c["messages"]), time.time()
            if c["approved_tool"] and step == c["start_step"]:
                self._step_handler._run_approved_tool(c, step)
                c["approved_tool"] = None
                continue
            if not self._host._core_tools._check_budget(c["messages"]):
                return self._handle_budget_exceeded(c, step, step_start)
            replan_deviation = c.get("_plan_deviation_count", 0)
            if replan_deviation >= 3 and c.get("_plan"):
                replan_count = c.get("_replan_count", 0)
                if replan_count < 2:
                    self._replan_handler.trigger(c)
                else:
                    c["_plan_deviation_count"] = 0
            if c.get("_plan") and c["_plan"].steps:
                _plan = c["_plan"]
                _total = len(_plan.steps)
                _completed = c.get("_plan_step_index", 0)
                _next_desc = _plan.steps[_completed].description if _completed < _total else "全部完成"
                _last_output = ""
                for _msg in reversed(c["messages"]):
                    if isinstance(_msg.get("content"), str) and _msg["content"].startswith("工具返回："):
                        _last_output = _msg["content"][:100]
                        break
                c["messages"].append(
                    {
                        "role": "user",
                        "content": (f"当前进度：已完成步骤 {_completed}/{_total}\n上一步结果：{_last_output}\n计划中下一步：{_next_desc}"),
                    }
                )
            try:
                streamer = getattr(self, "_streamer", None)
                trace_id = getattr(self, "_trace_id", None)
                if streamer and trace_id:
                    streamer.stream(trace_id, "agent.llm_call", {"step": step, "agent": c["agent_key"]})
                future = self._executor.submit(self._host._call_ai, c["messages"], spec["default_temperature"], step, None)
                try:
                    ai_resp = future.result(timeout=self.STEP_TIMEOUT_SECONDS)
                except FuturesTimeoutError:
                    self._timeout_count += 1
                    with trace_step("llm_call_timeout", {"step": step, "agent": c["agent_key"]}):
                        pass
                    logger.warning("Step %d timed out after %ds for agent %s", step, self.STEP_TIMEOUT_SECONDS, c["agent_key"])
                    return RuntimeResult(
                        status="timeout",
                        result="Agent step timed out",
                        iterations=step - c["start_step"],
                        tool_calls=c["tool_calls"],
                        logs=c["logs"],
                    )
                llm_call_count += 1
                if llm_call_count > self.MAX_LLM_CALLS:
                    return RuntimeResult(
                        status="llm_limit_exceeded",
                        result="LLM call limit exceeded",
                        iterations=step - c["start_step"],
                        tool_calls=c["tool_calls"],
                        logs=c["logs"],
                    )
                if streamer and trace_id:
                    streamer.stream(trace_id, "agent.llm_result", {"step": step, "reply_preview": ai_resp.get("reply", "")[:200]})
                validator = OutputSchemaValidator()
                try:
                    parsed = json.loads(ai_resp.get("reply", "{}"))
                    passed, errors = validator.validate(c["agent_key"], parsed)
                    if not passed:
                        corrected = validator.coerce(c["agent_key"], parsed)
                        ai_resp["reply"] = json.dumps(corrected, ensure_ascii=False)
                        logger.warning("Schema validation for %s failed: %s; coerced output", c["agent_key"], errors)
                except (json.JSONDecodeError, TypeError):
                    logger.warning("执行循环异常", exc_info=True)
                self._host._core_tools._accumulate_cost(ai_resp, step)
            except AllModelsFailedError as exc:
                logger.error("All LLM providers failed for %s: %s", c["agent_key"], exc)
                return RuntimeResult(
                    status="llm_failed",
                    result=f"All LLM providers failed: {exc}",
                    iterations=step - c["start_step"],
                    tool_calls=c["tool_calls"],
                    logs=c["logs"],
                )
            except (KeyError, TypeError, ValueError) as exc:
                if self._host._tool_exec._handle_step_error(c, step, str(exc), duration_ms=int((time.time() - step_start) * 1000)):
                    continue
                raise
            if not self._host._core_tools._check_budget():
                return self._host._handle_budget_exceeded(c, step, step_start)
            result = self._step_handler._handle_step_result(c, step, ai_resp, int((time.time() - step_start) * 1000), spec)
            if isinstance(result, RuntimeResult):
                return result
        return self._host._tool_exec._handle_max_iterations(c, max_iter)

    def execute(self, goal: str, agent_key: str, context: dict | None = None) -> RuntimeResult:
        """Execute an agent goal with full lifecycle: LLM calls, tools, failover, and degradation."""
        start_ts = time.time()
        degradation_log = None
        try:
            result = self._execute_impl(goal, agent_key, context)
            duration = time.time() - start_ts
            status = "success" if result.status == "completed" else result.status
            agent_metrics.agent_requests_total.labels(agent_name=agent_key, status=status).inc()
            agent_metrics.agent_llm_duration.labels(agent_name=agent_key, model="all").observe(duration)
            return result
        except AllModelsFailedError as exc:
            logger.error("LLM degraded for %s: %s", agent_key, exc)
            degradation_log = {
                "agent_key": agent_key,
                "reason": f"LLM failure: {exc}",
                "level": "L2",
                "timestamp": time.time(),
            }
            agent = AgentRegistry.get(agent_key)
            fallback_l2 = agent.identity.fallback_l2 if agent else None
            if fallback_l2:
                logger.info("L2 fallback for %s: %s", agent_key, fallback_l2)
                self._log_degradation(agent_key, "all_llm_providers_failed", "L2")
                return RuntimeResult(
                    status="degraded_l2",
                    result=fallback_l2,
                    iterations=0,
                    tool_calls=0,
                    logs=[{"type": "degradation", "agent": agent_key, "from": "L1", "to": "L2", "fallback": fallback_l2}],
                    metadata={"degradation": degradation_log},
                )
            logger.info("L3 silent skip for %s: no fallback_l2 configured", agent_key)
            self._log_degradation(agent_key, "all_llm_providers_failed", "L3")
            return RuntimeResult(
                status="skipped",
                result=f"{agent_key} temporarily unavailable (L3 skip)",
                iterations=0,
                tool_calls=0,
                logs=[{"type": "degradation", "agent": agent_key, "from": "L1", "to": "L3"}],
                metadata={"degradation": degradation_log},
            )
        except (KeyError, TypeError, ValueError, ConnectionError, TimeoutError) as exc:
            logger.error("Tool degraded for %s: %s", agent_key, exc)
            result, handled = self._failover_handler.handle_failover(agent_key, goal, context, exc, "tool call failure")
            if handled:
                return result
            self._log_degradation(agent_key, f"tool_failure: {exc}", "L2")
            return RuntimeResult(
                status="degraded",
                result=f"Tool {agent_key} unavailable",
                iterations=0,
                tool_calls=0,
                logs=[],
            )
        except Exception as exc:
            logger.error("Unexpected execution error for %s: %s", agent_key, exc, exc_info=True)
            result, handled = self._failover_handler.handle_failover(agent_key, goal, context, exc, "unexpected error")
            if handled:
                return result
            self._log_degradation(agent_key, f"unexpected: {exc}", "L3")
            return RuntimeResult(
                status="error",
                result=f"Execution failed: {exc}",
                iterations=0,
                tool_calls=0,
                logs=[],
            )

    @staticmethod
    def _log_degradation(agent_key: str, reason: str, level: str) -> None:
        logger.warning("Degradation: agent=%s reason=%s level=%s", agent_key, reason, level)
        agent_metrics.agent_degradation_total.labels(agent_key=agent_key, level=level).inc()
