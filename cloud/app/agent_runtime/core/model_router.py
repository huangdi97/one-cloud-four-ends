"""ModelRouter — 智能路由升级：task-complexity → model 映射 + cost-based fallback + latency budget。"""

import logging
import time
from enum import Enum

from cloud.app.agent_runtime.core.models import AgentTier, ModelPreference
from cloud.app.agent_runtime.runtime_llm import RuntimeLLM

logger = logging.getLogger(__name__)


class TaskComplexity(str, Enum):
    simple = "simple"
    medium = "medium"
    complex = "complex"


_COMPLEXITY_CONFIG = {
    TaskComplexity.simple: {
        "model": "deepseek-v4-flash",
        "tier": AgentTier.cloud_normal,
        "temperature": 0.1,
        "latency_budget_ms": 500,
        "cost_index": 1,
    },
    TaskComplexity.medium: {
        "model": "deepseek-v4-standard",
        "tier": AgentTier.cloud_normal,
        "temperature": 0.3,
        "latency_budget_ms": 2000,
        "cost_index": 2,
    },
    TaskComplexity.complex: {
        "model": "deepseek-v4-pro",
        "tier": AgentTier.cloud_agent,
        "temperature": 0.5,
        "latency_budget_ms": 5000,
        "cost_index": 3,
    },
}

_FALLBACK_BY_COST = sorted(_COMPLEXITY_CONFIG.values(), key=lambda x: x["cost_index"])


def _resolve_complexity(task_complexity: str | TaskComplexity) -> TaskComplexity:
    if isinstance(task_complexity, str):
        return TaskComplexity(task_complexity)
    return task_complexity


class ModelRouter:
    """包装 RuntimeLLM，按任务复杂度智能路由 model + cost-based fallback + latency budget。"""

    def __init__(self, preference: ModelPreference | None = None):
        self.preference = preference
        self._llm = RuntimeLLM()

    @property
    def temperature(self) -> float:
        """Return the temperature from the preference, defaulting to 0.7."""
        return self.preference.temperature if self.preference else 0.7

    def route(self, agent_key: str, task_complexity: str | TaskComplexity, budget_tokens: int | None = None) -> dict:
        """Resolve task complexity into a model/tier/latency configuration dict."""
        task_complexity = _resolve_complexity(task_complexity)
        config = _COMPLEXITY_CONFIG.get(task_complexity)
        if not config:
            raise ValueError(f"Unknown task_complexity: {task_complexity}")
        return {
            "agent_key": agent_key,
            "model": config["model"],
            "tier": config["tier"].value,
            "temperature": config["temperature"],
            "latency_budget_ms": config["latency_budget_ms"],
            "cost_index": config["cost_index"],
            "budget_tokens": budget_tokens,
        }

    def build_request_body(self, messages: list[dict], route_config: dict | None = None) -> dict:
        """Build the LLM request body with model and temperature from route config."""
        if route_config:
            model = route_config.get("model", "deepseek-v4-flash")
            temperature = route_config.get("temperature", 0.7)
        else:
            model = "deepseek-v4-flash"
            temperature = self.temperature
        return {
            "model": model,
            "messages": messages,
            "temperature": temperature,
        }

    def call(self, messages: list[dict], route_config: dict | None = None) -> dict:
        """Execute an LLM call with latency-budget and cost-based fallback logic."""
        body = self.build_request_body(messages, route_config)
        start = time.time()
        result = self._llm._raw_llm_call(body)
        elapsed_ms = (time.time() - start) * 1000
        if not route_config:
            return result
        latency_budget = route_config.get("latency_budget_ms", 0)
        if latency_budget and elapsed_ms > latency_budget:
            logger.warning(
                "Latency budget exceeded for %s: %.0fms > %dms, trying cost-based fallback",
                route_config.get("agent_key", "unknown"),
                elapsed_ms,
                latency_budget,
            )
            result = self._do_cost_fallback(messages, route_config)
        elif not result.get("success", True):
            logger.warning(
                "Primary model %s failed for %s, trying cost-based fallback",
                route_config.get("model", "unknown"),
                route_config.get("agent_key", "unknown"),
            )
            result = self._do_cost_fallback(messages, route_config)
        return result

    def _do_cost_fallback(self, messages: list[dict], failed_config: dict) -> dict:
        cost_index = failed_config.get("cost_index", 999)
        agent_key = failed_config.get("agent_key", "unknown")
        budget_tokens = failed_config.get("budget_tokens")
        for fallback in _FALLBACK_BY_COST:
            if fallback["cost_index"] >= cost_index:
                continue
            fb_complexity = TaskComplexity.simple
            for c, cfg in _COMPLEXITY_CONFIG.items():
                if cfg["cost_index"] == fallback["cost_index"]:
                    fb_complexity = c
                    break
            fb_config = self.route(agent_key, fb_complexity, budget_tokens)
            body = self.build_request_body(messages, fb_config)
            logger.info("Fallback: trying %s (cost_index=%d)", fallback["model"], fallback["cost_index"])
            result = self._llm._raw_llm_call(body)
            if result.get("success", True):
                return result
        return {
            "success": False,
            "error": "All fallback models failed",
            "model": failed_config.get("model", "unknown"),
        }
