"""Orchestrates multi-agent parallel dispatch and chaining."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from cloud.app.agent_runtime.core.models import RuntimeResult
from cloud.app.agent_runtime.lifecycle.orchestrator import Orchestrator

if TYPE_CHECKING:
    from cloud.app.agent_runtime.lifecycle.execution_loop import ExecutionEngine


def _identity_to_spec(agent) -> dict:
    identity = agent.identity
    return {
        "role_desc": f"你是{identity.role}，{identity.goal}",
        "allowed_tools": identity.allowed_tools,
        "max_iterations": 10,
        "default_temperature": identity.model_preference.temperature,
        "max_permission": identity.safety_profile.max_permission,
        "trigger_cron": None,
        "trigger_mode": identity.trigger_mode.value,
        "event_subscriptions": identity.event_subscriptions,
    }


class OrchestratedExecution:
    """Orchestrates multi-agent execution: registration, parallel dispatch, and chaining."""

    def __init__(self, engine: ExecutionEngine | None = None):
        self._engine = engine
        self._orchestrator = Orchestrator(runtime_core=engine)

    def register_agent(self, agent_key: str, agent: Any) -> None:
        """Register an agent with the underlying orchestrator."""
        self._orchestrator.register(agent_key, agent)

    def dispatch_to_agents(self, goal: str, agent_keys: list[str]) -> list[RuntimeResult]:
        """Dispatch a goal to multiple agents in parallel and return their results."""
        results = self._orchestrator.dispatch(goal, agent_keys)
        return [
            RuntimeResult(
                status=r.status,
                result=r.result,
                iterations=0,
                tool_calls=0,
                logs=[],
                metadata={"agent_key": r.agent_key, "confidence": r.confidence},
            )
            for r in results
        ]

    def chain_agents(self, goal: str, steps: list[str]) -> RuntimeResult:
        """Chain agents sequentially, where each agent's output feeds the next."""
        result = self._orchestrator.chain(goal, steps)
        return RuntimeResult(
            status=result.status,
            result=result.result,
            iterations=0,
            tool_calls=0,
            logs=[],
            metadata={"agent_key": result.agent_key, "confidence": result.confidence},
        )
