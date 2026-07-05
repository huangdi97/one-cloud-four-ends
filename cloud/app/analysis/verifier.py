"""Hypothesis verification loop for anomaly root-cause analysis."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Optional

from .hypothesizer import Hypothesis, Hypothesizer

ToolRunner = Callable[[str, dict[str, Any]], dict[str, Any]]


@dataclass
class VerificationResult:
    """Final result of a hypothesis verification loop."""

    anomaly_id: str
    root_cause: str
    root_cause_category: str
    confidence: float
    converged: bool
    rounds: int
    verified_hypothesis: Hypothesis | None
    evidence: list[dict[str, Any]] = field(default_factory=list)
    rejected_hypotheses: list[dict[str, Any]] = field(default_factory=list)
    recommendation: str = ""


class HypothesisVerifier:
    """Verify, reject, and refine anomaly hypotheses until convergence."""

    def __init__(
        self,
        tool_runner: ToolRunner | None = None,
        hypothesizer: Optional[Hypothesizer] = None,
        confidence_threshold: float = 0.8,
        max_rounds: int = 3,
    ):
        self._tool_runner = tool_runner
        self._hypothesizer = hypothesizer or Hypothesizer()
        self._confidence_threshold = confidence_threshold
        self._max_rounds = max(1, max_rounds)

    def verify(self, hypothesis: Hypothesis) -> VerificationResult:
        """Verify one hypothesis and refine alternatives when it is disproved.

        Args:
            hypothesis: Initial hypothesis to test.

        Returns:
            Verification result with one final root-cause conclusion.
        """
        queue = [hypothesis]
        seen = {hypothesis.hypothesis_id}
        best: tuple[Hypothesis, float, list[dict[str, Any]]] | None = None
        rejected: list[dict[str, Any]] = []
        rounds = 0

        while queue and rounds < self._max_rounds:
            current = queue.pop(0)
            rounds += 1
            evidence = self._collect_evidence(current)
            confidence = self._score(current, evidence)
            if best is None or confidence > best[1]:
                best = (current, confidence, evidence)

            if confidence >= self._confidence_threshold:
                return self._result(current, confidence, True, rounds, evidence, rejected)

            rejected.append(
                {
                    "hypothesis_id": current.hypothesis_id,
                    "description": current.description,
                    "confidence": round(confidence, 2),
                    "reason": "关键证据不足，未达到80%置信度收敛条件。",
                }
            )
            for next_hypothesis in self._hypothesizer.generate_hypotheses(current.anomaly_event):
                if next_hypothesis.hypothesis_id not in seen:
                    seen.add(next_hypothesis.hypothesis_id)
                    queue.append(next_hypothesis)

        if best is None:
            return VerificationResult(
                anomaly_id=hypothesis.anomaly_id,
                root_cause="未能获得足够证据形成根因结论。",
                root_cause_category="unknown",
                confidence=0.0,
                converged=False,
                rounds=rounds,
                verified_hypothesis=None,
                rejected_hypotheses=rejected,
                recommendation="补齐费用、拜访、流向和审计日志后重新验证。",
            )
        return self._result(best[0], best[1], best[1] >= self._confidence_threshold, rounds, best[2], rejected)

    def verify_anomaly(self, anomaly_event: Any) -> VerificationResult:
        """Generate hypotheses for one anomaly and verify them."""
        hypotheses = self._hypothesizer.generate_hypotheses(anomaly_event)
        return self.verify(hypotheses[0])

    def _collect_evidence(self, hypothesis: Hypothesis) -> list[dict[str, Any]]:
        params = {
            "anomaly_id": hypothesis.anomaly_id,
            "hypothesis_id": hypothesis.hypothesis_id,
            "required_data": hypothesis.required_data,
            "category": hypothesis.root_cause_category,
            "anomaly_event": hypothesis.anomaly_event,
        }
        collected = [
            self._call_tool("collect_related_data", params),
            self._call_tool("run_pattern_analysis", params),
            self._call_tool("run_causal_inference", params),
        ]
        return [item for item in collected if item]

    def _call_tool(self, tool_name: str, params: dict[str, Any]) -> dict[str, Any]:
        if self._tool_runner:
            result = self._tool_runner(tool_name, params)
            return result if isinstance(result, dict) else {"source": tool_name, "value": result}
        return self._default_tool_result(tool_name, params)

    def _default_tool_result(self, tool_name: str, params: dict[str, Any]) -> dict[str, Any]:
        event = params["anomaly_event"]
        evidence = event.get("evidence") if isinstance(event.get("evidence"), dict) else {}
        category = params["category"]
        score = _category_score(category, event, evidence)
        source = f"{tool_name}:{params['anomaly_id']}"
        if tool_name == "collect_related_data":
            return {
                "source": source,
                "confidence": score,
                "supports": score >= 0.65,
                "data": {key: event.get(key) for key in ("agent_id", "rep_id", "dealer_id", "dealer", "level", "status") if event.get(key)},
                "evidence": evidence,
            }
        if tool_name == "run_pattern_analysis":
            related_count = _related_count(event, evidence)
            pattern_bonus = 0.1 if related_count else 0.0
            return {
                "source": source,
                "confidence": min(0.95, score + pattern_bonus),
                "supports": score + pattern_bonus >= 0.7,
                "related_pattern_count": related_count,
            }
        return {
            "source": source,
            "confidence": min(0.95, score + 0.04),
            "supports": score >= 0.62,
            "causal_factor": category,
        }

    def _score(self, hypothesis: Hypothesis, evidence: list[dict[str, Any]]) -> float:
        if not evidence:
            return hypothesis.prior_confidence * 0.6
        confidences = [_safe_float(item.get("confidence"), hypothesis.prior_confidence) for item in evidence]
        support_ratio = sum(1 for item in evidence if item.get("supports")) / len(evidence)
        weighted = max(confidences) * 0.55 + (sum(confidences) / len(confidences)) * 0.3 + support_ratio * 0.15
        return round(min(0.99, max(0.0, weighted)), 2)

    def _result(
        self,
        hypothesis: Hypothesis,
        confidence: float,
        converged: bool,
        rounds: int,
        evidence: list[dict[str, Any]],
        rejected: list[dict[str, Any]],
    ) -> VerificationResult:
        return VerificationResult(
            anomaly_id=hypothesis.anomaly_id,
            root_cause=hypothesis.description,
            root_cause_category=hypothesis.root_cause_category,
            confidence=round(confidence, 2),
            converged=converged,
            rounds=rounds,
            verified_hypothesis=hypothesis,
            evidence=evidence,
            rejected_hypotheses=rejected,
            recommendation=_recommendation(hypothesis.root_cause_category),
        )


def _category_score(category: str, event: dict[str, Any], evidence: dict[str, Any]) -> float:
    text = _flatten_text(event, evidence)
    direct_flags = {
        "expense_visit_mismatch": ("expense_visit_mismatch", "expense_without_visit", "amount_mismatch", "invoice_mismatch"),
        "distributor_concentration": ("dealer_pattern", "multiple_reps", "channel_pattern", "same_dealer_anomaly"),
        "visit_execution_gap": ("route_anomaly", "gps_anomaly", "visit_gap", "time_conflict", "location_mismatch"),
        "data_quality_issue": ("duplicate_record", "missing_data", "late_sync", "data_quality_issue"),
        "policy_rule_breach": ("rule_hit", "policy_breach", "violation", "red_light"),
    }
    if any(bool(evidence.get(flag) or event.get(flag)) for flag in direct_flags.get(category, ())):
        return 0.9
    if category == "expense_visit_mismatch" and _contains(text, ("expense", "费用", "invoice", "金额", "reimburse")):
        return 0.84
    if category == "distributor_concentration":
        if _related_count(event, evidence) or _contains(text, ("dealer", "经销商", "distributor", "渠道")):
            return 0.86 if _related_count(event, evidence) else 0.74
    if category == "visit_execution_gap" and _contains(text, ("visit", "拜访", "gps", "route", "location", "签到")):
        return 0.82
    if category == "data_quality_issue" and _contains(text, ("duplicate", "重复", "missing", "缺失", "sync", "同步")):
        return 0.8
    if category == "policy_rule_breach" and _contains(text, ("red", "红灯", "violation", "违规", "rule", "规则", "l1", "l2", "l3")):
        return 0.82
    return 0.52


def _related_count(event: dict[str, Any], evidence: dict[str, Any]) -> int:
    for key in ("related_pattern_count", "similar_anomaly_count", "same_dealer_anomaly_count", "other_rep_count"):
        value = event.get(key, evidence.get(key))
        if isinstance(value, (int, float)):
            return int(value)
    for key in ("historical_anomalies", "related_events", "history"):
        value = event.get(key, evidence.get(key))
        if isinstance(value, list):
            return len(value)
    return 0


def _flatten_text(*items: dict[str, Any]) -> str:
    parts: list[str] = []
    for item in items:
        for value in item.values():
            if isinstance(value, dict):
                parts.extend(str(v) for v in value.values())
            elif isinstance(value, list):
                parts.extend(str(v) for v in value[:10])
            else:
                parts.append(str(value))
    return " ".join(parts).lower()


def _contains(text: str, needles: tuple[str, ...]) -> bool:
    return any(needle.lower() in text for needle in needles)


def _safe_float(value: Any, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _recommendation(category: str) -> str:
    mapping = {
        "expense_visit_mismatch": "暂停相关费用结算，复核发票、拜访、流向三类原始凭证后再恢复。",
        "distributor_concentration": "将异常从单代表升级为经销商专项核查，抽检同经销商下其他代表和订单。",
        "visit_execution_gap": "要求补充HCP确认和GPS轨迹证明，并复盘该代表近期拜访计划执行质量。",
        "data_quality_issue": "先冻结自动处罚动作，完成源系统去重、补字段和同步延迟排查。",
        "policy_rule_breach": "按命中规则启动合规处置，并保留审计链供人工复核。",
    }
    return mapping.get(category, "补齐关键证据后由合规负责人复核。")
