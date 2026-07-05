import json
from unittest.mock import MagicMock, patch

from cloud.app.services.brain.feature_classifier import causal_attribution
from cloud.app.services.brain.feature_extractor import extract_time_series
from cloud.app.services.intel.research_trajectory_service import ResearchTrajectoryService


class TestResearchTrajectory:
    def setup_method(self):
        self.service = ResearchTrajectoryService()

    def test_get_pi_trajectory_score_no_data(self):
        mock_db = MagicMock()
        mock_db.execute.return_value.fetchone.return_value = None
        with patch("cloud.app.services.research_trajectory_stats.get_research_db", return_value=mock_db):
            result = self.service.get_pi_trajectory_score(999)
        assert result["trajectory_score"] == 0
        assert "尚无预测数据" in result["recommendation"]

    def test_offline_visit_score_high(self):
        mock_db = MagicMock()
        pred = {
            "id": 1,
            "pi_id": 1,
            "predicted_areas": json.dumps(
                [
                    {"area": "肿瘤", "probability": 0.9, "trend": "up"},
                ]
            ),
            "data_quality": "high",
            "confidence": 0.9,
            "rationale": "t",
            "area_transition": "{}",
        }
        mock_db.execute.return_value.fetchone.return_value = pred
        with patch("cloud.app.services.research_trajectory_stats.get_research_db", return_value=mock_db):
            result = self.service.get_pi_trajectory_score(1)
        assert 70 <= result["trajectory_score"] <= 100
        assert result["recommendation"] == "高潜力领域，建议重点跟进"

    def test_offline_visit_score_low(self):
        mock_db = MagicMock()
        pred = {
            "id": 2,
            "pi_id": 2,
            "predicted_areas": json.dumps(
                [
                    {"area": "通用", "probability": 0.1, "trend": "stable"},
                ]
            ),
            "data_quality": "low",
            "confidence": 0.1,
            "rationale": "t",
            "area_transition": "{}",
        }
        mock_db.execute.return_value.fetchone.return_value = pred
        with patch("cloud.app.services.research_trajectory_stats.get_research_db", return_value=mock_db):
            result = self.service.get_pi_trajectory_score(2)
        assert 0 <= result["trajectory_score"] < 40

    def test_extract_time_series_simple(self):
        mock_db = MagicMock()
        t1 = {
            "id": 1,
            "pi_id": 1,
            "observation_date": "2025-01-01",
            "dominant_area": "肿瘤",
            "active_areas": '["肿瘤"]',
            "area_weights": '{"肿瘤": 0.8}',
            "source": "manual",
            "data_quality": "medium",
        }
        t2 = {
            "id": 2,
            "pi_id": 1,
            "observation_date": "2025-02-01",
            "dominant_area": "免疫",
            "active_areas": '["免疫"]',
            "area_weights": '{"免疫": 0.6}',
            "source": "manual",
            "data_quality": "medium",
        }
        c1, c2, c3 = MagicMock(), MagicMock(), MagicMock()
        c1.fetchall.return_value = [t1, t2]
        c2.fetchone.return_value = {"pi_id": 1, "name": "Test PI"}
        c3.fetchall.return_value = []
        mock_db.execute.side_effect = [c1, c2, c3]
        with patch("cloud.app.services.feature_extractor.get_research_db", return_value=mock_db):
            result = extract_time_series(1)
        assert "time_points" in result
        assert "dominant_transitions" in result
        assert "stat_features" in result
        assert len(result["time_points"]) == 2
        assert len(result["dominant_transitions"]) == 1
        assert result["stat_features"]["observation_count"] == 2

    def test_causal_attribution(self):
        features = {
            "time_points": [
                {"date": "2025-01", "dominant_area": "A", "active_areas": [], "area_weights": {}, "source": "", "data_quality": "high"},
                {"date": "2025-02", "dominant_area": "A", "active_areas": [], "area_weights": {}, "source": "", "data_quality": "high"},
                {"date": "2025-03", "dominant_area": "B", "active_areas": [], "area_weights": {}, "source": "", "data_quality": "high"},
            ],
            "area_weights_series": {
                "肿瘤": [{"date": "2025-01", "weight": 0.3}, {"date": "2025-02", "weight": 0.5}, {"date": "2025-03", "weight": 0.9}],
            },
            "dominant_transitions": [
                {"from_area": "A", "to_area": "B", "transition_date": "2025-03-01", "interval_days": 30},
            ],
            "event_timeline": [],
            "stat_features": {"observation_count": 3, "transition_count": 1, "avg_interval_days": 30, "latest_stability_measure": 0.67},
        }
        pred = {"predicted_areas": [], "confidence": 0.5, "rationale": "test"}
        result = causal_attribution(pred, features)
        assert len(result["causal_attribution"]["drivers"]) > 0
