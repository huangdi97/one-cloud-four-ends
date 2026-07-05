"""科研轨迹服务，负责 PI 研究轨迹记录、领域转移预测与趋势分析。"""

import json
from datetime import datetime, timedelta

from fastapi import HTTPException
from starlette import status

from cloud.app.research_database import get_research_db
from cloud.app.services.brain.feature_analyzer import run_prediction_fallback
from cloud.app.services.brain.feature_classifier import causal_attribution
from cloud.app.services.brain.feature_extractor import extract_time_series
from cloud.app.services.intel.research_trajectory_stats import ResearchTrajectoryStatsMixin


class ResearchTrajectoryService(ResearchTrajectoryStatsMixin):
    """科研轨迹服务，提供 PI 轨迹记录、领域转移预测与评分、趋势分析。"""

    def _init_db_table(self):
        """初始化 pi_trajectories 和 pi_predictions 数据库表（如不存在则创建）。"""
        db = get_research_db()
        try:
            db.execute(
                "CREATE TABLE IF NOT EXISTS pi_trajectories ("
                "id INTEGER PRIMARY KEY AUTOINCREMENT, pi_id INTEGER NOT NULL, "
                "observation_date TEXT NOT NULL, active_areas TEXT DEFAULT '[]', "
                "area_weights TEXT DEFAULT '{}', dominant_area TEXT DEFAULT '', "
                "source TEXT DEFAULT 'manual', data_quality TEXT DEFAULT 'medium', "
                "created_at TEXT DEFAULT CURRENT_TIMESTAMP, "
                "FOREIGN KEY (pi_id) REFERENCES research_pi_profiles(pi_id))"
            )
            db.execute(
                "CREATE TABLE IF NOT EXISTS pi_predictions ("
                "id INTEGER PRIMARY KEY AUTOINCREMENT, pi_id INTEGER NOT NULL, "
                "prediction_date TEXT NOT NULL, horizon_days INTEGER DEFAULT 90, "
                "predicted_areas TEXT DEFAULT '[]', confidence REAL DEFAULT 0.0, "
                "rationale TEXT DEFAULT '', area_transition TEXT DEFAULT '{}', "
                "created_at TEXT DEFAULT CURRENT_TIMESTAMP, "
                "FOREIGN KEY (pi_id) REFERENCES research_pi_profiles(pi_id))"
            )
            db.commit()
        finally:
            db.close()

    def get_trajectory(self, pi_id: int) -> dict:
        """Retrieve the full research trajectory for a PI, including observations, predictions, and quotations.

        Args:
            pi_id: The PI's ID.

        Returns:
            A dict with pi_info, trajectory_points, recent_predictions, and quotation_trend.

        Raises:
            HTTPException: 404 if the PI is not found.
        """
        db = get_research_db()
        try:
            pi_row = db.execute("SELECT * FROM research_pi_profiles WHERE pi_id = ?", (pi_id,)).fetchone()
            if not pi_row:
                raise HTTPException(status.HTTP_404_NOT_FOUND, detail="PI not found")
            pi_info = dict(pi_row)
            traj_rows = db.execute("SELECT * FROM pi_trajectories WHERE pi_id = ? ORDER BY observation_date ASC", (pi_id,)).fetchall()
            pred_rows = db.execute("SELECT * FROM pi_predictions WHERE pi_id = ? ORDER BY created_at DESC LIMIT 2", (pi_id,)).fetchall()
            quotation_rows = db.execute(
                "SELECT * FROM research_quotations WHERE customer_name LIKE ? ORDER BY created_at DESC",
                (f"%{pi_info['name']}%",),
            ).fetchall()
            return {
                "pi_info": pi_info,
                "trajectory_points": [dict(r) for r in traj_rows],
                "recent_predictions": [dict(r) for r in pred_rows],
                "quotation_trend": [dict(r) for r in quotation_rows],
            }
        finally:
            db.close()

    def predict_trajectory(self, pi_id: int, horizon_days: int = 90) -> dict:
        """Predict a PI's future research trajectory using AI analysis of time-series features.

        Extracts features from trajectory points and quotations over the past year,
        calls an LLM for prediction, and stores the result in pi_predictions.

        Args:
            pi_id: The PI's ID.
            horizon_days: Number of days to forecast (default 90).

        Returns:
            A dict containing predicted_areas, confidence, rationale, and area_transition.

        Raises:
            HTTPException: 404 if the PI is not found.
        """
        self._init_db_table()
        db = get_research_db()
        try:
            pi_row = db.execute("SELECT * FROM research_pi_profiles WHERE pi_id = ?", (pi_id,)).fetchone()
            if not pi_row:
                raise HTTPException(status.HTTP_404_NOT_FOUND, detail="PI not found")
            pi_info = dict(pi_row)
            twelve_months_ago = (datetime.now() - timedelta(days=365)).strftime("%Y-%m-%d")
            traj_rows = db.execute(
                "SELECT * FROM pi_trajectories WHERE pi_id = ? AND observation_date >= ? ORDER BY observation_date ASC",
                (pi_id, twelve_months_ago),
            ).fetchall()
            quotation_rows = db.execute(
                "SELECT * FROM research_quotations WHERE customer_name LIKE ? AND created_at >= ? ORDER BY created_at ASC",
                (f"%{pi_info['name']}%", twelve_months_ago),
            ).fetchall()
            points = [dict(r) for r in traj_rows]
            quotations = [dict(r) for r in quotation_rows]

            features = extract_time_series(pi_id)
            ai_result = self._ai_predict_transition(pi_info, features, horizon_days)

            if ai_result:
                result = ai_result
                result["area_transition"] = {
                    "from_areas": [t["from_area"] for t in features["dominant_transitions"][-2:]] if features["dominant_transitions"] else [],
                    "to_areas": [p["area"] for p in ai_result["predicted_areas"][:2]],
                    "transition_path": ai_result.get("transition_path", []),
                }
                result["confidence"] = round(result["confidence"] * features["stat_features"]["latest_stability_measure"], 2)
                causal_attribution(result, features)
            else:
                result = run_prediction_fallback(points, quotations, pi_info, horizon_days)

            now_str = datetime.now().strftime("%Y-%m-%d")
            db.execute(
                "INSERT INTO pi_predictions (pi_id, prediction_date, horizon_days, "
                "predicted_areas, confidence, rationale, area_transition) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    pi_id,
                    now_str,
                    horizon_days,
                    json.dumps(result["predicted_areas"], ensure_ascii=False),
                    result["confidence"],
                    result["rationale"],
                    json.dumps(result.get("area_transition", {}), ensure_ascii=False),
                ),
            )
            db.commit()
            return result
        finally:
            db.close()

    def _ai_predict_transition(self, pi_info: dict, features: dict, horizon_days: int) -> dict | None:
        """调用 LLM 对 PI 进行领域转移预测。

        Args:
            pi_info: PI 信息字典。
            features: 时间序列特征。
            horizon_days: 预测天数。

        Returns:
            预测结果字典，若 LLM 未返回有效预测则返回 None。
        """
        from cloud.app.services.intel.research_trajectory_ai import build_prediction_prompt, call_llm_for_prediction

        prompt = build_prediction_prompt(pi_info, features, horizon_days)
        result = call_llm_for_prediction(prompt)
        if not result.get("predicted_areas"):
            return None
        return result
