from unittest.mock import MagicMock

import pytest

from cloud.app.services.platform_svc.model_compression_service import COMPRESSION_TYPES, ModelCompressionService


class TestModelCompression:
    def setup_method(self):
        self.service = ModelCompressionService(db=MagicMock())

    def test_compress_all_types(self):
        for ct_key in COMPRESSION_TYPES:
            self.service.db = MagicMock()
            c1 = MagicMock()
            c1.fetchone.return_value = None
            c3 = MagicMock()
            c3.fetchone.return_value = {
                "compression_ratio": COMPRESSION_TYPES[ct_key]["compression_ratio"],
                "accuracy_impact": COMPRESSION_TYPES[ct_key]["accuracy_impact"],
            }
            self.service.db.execute.side_effect = [c1, None, c3]
            result = self.service.compress("bert-base-chinese", ct_key)
            assert "compression_ratio" in result
            assert "accuracy_impact" in result
            assert result["compression_ratio"] == COMPRESSION_TYPES[ct_key]["compression_ratio"]

    def test_estimate_size(self):
        assert self.service._estimate_size(1000000) == 4000000
        assert self.service._estimate_size(0) == 0

    def test_get_available_types(self):
        types = self.service.get_available_types()
        keys = [t["key"] for t in types]
        assert "quantum_inspired" in keys

    def test_compress_invalid_type(self):
        with pytest.raises(ValueError):
            self.service.compress("bert-base-chinese", "nonexistent")
