"""Accuracy, latency, and confidence calibration evaluation metrics."""

import math
from typing import Sequence


def accuracy_score(correct: int, total: int) -> dict:
    """Compute accuracy as correct / total."""
    if total <= 0:
        return {"accuracy": 0.0, "correct": 0, "total": 0}
    return {
        "accuracy": round(correct / total, 4),
        "correct": correct,
        "total": total,
    }


def latency_stats(latencies: Sequence[float]) -> dict:
    """Compute p50, p95, and mean latency in milliseconds."""
    if not latencies:
        return {"p50_ms": 0.0, "p95_ms": 0.0, "mean_ms": 0.0, "count": 0}
    sorted_lats = sorted(latencies)
    n = len(sorted_lats)
    p50 = sorted_lats[max(0, min(n - 1, int(math.floor(n * 0.50))))]
    p95 = sorted_lats[max(0, min(n - 1, int(math.floor(n * 0.95))))]
    mean = sum(sorted_lats) / n
    return {
        "p50_ms": round(p50 * 1000, 2),
        "p95_ms": round(p95 * 1000, 2),
        "mean_ms": round(mean * 1000, 2),
        "count": n,
    }


def confidence_calibration(
    confidences: Sequence[float],
    correctness: Sequence[bool],
    n_bins: int = 10,
) -> dict:
    """Compute expected calibration error (ECE) over n_bins."""
    if not confidences or len(confidences) != len(correctness):
        return {"ece": 0.0, "bins": [], "count": 0}
    bin_edges = [i / n_bins for i in range(n_bins + 1)]
    bins = []
    ece = 0.0
    for i in range(n_bins):
        lo, hi = bin_edges[i], bin_edges[i + 1]
        in_bin = [(c, corr) for c, corr in zip(confidences, correctness) if lo <= c < hi or (i == n_bins - 1 and c == 1.0)]
        if not in_bin:
            bins.append({"bin": f"[{lo:.1f},{hi:.1f})", "count": 0, "avg_conf": 0.0, "acc": 0.0})
            continue
        avg_conf = sum(x[0] for x in in_bin) / len(in_bin)
        acc = sum(1 for x in in_bin if x[1]) / len(in_bin)
        gap = abs(avg_conf - acc)
        ece += gap * (len(in_bin) / len(confidences))
        bins.append(
            {
                "bin": f"[{lo:.1f},{hi:.1f})",
                "count": len(in_bin),
                "avg_conf": round(avg_conf, 4),
                "acc": round(acc, 4),
            }
        )
    return {"ece": round(ece, 4), "bins": bins, "count": len(confidences)}
