"""E2E tests: diversion detection → holographic audit engine → red-light notification."""

import sqlite3
from unittest.mock import MagicMock

from cloud.app.services.compliance_svc.diversion_service import DiversionDetectionService


class TestDiversionHolographicE2E:
    def test_diversion_triggers_holographic_and_red_light(self):
        db = sqlite3.connect(":memory:")
        mock_notifier = MagicMock()
        svc = DiversionDetectionService(db, notifier=mock_notifier)

        result = svc.check_distribution(
            {
                "product": "药X",
                "region": "beijing",
                "authorized_region": "shanghai",
                "quantity": 200,
                "dealer_id": "dlr-001",
                "rep_id": "rep-001",
            }
        )

        assert result["is_diversion"] is True
        assert result["severity"] == "high"
        assert result["holographic_score"] is not None
        assert result["holographic_level"] is not None

        mock_notifier.send.assert_called()
        call_args = mock_notifier.send.call_args_list
        messages = [args[0][0] for args in call_args]
        assert any("[红灯]" in msg for msg in messages)

        records = svc.get_diversion_records("rep-001", days=30)
        assert len(records) >= 1
        assert records[0]["is_diversion"] == 1
        assert records[0]["holographic_score"] is not None
        db.close()

    def test_diversion_low_quantity_holographic_escalates(self):
        db = sqlite3.connect(":memory:")
        mock_notifier = MagicMock()
        svc = DiversionDetectionService(db, notifier=mock_notifier)

        result = svc.check_distribution(
            {
                "product": "药Y",
                "region": "beijing",
                "authorized_region": "shanghai",
                "quantity": 30,
                "dealer_id": "dlr-002",
                "rep_id": "rep-002",
            }
        )

        assert result["is_diversion"] is True
        assert result["severity"] == "high"
        assert result["holographic_score"] is not None
        assert result["holographic_level"] is not None

        mock_notifier.send.assert_called()
        db.close()

    def test_normal_distribution_no_diversion(self):
        db = sqlite3.connect(":memory:")
        svc = DiversionDetectionService(db)

        result = svc.check_distribution(
            {
                "product": "药Z",
                "region": "shanghai",
                "authorized_region": "shanghai",
                "quantity": 50,
                "rep_id": "rep-003",
            }
        )

        assert result["is_diversion"] is False
        assert result["holographic_score"] is None
        db.close()

    def test_diversion_log_persistence_with_holographic(self):
        db = sqlite3.connect(":memory:")
        svc = DiversionDetectionService(db)

        svc.check_distribution(
            {
                "product": "药W",
                "region": "guangzhou",
                "authorized_region": "shenzhen",
                "quantity": 500,
                "dealer_id": "dlr-003",
                "rep_id": "rep-004",
            }
        )

        rows = db.execute("SELECT * FROM diversion_log").fetchall()
        assert len(rows) >= 1
        cols = [d[0] for d in db.execute("SELECT * FROM diversion_log").description]
        row = dict(zip(cols, rows[0]))
        assert row["is_diversion"] == 1
        assert row["severity"] == "high"
        assert row["holographic_score"] is not None
        assert row["holographic_level"] is not None
        assert row["holographic_findings"] is not None
        db.close()
