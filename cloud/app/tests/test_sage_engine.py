from unittest.mock import MagicMock, patch

from cloud.app.services.brain.sage_engine_service import SageEngineService
from cloud.app.services.brain.sage_linking import _extract_common_area


class TestSageEngine:
    def setup_method(self):
        self.service = SageEngineService(db=MagicMock())

    def test_score_all_memories_empty(self):
        with (
            patch.object(SageEngineService, "_score_episodic", return_value=0),
            patch.object(SageEngineService, "_score_semantic", return_value=0),
            patch.object(SageEngineService, "_score_procedural", return_value=0),
            patch.object(SageEngineService, "_score_world_tree", return_value=0),
        ):
            result = self.service.score_all_memories()
        assert result["total_scored"] == 0
        assert result["tier_distribution"] == {"hot": 0, "warm": 0, "cold": 0}
        assert result["by_component"] == {"brain_memory": 0, "world_tree": 0}

    def test_normalize(self):
        assert self.service._normalize(5, 0, 10) == 0.5
        assert self.service._normalize(0, 0, 10) == 0.0
        assert self.service._normalize(10, 0, 10) == 1.0
        assert self.service._normalize(10, 10, 10) == 0.0

    def test_evolve_cold_path(self):
        mock_score = {
            "total_scored": 5,
            "tier_distribution": {"hot": 0, "warm": 0, "cold": 2},
            "by_component": {"brain_memory": 0, "world_tree": 0},
            "last_scored_at": "2025-01-01T00:00:00",
        }
        cold_scores = [
            {
                "memory_type": "episodic",
                "memory_id": "e1",
                "component": "brain_memory",
                "score": 10.0,
                "tier": "cold",
                "access_count": 0,
                "utility_score": 0.1,
                "confidence": 0.5,
            },
            {
                "memory_type": "semantic",
                "memory_id": "s1",
                "component": "brain_memory",
                "score": 15.0,
                "tier": "cold",
                "access_count": 0,
                "utility_score": 0.2,
                "confidence": 0.5,
            },
        ]
        self.service.score_all_memories = MagicMock(return_value=mock_score)
        self.service.repo.get_scores_by_tier = MagicMock(side_effect=lambda t: cold_scores if t == "cold" else [])
        self.service.repo.log_evolution = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = {"cnt": 0}
        self.service.db.execute = MagicMock(return_value=mock_cursor)
        with (
            patch("cloud.app.services.sage_engine_service.MemoryConsolidationService") as mcs_cls,
            patch("cloud.app.services.sage_engine_service.BrainEvolutionService") as bes_cls,
        ):
            mcs = mcs_cls.return_value
            bes = bes_cls.return_value
            result = self.service.evolve()
        assert result["cold_consolidated"] == 2
        assert mcs.trigger_consolidation.called
        assert bes.fold_memories.called
        assert self.service.repo.log_evolution.call_count == 2

    def test_extract_common_area(self):
        a = {"area_weights": {"肿瘤": 0.8}}
        b = {"area_weights": {"肿瘤": 0.6}}
        assert _extract_common_area(a, b) == ["肿瘤"]
        assert _extract_common_area({"area_weights": {"A": 1}}, {"area_weights": {"B": 1}}) == []
