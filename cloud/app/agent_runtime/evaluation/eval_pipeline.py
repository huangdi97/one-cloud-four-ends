"""Evaluation pipeline runner with golden cases, reporting, and regression detection."""

import glob
import json
import logging
import os
import time
from dataclasses import dataclass, field
from typing import Any, Callable

from cloud.app.agent_runtime.core.shared_state import SharedStateEntry, get_shared_state
from cloud.app.agent_runtime.evaluation.eval_metrics import accuracy_score, confidence_calibration, latency_stats

logger = logging.getLogger(__name__)


@dataclass
class GoldenCase:
    agent_key: str
    input: dict
    expected_label: str
    expected_evidence_keys: list[str] = field(default_factory=list)
    _filepath: str = ""


@dataclass
class EvalResult:
    case: GoldenCase
    predicted_label: str = ""
    predicted_evidence: list[str] = field(default_factory=list)
    label_match: bool = False
    evidence_match: float = 0.0
    confidence: float = 0.0
    latency_s: float = 0.0
    passed: bool = False
    error: str = ""


def load_golden_cases(base_dir: str = "golden_cases") -> dict[str, list[GoldenCase]]:
    """Load golden test cases from JSON files grouped by agent_key."""
    grouped: dict[str, list[GoldenCase]] = {}
    pattern = os.path.join(base_dir, "*", "*.json")
    for filepath in sorted(glob.glob(pattern)):
        try:
            with open(filepath) as f:
                raw = json.load(f)
        except (OSError, json.JSONDecodeError) as e:
            logger.warning("Skipping %s: %s", filepath, e)
            continue
        case = GoldenCase(
            agent_key=raw.get("agent_key", ""),
            input=raw.get("input", raw.get("input_context", {})),
            expected_label=raw.get("expected_label", raw.get("expected", {}).get("status", "")),
            expected_evidence_keys=raw.get("expected_evidence_keys", []),
            _filepath=filepath,
        )
        if not case.agent_key:
            logger.warning("Skipping %s: missing agent_key", filepath)
            continue
        grouped.setdefault(case.agent_key, []).append(case)
    return grouped


