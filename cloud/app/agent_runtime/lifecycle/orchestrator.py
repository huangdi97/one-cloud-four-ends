"""Agent 间通信协调者 — 支持并行分发、链式调用、结果聚合。"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from cloud.app.agent_runtime.core.models import AgentResult

logger = logging.getLogger(__name__)


class Orchestrator:
    def __init__(self, runtime_core=None):
        self._runtime = runtime_core
        self._agents: dict[str, Any] = {}

    def register(self, agent_key: str, agent: Any) -> None:
        """Register an agent with the orchestrator."""
        self._agents[agent_key] = agent

    def dispatch(self, task: str, agent_keys: list[str], context: dict | None = None) -> list[AgentResult]:
        """Dispatch a task to multiple agents sequentially and return their results."""
        results: list[AgentResult] = []
        for key in agent_keys:
            try:
                if self._runtime:
                    result = self._runtime.execute(task, key, context)
                elif key in self._agents:
                    result = self._agents[key].execute(task, context)
                else:
                    result = AgentResult(agent_key=key, status="error", result=f"unknown agent: {key}")
                results.append(result if isinstance(result, AgentResult) else AgentResult(agent_key=key, status="success", result=str(result)))
            except Exception as e:
                logger.exception("dispatch failed for %s", key)
                results.append(AgentResult(agent_key=key, status="error", result=str(e)))
        return results

    async def dispatch_async(self, task: str, agent_keys: list[str], context: dict | None = None) -> list[AgentResult]:
        """Dispatch a task to multiple agents concurrently and return their results."""

        async def _run(key: str) -> AgentResult:
            try:
                if self._runtime:
                    result = self._runtime.execute(task, key, context)
                elif key in self._agents:
                    result = self._agents[key].execute(task, context)
                else:
                    return AgentResult(agent_key=key, status="error", result=f"unknown agent: {key}")
                return result if isinstance(result, AgentResult) else AgentResult(agent_key=key, status="success", result=str(result))
            except Exception as e:
                return AgentResult(agent_key=key, status="error", result=str(e))

        return await asyncio.gather(*[_run(key) for key in agent_keys])

    def chain(self, task: str, steps: list[str], context: dict | None = None) -> AgentResult:
        """Execute agents sequentially, feeding each agent's output as context to the next."""
        current_context = dict(context or {})
        last_result = ""
        for step_key in steps:
            if self._runtime:
                result = self._runtime.execute(task, step_key, current_context)
            elif step_key in self._agents:
                result = self._agents[step_key].execute(task, current_context)
            else:
                return AgentResult(agent_key=step_key, status="error", result=f"unknown agent: {step_key}")
            if result.status != "success":
                return AgentResult(agent_key=step_key, status=result.status, result=result.result)
            last_result = result.result
            current_context["previous_result"] = result.result
        return AgentResult(agent_key=steps[-1], status="success", result=last_result)

    def aggregate(self, results: list[AgentResult]) -> dict:
        """Aggregate multiple agent results into a summary dictionary."""
        return {
            "total": len(results),
            "success_count": sum(1 for r in results if r.status == "success"),
            "error_count": sum(1 for r in results if r.status == "error"),
            "results": [r.model_dump() for r in results],
        }
