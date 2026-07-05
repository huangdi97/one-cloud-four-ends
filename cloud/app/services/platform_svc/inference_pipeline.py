"""推演管线服务 — 串接 causal_service + hypothesizer + verifier + pattern_discovery + narrator。"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Optional

from cloud.app.analysis import (
    HypothesisVerifier,
    Hypothesizer,
    Narrator,
    PatternDiscovery,
)
from cloud.app.services.brain.causal_service import CausalService


@dataclass
class CausalChain:
    path: list[str]
    strength: float
    evidence: list[str] = field(default_factory=list)


@dataclass
class PredictionInterval:
    low: str
    high: str


@dataclass
class ParallelCase:
    entity: str
    action: str
    outcome: str
    similarity: float


@dataclass
class BacktestResult:
    method: str
    accuracy: str


@dataclass
class InferenceResult:
    chains: list[dict]
    confidence: float
    prediction_interval: dict
    parallel_cases: list[dict]
    backtest: dict
    narrative: str


class InferencePipeline:
    def __init__(
        self,
        hypothesizer: Optional[Hypothesizer] = None,
        verifier: HypothesisVerifier | None = None,
        pattern_discovery: PatternDiscovery | None = None,
        narrator: Narrator | None = None,
        causal_service: CausalService | None = None,
    ):
        self._hypothesizer = hypothesizer or Hypothesizer()
        self._verifier = verifier or HypothesisVerifier()
        self._pattern_discovery = pattern_discovery or PatternDiscovery()
        self._narrator = narrator or Narrator()
        self._causal_service = causal_service or CausalService()

    async def run(
        self,
        scenario: str,
        domain: str,
        user_id: str,
        horizon_days: int = 90,
    ) -> InferenceResult:
        anomaly_event = self._build_event(scenario, domain, user_id)
        hypotheses = self._hypothesizer.generate_hypotheses(anomaly_event)
        chains = self._build_causal_chains(hypotheses, domain)
        parallel_cases = self._discover_parallel_cases(anomaly_event)
        backtest = self._run_backtest(hypotheses, anomaly_event)
        narrative = self._generate_narrative(scenario, chains, backtest)
        confidence = self._compute_confidence(chains, backtest)
        prediction_interval = self._estimate_interval(scenario, chains, horizon_days)
        return InferenceResult(
            chains=[asdict(c) if isinstance(c, CausalChain) else c for c in chains],
            confidence=confidence,
            prediction_interval=asdict(prediction_interval),
            parallel_cases=[asdict(p) if isinstance(p, ParallelCase) else p for p in parallel_cases],
            backtest=asdict(backtest),
            narrative=narrative,
        )

    def _build_event(self, scenario: str, domain: str, user_id: str) -> dict[str, Any]:
        return {
            "anomaly_id": f"scenario-{domain}",
            "scenario": scenario,
            "domain": domain,
            "user_id": user_id,
            "signals": {domain: {"scenario": scenario, "severity": "high"}},
            "evidence": {"description": scenario, "domain": domain},
            "metadata": {"source": "inference_pipeline", "type": "what_if"},
        }

    def _build_causal_chains(self, hypotheses: list, domain: str) -> list[CausalChain]:
        chains: list[CausalChain] = []
        for h in hypotheses:
            path_parts = [h.description[:20]]
            if h.root_cause_category:
                path_parts.append(h.root_cause_category)
            strength = self._causal_service.causal_infer(
                features={h.root_cause_category: h.prior_confidence},
                target=domain,
            )
            weight = strength.get("feature_weights", {}).get(h.root_cause_category, h.prior_confidence)
            chains.append(
                CausalChain(
                    path=[h.description, h.root_cause_category, domain, "影响"],
                    strength=round(weight, 4),
                    evidence=[h.hypothesis_id],
                )
            )
        chains.sort(key=lambda c: c.strength, reverse=True)
        return chains[:5]

    def _discover_parallel_cases(self, anomaly_event: dict) -> list[ParallelCase]:
        patterns = self._pattern_discovery.discover(anomaly_event)
        return [
            ParallelCase(
                entity=p.summary[:20],
                action=p.matched_dimensions[0] if p.matched_dimensions else "调整",
                outcome=p.escalation,
                similarity=round(p.similarity, 4),
            )
            for p in patterns[:5]
        ]

    def _run_backtest(self, hypotheses: list, anomaly_event: dict) -> BacktestResult:
        hypothesis = hypotheses[0] if hypotheses else None
        if hypothesis:
            result = self._verifier.verify(hypothesis)
            accuracy = f"{result.rounds}次回溯验证，置信度{result.confidence:.0%}"
        else:
            accuracy = "无可用假设验证"
        return BacktestResult(
            method="用历史数据模拟同样决策",
            accuracy=accuracy,
        )

    def _generate_narrative(self, scenario: str, chains: list[CausalChain], backtest: BacktestResult) -> str:
        top = chains[0] if chains else None
        if top:
            return f"如果{scenario}，根据历史模式：{top.path[0]}→{top.path[1]}，因果强度{top.strength:.0%}。{backtest.accuracy}。"
        return f"如果{scenario}，当前无足够历史数据形成可靠推演。"

    def _compute_confidence(self, chains: list[CausalChain], backtest: BacktestResult) -> float:
        if not chains:
            return 0.0
        avg_strength = sum(c.strength for c in chains) / len(chains)
        return round(min(avg_strength * 1.1, 0.95), 4)

    def _estimate_interval(self, scenario: str, chains: list[CausalChain], horizon_days: int) -> PredictionInterval:
        avg = sum(c.strength for c in chains) / len(chains) if chains else 0.3
        return PredictionInterval(
            low=f"转化率下降{int(avg * 5)}%",
            high=f"转化率下降{int(avg * 18)}%",
        )
