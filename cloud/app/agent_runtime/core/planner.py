"""L4 Meta-Cognitive: PlanGenerator — generates and validates structured execution plans."""

import json
import logging
import re

from pydantic import BaseModel

from cloud.app.agent_runtime.core.reasoning_chain import ReasoningChain
from shared.config import settings as config_settings

logger = logging.getLogger(__name__)


class PlanStep(BaseModel):
    step_id: str
    description: str
    tool: str
    params_template: dict = {}
    expected_state: str = ""
    dependencies: list[str] = []
    fallback: str | None = None
    verification_criteria: list[str] = []


class Plan(BaseModel):
    goal: str
    steps: list[PlanStep]
    max_steps: int = 10
    completion_conditions: list[str] = []
    plan_confidence: float = 0.0


class Planner:
    """Generates structured plans via LLM and validates them against schema."""

    PLAN_SCHEMA_HINT = (
        "You are a plan generator. Output ONLY a JSON object matching this schema:\n"
        '{{"goal": "...", "steps": [{{"step_id": "s1", "description": "...", "tool": "tool_name", '
        '"params_template": {{...}}, "expected_state": "...", "dependencies": [], "fallback": null, '
        '"verification_criteria": ["..."]}}], "max_steps": 10, '
        '"completion_conditions": ["..."], "plan_confidence": 0.0}}\n'
        "Use tools from: {tools}. Context: {context}"
    )

    def __init__(self, llm_url: str = config_settings.ai_chat_url):
        self._llm_url = llm_url
        self._reasoning = ReasoningChain()

    def plan(self, goal: str, agent_key: str, context: dict | None = None) -> dict:
        """Produce a plan dict, optionally enriched with a reasoning chain for complex goals."""
        ctx = context or {}
        if self._is_complex(goal) or ctx.get("complex"):
            reason_steps = self._reasoning.chain_of_thought(goal, ctx)
            return {
                "step": -1,
                "action": "plan",
                "agent_key": agent_key,
                "goal": goal,
                "context": ctx,
                "reasoning_chain": reason_steps,
            }
        return {
            "step": -1,
            "action": "plan",
            "agent_key": agent_key,
            "goal": goal,
            "context": ctx,
        }

    def generate_plan(
        self,
        goal: str,
        tools: list[str],
        context: dict | None = None,
        execution_context: dict | None = None,
        complexity: bool | None = None,
    ) -> Plan:
        """Generate a validated Plan by calling the LLM and optionally applying chain-of-thought."""
        if complexity is None:
            complexity = self._is_complex(goal)

        if complexity:
            reason_steps = self._reasoning.chain_of_thought(goal, context or {})
            annotated_context = dict(context or {})
            annotated_context["reasoning_chain"] = reason_steps
            ctx = annotated_context
        else:
            ctx = context or {}

        prompt = self.PLAN_SCHEMA_HINT.format(tools=json.dumps(tools), context=json.dumps(ctx, ensure_ascii=False))
        messages = [{"role": "system", "content": prompt}, {"role": "user", "content": goal}]

        try:
            reply = self._call_llm(messages)
            raw = self._extract_json(reply)
            plan = Plan(**raw)
            if not plan.completion_conditions:
                plan.completion_conditions = ["Task goal achieved"]
            if not self.validate_plan(plan):
                logger.warning("Generated plan failed validation, returning empty plan")
                return Plan(goal=goal, steps=[], plan_confidence=0.0)
            return plan
        except (KeyError, TypeError, ValueError) as e:
            logger.error("Plan generation failed: %s", e)
            return Plan(goal=goal, steps=[], plan_confidence=0.0)

    def validate_plan(self, plan: Plan) -> bool:
        """Validate plan structure — schema checks, dependency integrity, tool presence."""
        if not plan.goal or not plan.steps:
            return False
        if plan.max_steps < 1 or plan.max_steps > 50:
            return False
        if not (0.0 <= plan.plan_confidence <= 1.0):
            return False

        step_ids = set()
        for step in plan.steps:
            if not step.step_id or not step.tool or not step.description:
                return False
            if step.step_id in step_ids:
                return False
            step_ids.add(step.step_id)

        for step in plan.steps:
            for dep in step.dependencies:
                if dep not in step_ids:
                    return False

        return True

    def _call_llm(self, messages: list[dict]) -> str:
        from cloud.app.agent_runtime.runtime_llm import RuntimeLLM

        llm = RuntimeLLM()
        llm._auth_header = ""
        try:
            result = llm._call_ai(messages, temperature=0.2, force_level=5)
            return result.get("reply", "")
        except (KeyError, TypeError, ValueError):
            logger.warning("Planner exception", exc_info=True)
            return ""

    @staticmethod
    def _is_complex(goal: str) -> bool:
        if len(goal) > 100:
            return True
        sentences = [s.strip() for s in re.split(r"[.?!]\s+", goal) if s.strip()]
        return len(sentences) > 1

    @staticmethod
    def _extract_json(raw: str) -> dict:
        raw = raw.strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[-1]
            raw = raw.rsplit("```", 1)[0]
        return json.loads(raw)


PlanGenerator = Planner
