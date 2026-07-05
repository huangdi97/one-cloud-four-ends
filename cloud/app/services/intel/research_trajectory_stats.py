"""研究轨迹统计方法，包含 PI 轨迹评分与趋势分析。"""

from collections import Counter
from datetime import datetime, timedelta

from cloud.app.research_database import get_research_db
from cloud.app.services.brain.feature_extractor import normalize_areas


class ResearchTrajectoryStatsMixin:
    """研究轨迹统计方法，提供轨迹评分与趋势分析。"""

    def _compute_area_trajectory_score(self, pred: dict, quality_factor: float, area: str | None) -> dict:
        predicted_areas = normalize_areas(pred.get("predicted_areas", "[]"))
        quality = pred.get("data_quality", "medium") if "data_quality" in pred else "medium"
        if area:
            target = [p for p in predicted_areas if isinstance(p, dict) and p.get("area") == area]
        else:
            target = [p for p in predicted_areas if isinstance(p, dict)]
        if not target:
            return {
                "trajectory_score": 0,
                "data_quality": quality,
                "recommendation": "指定领域无预测数据",
            }
        max_prob = max(p.get("probability", 0) for p in target)
        best = max(target, key=lambda x: x.get("probability", 0))
        trend = best.get("trend", "stable")
        trend_bonus = 10 if trend == "up" else -10 if trend == "down" else 0
        trajectory_score = min(100, round(max_prob * 100 * quality_factor + trend_bonus))
        if trajectory_score >= 70:
            recommendation = "高潜力领域，建议重点跟进"
        elif trajectory_score >= 40:
            recommendation = "中等潜力，建议保持关注"
        else:
            recommendation = "低活跃度，建议观察"
        return {
            "trajectory_score": trajectory_score,
            "data_quality": quality,
            "recommendation": recommendation,
        }

    def _compute_trend_data(self, since: str) -> dict:
        db = get_research_db()
        try:
            traj_rows = db.execute("SELECT dominant_area, active_areas FROM pi_trajectories WHERE observation_date >= ?", (since,)).fetchall()
            pred_rows = db.execute("SELECT predicted_areas FROM pi_predictions WHERE prediction_date >= ?", (since,)).fetchall()
            dominant_counter = Counter()
            active_counter = Counter()
            for row in traj_rows:
                if row["dominant_area"]:
                    dominant_counter[row["dominant_area"]] += 1
                for a in normalize_areas(row["active_areas"]):
                    if isinstance(a, str):
                        active_counter[a] += 1
            pred_area_counter = Counter()
            for row in pred_rows:
                for p in normalize_areas(row["predicted_areas"]):
                    if isinstance(p, dict):
                        area = p.get("area", "")
                        if area:
                            pred_area_counter[area] += 1
                    elif isinstance(p, str):
                        pred_area_counter[p] += 1
            return {"dominant_counter": dominant_counter, "active_counter": active_counter, "pred_area_counter": pred_area_counter}
        finally:
            db.close()

    def get_pi_trajectory_score(self, pi_id: int, area: str | None = None) -> dict:
        """Compute a trajectory score for a PI, optionally scoped to a specific research area.

        Uses the latest prediction, data quality weighting, and trend bonuses to produce
        a 0-100 score with a human-readable recommendation.

        Args:
            pi_id: The PI's ID.
            area: Optional specific research area to score. If None, scores all areas.

        Returns:
            A dict with pi_id, area, trajectory_score, data_quality, recommendation, and source_prediction_id.
        """
        QUALITY_MAP = {"high": 1.0, "medium": 0.8, "low": 0.5}
        db = get_research_db()
        try:
            pred_row = db.execute(
                "SELECT * FROM pi_predictions WHERE pi_id = ? ORDER BY created_at DESC LIMIT 1",
                (pi_id,),
            ).fetchone()
            if not pred_row:
                return {
                    "pi_id": pi_id,
                    "area": area or "all",
                    "trajectory_score": 0,
                    "data_quality": "low",
                    "recommendation": "尚无预测数据，请先执行预测",
                    "source_prediction_id": None,
                }
            pred = dict(pred_row)
            quality = pred.get("data_quality", "medium") if "data_quality" in pred else "medium"
            quality_factor = QUALITY_MAP.get(quality, 0.8)
            score_data = self._compute_area_trajectory_score(pred, quality_factor, area)
            return {
                "pi_id": pi_id,
                "area": area or "all",
                **score_data,
                "source_prediction_id": pred["id"],
            }
        finally:
            db.close()

    def _analyze_trend_areas(self, dominant_counter, active_counter, pred_area_counter) -> dict:
        all_areas = dominant_counter + active_counter + pred_area_counter
        total = sum(all_areas.values()) or 1
        sorted_areas = all_areas.most_common()
        hot = [{"area": a, "count": c, "ratio": round(c / total, 2)} for a, c in sorted_areas[:5]]
        emerging = []
        declining = []
        for a, c in sorted_areas:
            ratio = c / total
            in_traj = a in dominant_counter
            in_pred = a in pred_area_counter
            if in_pred and not in_traj:
                emerging.append({"area": a, "count": c, "ratio": round(ratio, 2)})
            if in_traj and not in_pred:
                declining.append({"area": a, "count": c, "ratio": round(ratio, 2)})
        return {"hot_areas": hot[:5], "emerging_areas": emerging[:5], "declining_areas": declining[:5]}

    def get_trends(self, days: int = 90) -> dict:
        """Retrieve research area trends including hot, emerging, and declining areas.

        Analyzes dominant areas from trajectories and predicted areas from predictions
        over the specified number of days.

        Args:
            days: Lookback window in days (default 90).

        Returns:
            A dict with hot_areas, emerging_areas, and declining_areas lists.
        """
        since = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
        counters = self._compute_trend_data(since)
        return self._analyze_trend_areas(counters["dominant_counter"], counters["active_counter"], counters["pred_area_counter"])
