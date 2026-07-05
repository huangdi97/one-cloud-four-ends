"""AnalysisAgent — L4 Harness 驱动异常根因分析 Agent，为 anomaly_analysis 提供专用执行逻辑。

集成模式发现、假设生成、因果推断与自然语言叙事，输出结构化的根因分析结果。
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any, Optional

from cloud.app.agent_runtime.core.models import AgentIdentity
from cloud.app.agents.base_agent import AgentContext, AgentResponse, BaseAgent
from cloud.app.analysis import (
    Hypothesis,
    Hypothesizer,
    Narrative,
    Narrator,
    PatternDiscovery,
    RelatedPattern,
)
from cloud.app.analysis.verifier import VerificationResult
from cloud.app.services.brain.causal_service import CausalService

logger = logging.getLogger(__name__)

__all__ = ["AnalysisResult", "AnalysisAgent"]


@dataclass
class AnalysisResult:
    """异常根因分析结果，包含根因、置信度、关联模式、严重级别与建议行动。"""

    root_cause: str = ""
    confidence: float = 0.0
    related_patterns: list[RelatedPattern] = field(default_factory=list)
    severity: str = "medium"
    suggested_actions: list[str] = field(default_factory=list)


class AnalysisAgent(BaseAgent):
    """异常根因分析 Agent，集成模式发现、假设生成、因果推断与叙事报告管线。

    优先通过 RuntimeCore 走完整 L4 循环（规划→执行→验证→反思），
    降级时直接调用本地分析管线。
    """

    def __init__(
        self,
        identity: AgentIdentity,
        pattern_discovery: PatternDiscovery | None = None,
        hypothesizer: Optional[Hypothesizer] = None,
        narrator: Narrator | None = None,
        causal_service: CausalService | None = None,
        runtime_core: Optional[Any] = None,
    ) -> None:
        self._identity = identity
        self._pattern_discovery = pattern_discovery or PatternDiscovery()
        self._hypothesizer = hypothesizer or Hypothesizer()
        self._narrator = narrator or Narrator()
        self._causal_service = causal_service or CausalService()
        if runtime_core is not None:
            self._runtime_core = runtime_core
        else:
            from cloud.app.agent_runtime.core.runtime_core import RuntimeCore

            self._runtime_core = RuntimeCore()

    @staticmethod
    def _build_fallback_result():
        return {
            "root_cause": "无法解析分析目标",
            "confidence": 0.0,
            "related_patterns": [],
            "severity": "unknown",
            "suggested_actions": ["请提供有效的异常事件数据"],
        }

    @staticmethod
    def _build_analysis_output(result):
        return {
            "root_cause": result.root_cause,
            "confidence": result.confidence,
            "related_patterns": [
                {
                    "pattern_id": p.pattern_id,
                    "anomaly_id": p.anomaly_id,
                    "similarity": p.similarity,
                    "matched_dimensions": p.matched_dimensions,
                    "escalation": p.escalation,
                    "summary": p.summary,
                }
                for p in result.related_patterns
            ],
            "severity": result.severity,
            "suggested_actions": result.suggested_actions,
        }

    async def execute(self, context: AgentContext) -> AgentResponse:
        """执行异常根因分析，优先通过 RuntimeCore 走 L4 循环，降级走直接 LLM 管线。"""
        agent_id = self._identity.key
        agent_name = self._identity.name
        logger.info("AnalysisAgent(%s) execute: %s", agent_id, context.message[:64])

        if self._runtime_core is not None:
            return await self._l4_execute(agent_id, agent_name, context)

        return await self._direct_llm_execute(agent_id, agent_name, context)

    async def _l4_execute(self, agent_id: str, agent_name: str, context: AgentContext) -> AgentResponse:
        from cloud.app.agent_runtime.reflection.reflector import Reflector
        from cloud.app.agent_runtime.safety.verifier import Verifier

        plan = self._runtime_core.plan(
            purpose="anomaly_analysis",
            context={"message": context.message, "agent_id": agent_id, "agent_name": agent_name},
        )
        if not plan.steps:
            logger.warning("L4 planner returned empty plan for anomaly_analysis, falling back")
            return await self._direct_llm_execute(agent_id, agent_name, context)

        verifier = Verifier()
        reflector = Reflector()

        for step in plan.steps:
            result = self._runtime_core.execute_step(step)
            vr = verifier.verify_step(step, result, agent_key=agent_id)
            if vr.confidence < 0.6:
                logger.info(
                    "L4 step %s confidence=%.2f < 0.6, triggering reflector",
                    step.step_id,
                    vr.confidence,
                )
                reflection = reflector.reflect(
                    task=step.description,
                    original_plan=plan,
                    analysis=None,
                    context={"step_result": result, "verification": vr.model_dump()},
                )
                if reflection and reflection.plan and reflection.plan.steps:
                    logger.info("Reflector proposed %d replacement steps", len(reflection.plan.steps))

        return AgentResponse(
            reply=json.dumps(
                {
                    "root_cause": "L4 Harness 执行完成",
                    "confidence": 1.0,
                    "related_patterns": [],
                    "severity": "medium",
                    "suggested_actions": [f"L4 Harness 执行完成，步数: {len(plan.steps)}"],
                },
                ensure_ascii=False,
            ),
            actions=[
                {
                    "agent": agent_name,
                    "severity": "medium",
                    "confidence": 1.0,
                },
            ],
            memory_updates=[],
        )

    async def _direct_llm_execute(self, agent_id: str, agent_name: str, context: AgentContext) -> AgentResponse:
        """降级路径：直接调用本地分析管线执行异常根因分析。"""
        anomaly_event = self._parse_anomaly_event(context)
        if not anomaly_event:
            return AgentResponse(reply=json.dumps(self._build_fallback_result(), ensure_ascii=False))

        related_patterns = self._run_pattern_discovery(anomaly_event)
        hypotheses = self._run_hypothesis_generation(anomaly_event)
        causal_result = self._run_causal_inference(anomaly_event, hypotheses)
        narrative = self._run_narration(anomaly_event, hypotheses, causal_result)

        result = AnalysisResult(
            root_cause=narrative.cause if narrative else "无法确定根因",
            confidence=causal_result.get("confidence", 0.0),
            related_patterns=related_patterns,
            severity=self._assess_severity(anomaly_event, causal_result),
            suggested_actions=self._build_suggested_actions(narrative, causal_result),
        )
        return AgentResponse(
            reply=json.dumps(self._build_analysis_output(result), ensure_ascii=False),
            actions=[
                {
                    "agent": agent_name,
                    "severity": result.severity,
                    "confidence": result.confidence,
                },
            ],
            memory_updates=[],
        )

    def capabilities(self) -> list[str]:
        """返回 identity 允许的工具列表。"""
        return list(self._identity.allowed_tools)

    def _parse_anomaly_event(self, context: AgentContext) -> dict[str, Any] | None:
        """从 context 中解析异常事件数据。

        Args:
            context: Agent 执行上下文。

        Returns:
            解析后的异常事件字典，解析失败返回 None。
        """
        message = context.message
        try:
            data = json.loads(message)
            if isinstance(data, dict):
                return data
        except (json.JSONDecodeError, TypeError):
            pass
        if message.strip():
            return {"raw_message": message.strip()}
        return None

    def _run_pattern_discovery(
        self,
        anomaly_event: dict[str, Any],
    ) -> list[RelatedPattern]:
        """调用 pattern_discovery 发现历史相似异常模式。

        Args:
            anomaly_event: 当前异常事件数据。

        Returns:
            关联模式列表，按相似度降序排列。
        """
        try:
            return self._pattern_discovery.discover(anomaly_event)
        except Exception:
            logger.exception("Pattern discovery failed")
            return []

    def _run_hypothesis_generation(
        self,
        anomaly_event: dict[str, Any],
    ) -> list[Hypothesis]:
        """调用 hypothesizer 生成候选根因假设。

        Args:
            anomaly_event: 当前异常事件数据。

        Returns:
            按先验置信度降序排列的候选假设列表。
        """
        try:
            return self._hypothesizer.generate_hypotheses(anomaly_event)
        except Exception:
            logger.exception("Hypothesis generation failed")
            return []

    def _run_causal_inference(
        self,
        anomaly_event: dict[str, Any],
        hypotheses: list[Hypothesis],
    ) -> dict[str, Any]:
        """调用 causal_service 对最佳假设执行因果推断。

        Args:
            anomaly_event: 当前异常事件数据。
            hypotheses: 候选假设列表。

        Returns:
            因果推断结果，含 feature_weights、confidence 等。
        """
        best = hypotheses[0] if hypotheses else None
        if best is None:
            return {"confidence": 0.0, "method": "none", "target": "unknown"}
        features = self._extract_features(anomaly_event, best)
        try:
            return self._causal_service.causal_infer(
                features=features,
                target=best.root_cause_category,
                method="linear",
            )
        except Exception:
            logger.exception("Causal inference failed")
            return {"confidence": best.prior_confidence, "method": "fallback", "target": best.root_cause_category}

    def _extract_features(
        self,
        anomaly_event: dict[str, Any],
        hypothesis: Hypothesis,
    ) -> dict[str, float]:
        """从异常事件和假设中提取因果推断所需的特征。

        Args:
            anomaly_event: 当前异常事件数据。
            hypothesis: 选中的候选假设。

        Returns:
            特征名到权重的映射。
        """
        features: dict[str, float] = {}
        evidence = anomaly_event.get("evidence") if isinstance(anomaly_event.get("evidence"), dict) else {}
        for key in hypothesis.required_data:
            if key in anomaly_event:
                features[key] = 1.0
            elif key in evidence:
                features[key] = 0.8
            else:
                features[key] = 0.2
        if not features:
            features = {"default_evidence": 0.5}
        return features

    def _run_narration(
        self,
        anomaly_event: dict[str, Any],
        hypotheses: list[Hypothesis],
        causal_result: dict[str, Any],
    ) -> Narrative | None:
        """调用 narrator 生成分析叙事报告。

        Args:
            anomaly_event: 当前异常事件数据。
            hypotheses: 候选假设列表。
            causal_result: 因果推断结果。

        Returns:
            包含 discovery、cause、recommendation 三部分的叙事报告。
        """
        best = hypotheses[0] if hypotheses else None
        if best is None:
            return None
        verification_result = VerificationResult(
            anomaly_id=best.anomaly_id,
            root_cause=best.description,
            root_cause_category=best.root_cause_category,
            confidence=causal_result.get("confidence", best.prior_confidence),
            converged=causal_result.get("confidence", 0.0) >= 0.8,
            rounds=1,
            verified_hypothesis=best,
            evidence=[],
            recommendation=self._recommendation(best.root_cause_category),
        )
        try:
            return self._narrator.generate_narrative(verification_result)
        except Exception:
            logger.exception("Narrative generation failed")
            return None

    def _assess_severity(
        self,
        anomaly_event: dict[str, Any],
        causal_result: dict[str, Any],
    ) -> str:
        """评估异常严重级别。

        Args:
            anomaly_event: 当前异常事件数据。
            causal_result: 因果推断结果。

        Returns:
            严重级别：critical / high / medium / low。
        """
        level = anomaly_event.get("level", anomaly_event.get("severity", ""))
        if level in ("critical", "high", "medium", "low"):
            return level
        confidence = causal_result.get("confidence", 0.0)
        if confidence >= 0.8:
            return "high"
        if confidence >= 0.6:
            return "medium"
        if confidence >= 0.3:
            return "low"
        return "unknown"

    def _recommendation(self, category: str) -> str:
        """根据根因类别返回建议行动。

        Args:
            category: 根因分类。

        Returns:
            对应的建议行动文本。
        """
        mapping = {
            "expense_visit_mismatch": "暂停相关费用结算，复核发票、拜访、流向三类原始凭证后再恢复。",
            "distributor_concentration": "将异常从单代表升级为经销商专项核查，抽检同经销商下其他代表和订单。",
            "visit_execution_gap": "要求补充HCP确认和GPS轨迹证明，并复盘该代表近期拜访计划执行质量。",
            "data_quality_issue": "先冻结自动处罚动作，完成源系统去重、补字段和同步延迟排查。",
            "policy_rule_breach": "按命中规则启动合规处置，并保留审计链供人工复核。",
        }
        return mapping.get(category, "补齐关键证据后由合规负责人复核。")

    def _build_suggested_actions(
        self,
        narrative: Narrative | None,
        causal_result: dict[str, Any],
    ) -> list[str]:
        """从叙事报告和因果推断结果生成建议行动列表。

        Args:
            narrative: 分析叙事报告。
            causal_result: 因果推断结果。

        Returns:
            建议行动列表。
        """
        actions: list[str] = []
        if narrative and narrative.recommendation:
            actions.append(narrative.recommendation)
        if causal_result.get("method") == "none":
            actions.append("补充更多证据源后重新分析。")
        if not actions:
            actions.append("补齐关键证据后由合规负责人复核。")
        return actions