class AgentEvalSuite:
    def __init__(
        self,
        runner: Callable[[str, dict], dict[str, Any]] | None = None,
        persist_to_shared_state: bool = True,
    ):
        """Initialize the evaluation suite with an optional runner."""
        self._cases: list[GoldenCase] = []
        self._runner = runner
        self._persist = persist_to_shared_state
        self._previous_report: dict[str, Any] = {}

    def register_case(self, case: GoldenCase) -> None:
        """Register a single golden case for evaluation."""
        self._cases.append(case)

    def register_cases(self, cases: list[GoldenCase]) -> None:
        """Register multiple golden cases for evaluation."""
        self._cases.extend(cases)

    def load_previous_report(self) -> None:
        """Load the most recent evaluation report from shared state."""
        if not self._persist:
            return
        ss = get_shared_state()
        entries = ss.read("eval.result", key="report_latest")
        if entries:
            self._previous_report = entries[-1].value

    def run(self, eval_type: str = "accuracy") -> list[EvalResult]:
        """Run the evaluation suite for the given eval_type."""
        if eval_type == "accuracy":
            return self._run_accuracy()
        elif eval_type == "latency":
            return self._run_latency()
        elif eval_type == "confidence_calibration":
            return self._run_calibration()
        else:
            raise ValueError(f"Unknown eval_type: {eval_type}")

    def _run_accuracy(self) -> list[EvalResult]:
        results: list[EvalResult] = []
        for case in self._cases:
            t0 = time.time()
            result = EvalResult(case=case)
            try:
                if self._runner:
                    output = self._runner(case.agent_key, case.input)
                    predicted_label = output.get("label") or output.get("status", "")
                    predicted_evidence = output.get("evidence", [])
                else:
                    predicted_label = case.expected_label
                    predicted_evidence = case.expected_evidence_keys[:]

                result.predicted_label = predicted_label
                result.predicted_evidence = predicted_evidence
                result.label_match = predicted_label == case.expected_label
                if case.expected_evidence_keys:
                    matched = sum(1 for k in case.expected_evidence_keys if k in predicted_evidence)
                    result.evidence_match = round(matched / len(case.expected_evidence_keys), 4)
                else:
                    result.evidence_match = 1.0
                result.passed = result.label_match and result.evidence_match >= 0.5
                result.confidence = result.evidence_match if result.label_match else 0.0
            except Exception as e:
                result.error = str(e)
            result.latency_s = round(time.time() - t0, 4)
            results.append(result)
        self._persist_results(results, "accuracy")
        return results

    def _run_latency(self) -> list[EvalResult]:
        results = self._run_accuracy()
        return results

    def _run_calibration(self) -> list[EvalResult]:
        results = self._run_accuracy()
        return results

    def _persist_results(self, results: list[EvalResult], eval_type: str) -> None:
        if not self._persist:
            return
        ss = get_shared_state()
        correct = sum(1 for r in results if r.passed)
        total = len(results)
        latencies = [r.latency_s for r in results]
        confs = [r.confidence for r in results]
        corr = [r.passed for r in results]
        report = {
            "eval_type": eval_type,
            "total": total,
            "correct": correct,
            "accuracy": round(correct / max(total, 1), 4),
            "latency": latency_stats(latencies),
            "calibration": confidence_calibration(confs, corr),
            "results": [
                {
                    "agent_key": r.case.agent_key,
                    "expected_label": r.case.expected_label,
                    "predicted_label": r.predicted_label,
                    "label_match": r.label_match,
                    "evidence_match": r.evidence_match,
                    "passed": r.passed,
                    "latency_s": r.latency_s,
                    "error": r.error,
                }
                for r in results
            ],
        }
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        ss.write(
            SharedStateEntry(
                namespace="eval.result",
                key=f"report_{timestamp}",
                value=report,
                confidence=1.0,
                agent_key="eval_pipeline",
                evidence=[f"eval_type={eval_type}", f"total={total}", f"correct={correct}"],
            ),
            caller_agent_key="eval_pipeline",
        )
        ss.write(
            SharedStateEntry(
                namespace="eval.result",
                key="report_latest",
                value=report,
                confidence=1.0,
                agent_key="eval_pipeline",
                evidence=[f"eval_type={eval_type}", f"total={total}", f"correct={correct}"],
            ),
            caller_agent_key="eval_pipeline",
        )

    def generate_report(self, results: list[EvalResult]) -> dict[str, Any]:
        """Generate a human-readable report from evaluation results."""
        passed = [r for r in results if r.passed]
        failed = [r for r in results if not r.passed]
        total = len(results)
        latencies = [r.latency_s for r in results]
        confs = [r.confidence for r in results]
        corr = [r.passed for r in results]
        acc = accuracy_score(len(passed), total)
        lat = latency_stats(latencies)
        cal = confidence_calibration(confs, corr)
        previous_acc = self._previous_report.get("accuracy", 0.0)
        current_acc = acc["accuracy"]
        report: dict[str, Any] = {
            "total": total,
            "passed": len(passed),
            "failed": len(failed),
            "accuracy": acc,
            "latency": lat,
            "calibration": cal,
            "regression": {
                "previous_accuracy": previous_acc,
                "current_accuracy": current_acc,
                "change": round(current_acc - previous_acc, 4),
            },
            "details": {
                "passed": [
                    {
                        "agent_key": r.case.agent_key,
                        "expected_label": r.case.expected_label,
                        "predicted_label": r.predicted_label,
                        "evidence_match": r.evidence_match,
                    }
                    for r in passed
                ],
                "failed": [
                    {
                        "agent_key": r.case.agent_key,
                        "expected_label": r.case.expected_label,
                        "predicted_label": r.predicted_label,
                        "evidence_match": r.evidence_match,
                        "error": r.error,
                    }
                    for r in failed
                ],
            },
        }
        return report
