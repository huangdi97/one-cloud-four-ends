import sqlite3

from cloud.app.services.compliance_svc.diversion_service import DiversionDetectionService


class TestDiversionService:
    def test_diversion_detect_cross_region(self):
        db = sqlite3.connect(":memory:")
        svc = DiversionDetectionService(db)
        result = svc.check_distribution(
            {
                "product": "药A",
                "region": "beijing",
                "authorized_region": "shanghai",
                "quantity": 60,
            }
        )
        assert result["is_diversion"] is True
        assert result["severity"] == "medium"
        db.close()

    def test_diversion_detect_stuffing(self):
        db = sqlite3.connect(":memory:")
        svc = DiversionDetectionService(db)
        result = svc.check_distribution(
            {
                "product": "药B",
                "region": "shanghai",
                "authorized_region": "shanghai",
                "quantity": 100,
            }
        )
        assert result["is_diversion"] is False
        db.close()

    def test_diversion_anomaly_fluctuation(self):
        db = sqlite3.connect(":memory:")
        svc = DiversionDetectionService(db)
        result = svc.check_distribution(
            {
                "product": "药C",
                "region": "guangzhou",
                "authorized_region": "shenzhen",
                "quantity": 1000,
            }
        )
        assert result["is_diversion"] is True
        assert result["severity"] == "high"
        db.close()

    def test_diversion_ignore_normal(self):
        db = sqlite3.connect(":memory:")
        svc = DiversionDetectionService(db)
        result = svc.check_distribution(
            {
                "product": "药D",
                "region": "beijing",
                "authorized_region": "beijing",
                "quantity": 50,
            }
        )
        assert result["is_diversion"] is False
        db.close()
