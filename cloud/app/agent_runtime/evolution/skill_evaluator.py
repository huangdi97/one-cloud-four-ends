"""追踪工具 / 技能调用成功率，基于历史表现给出降级建议。"""

import json
import logging
import threading
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

from cloud.app.agent_runtime.evolution.feedback_collector import FeedbackCollector
from cloud.app.agent_runtime.evolution.skill_library import SkillLibrary

logger = logging.getLogger(__name__)

DEFAULT_EVAL_PATH = "data/skill_eval.json"


class SkillEvaluator:
    """追踪每个技能 / 工具的成功率，根据趋势给出降级或重训建议。

    评估维度：
    - 调用成功率（success / total）
    - 近 N 次趋势
    - 用户反馈关联
    """

    def __init__(self, skill_library: SkillLibrary, feedback_collector: FeedbackCollector, storage_path: str = DEFAULT_EVAL_PATH):
        """Initialize skill evaluator with skill library and feedback collector."""
        self._skill_library = skill_library
        self._feedback_collector = feedback_collector
        self._path = Path(storage_path)
        self._lock = threading.Lock()
        self._stats: dict[str, dict[str, Any]] = defaultdict(lambda: {"success": 0, "total": 0, "recent": [], "avg_latency": 0.0})
        self._load()

    def _load(self):
        if self._path.exists():
            try:
                with open(self._path) as f:
                    raw = json.load(f)
                self._stats = defaultdict(
                    lambda: {"success": 0, "total": 0, "recent": [], "avg_latency": 0.0},
                    raw,
                )
            except Exception as e:
                logger.warning("SkillEvaluator: failed to load %s: %s", self._path, e)

    def _save(self):
        self._path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self._path.with_suffix(".tmp")
        with open(tmp, "w") as f:
            json.dump(dict(self._stats), f, ensure_ascii=False, indent=2)
        tmp.replace(self._path)

    def record_call(self, skill_name: str, success: bool, latency: float = 0.0):
        """记录一次工具 / 技能调用结果。

        Args:
            skill_name: 技能名称
            success: 是否成功
            latency: 调用耗时（秒）
        """
        with self._lock:
            stat = self._stats[skill_name]
            stat["success"] += 1 if success else 0
            stat["total"] += 1
            stat["recent"].append({"success": success, "latency": latency, "timestamp": datetime.utcnow().isoformat()})
            if len(stat["recent"]) > 50:
                stat["recent"] = stat["recent"][-50:]
            n = stat["total"]
            prev_avg = stat["avg_latency"]
            stat["avg_latency"] = round((prev_avg * (n - 1) + latency) / n, 4)
            self._skill_library.record_use(skill_name, success)
            self._save()

    def get_success_rate(self, skill_name: str, window: int = 0) -> float:
        """查询技能成功率。

        Args:
            skill_name: 技能名称
            window: 若 >0 则只统计最近 N 次

        Returns:
            成功率 0~1，无数据返回 0.0
        """
        with self._lock:
            stat = self._stats.get(skill_name)
            if not stat or stat["total"] == 0:
                return 0.0
            if window > 0:
                recent = stat["recent"][-window:]
                if not recent:
                    return 0.0
                return sum(1 for r in recent if r["success"]) / len(recent)
            return stat["success"] / stat["total"]

    def get_degradation_suggestion(self, skill_name: str) -> dict[str, Any]:
        """分析技能表现，给出降级或改进建议。

        Args:
            skill_name: 技能名称

        Returns:
            {skill_name, success_rate, trend, suggestion, severity}
        """
        with self._lock:
            stat = self._stats.get(skill_name)
            if not stat or stat["total"] == 0:
                return {"skill_name": skill_name, "success_rate": 0.0, "trend": "unknown", "suggestion": "insufficient_data", "severity": "none"}

            overall = stat["success"] / stat["total"]
            recent_window = min(10, len(stat["recent"]))
            if recent_window >= 3:
                recent = stat["recent"][-recent_window:]
                recent_rate = sum(1 for r in recent if r["success"]) / len(recent)
            else:
                recent_rate = overall

            trend = "stable"
            if recent_rate < overall - 0.15:
                trend = "declining"
            elif recent_rate > overall + 0.15:
                trend = "improving"

            suggestion = "none"
            severity = "none"
            if recent_rate < 0.4 or overall < 0.4:
                suggestion = "decommission"
                severity = "critical"
            elif recent_rate < 0.6 or overall < 0.6:
                suggestion = "retrain_or_redesign"
                severity = "high"
            elif recent_rate < 0.8 or overall < 0.8:
                suggestion = "monitor_and_refine"
                severity = "medium"
            elif trend == "declining":
                suggestion = "watch_trend"
                severity = "low"

            avg_rating = self._feedback_collector.get_avg_rating("*", skill_name)
            if avg_rating and avg_rating < 3.0:
                suggestion = "urgent_review"
                severity = "critical"

            return {
                "skill_name": skill_name,
                "success_rate": round(overall, 4),
                "recent_rate": round(recent_rate, 4),
                "trend": trend,
                "total_calls": stat["total"],
                "avg_latency": stat["avg_latency"],
                "avg_user_rating": avg_rating,
                "suggestion": suggestion,
                "severity": severity,
            }

    def list_evaluations(self) -> dict[str, dict[str, Any]]:
        """返回所有技能的评估结果。"""
        with self._lock:
            return {name: self.get_degradation_suggestion(name) for name in list(self._stats.keys())}

    def get_bottom_skills(self, top_n: int = 5) -> list[dict[str, Any]]:
        """返回成功率最低的 N 个技能。"""
        evals = self.list_evaluations()
        sorted_evals = sorted(
            evals.values(),
            key=lambda e: (e["success_rate"], -e["total_calls"]),
        )
        return sorted_evals[:top_n]
